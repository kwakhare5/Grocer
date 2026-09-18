"""Swiggy OAuth 2.1 with PKCE implementation (RFC 7636, RFC 7591, RFC 8414).

Adheres strictly to Swiggy Builders Club specifications:
- Dynamic Client Registration (RFC 7591) at POST /auth/register
- PKCE S256 challenge generation
- State management and CSRF prevention
- Clean authorization code exchange at POST /auth/token
- Session revocation at POST /auth/logout
- Zero credential leakage in logs
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import threading
import time
from typing import Any, Optional
import httpx
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger("grocer.integrations.swiggy_oauth")

DEFAULT_AUTH_BASE_URL = "https://mcp.swiggy.com/auth"
DEFAULT_REDIRECT_URI = "https://grocerr.vercel.app"


def base64url_encode(data: bytes) -> str:
    """Encode bytes using URL-safe Base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_code_verifier(byte_length: int = 32) -> str:
    """Generate high-entropy cryptographic PKCE code_verifier (RFC 7636 §4.1)."""
    random_bytes = secrets.token_bytes(byte_length)
    return base64url_encode(random_bytes)


def generate_code_challenge(verifier: str) -> str:
    """Generate SHA-256 PKCE code_challenge (RFC 7636 §4.2)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64url_encode(digest)


def generate_state(byte_length: int = 16) -> str:
    """Generate cryptographically secure random anti-CSRF state token."""
    return secrets.token_urlsafe(byte_length)


class PendingAuthFlow(BaseModel):
    """Temporary storage for in-flight OAuth PKCE handshake."""
    state: str
    code_verifier: str
    customer_id: str
    redirect_uri: str
    client_id: str
    created_at: float = Field(default_factory=time.time)
    expires_at: float

    def __repr__(self) -> str:
        return "PendingAuthFlow(state=***, customer=***, verifier=***)"

    def __str__(self) -> str:
        return repr(self)


class SwiggyOAuthManager:
    """Manages Swiggy OAuth 2.1 PKCE lifecycle, DCR, and token exchange."""

    def __init__(
        self,
        base_url: str = DEFAULT_AUTH_BASE_URL,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        client_id_override: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.redirect_uri = redirect_uri
        self._cached_client_id: Optional[str] = client_id_override
        self._pending_flows: dict[str, PendingAuthFlow] = {}
        self._lock = threading.Lock()

    async def get_or_register_client_id(self, client_name: str = "GROCER") -> str:
        """Fetch cached client_id or dynamically register via RFC 7591."""
        if self._cached_client_id:
            return self._cached_client_id

        register_url = f"{self.base_url}/register"
        payload = {
            "client_name": client_name,
            "redirect_uris": [self.redirect_uri],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(register_url, json=payload)
                if res.status_code in (200, 201):
                    data = res.json()
                    registered_id = data.get("client_id")
                    if registered_id:
                        self._cached_client_id = str(registered_id)
                        logger.info("Successfully registered dynamic client_id with Swiggy")
                        return self._cached_client_id
                logger.warning(
                    "Swiggy DCR returned HTTP %d; using the standard client.",
                    res.status_code,
                )
        except Exception as exc:
            logger.warning("Swiggy DCR error: %s. Falling back to default client", exc)

        self._cached_client_id = "swiggy-mcp"
        return self._cached_client_id

    async def initiate_flow(
        self,
        customer_id: str,
        redirect_uri: Optional[str] = None,
        scope: str = "mcp:tools",
    ) -> tuple[str, str]:
        """Initiate OAuth 2.1 PKCE authorization.

        Returns:
            tuple: (authorize_url, state)
        """
        effective_redirect = redirect_uri or self.redirect_uri
        client_id = await self.get_or_register_client_id()

        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        state = generate_state()

        flow = PendingAuthFlow(
            state=state,
            code_verifier=verifier,
            customer_id=customer_id,
            redirect_uri=effective_redirect,
            client_id=client_id,
            expires_at=time.time() + 600.0,  # 10 minutes TTL
        )

        with self._lock:
            # Clean up expired pending flows
            now = time.time()
            self._pending_flows = {k: v for k, v in self._pending_flows.items() if v.expires_at > now}
            self._pending_flows[state] = flow

        query_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": effective_redirect,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "scope": scope,
        }
        encoded_query = httpx.QueryParams(query_params)
        authorize_url = f"{self.base_url}/authorize?{encoded_query}"
        return authorize_url, state

    async def exchange_code(
        self,
        code: str,
        state: str,
        code_verifier: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> dict[str, Any]:
        """Exchange authorization code for Swiggy access token.

        Validates state and PKCE code_verifier.
        """
        pending_flow: Optional[PendingAuthFlow] = None
        with self._lock:
            pending_flow = self._pending_flows.pop(state, None)

        if pending_flow is None:
            raise ValueError("OAuth state is invalid or has expired.")

        effective_verifier = pending_flow.code_verifier
        effective_redirect = pending_flow.redirect_uri
        client_id = pending_flow.client_id

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": effective_verifier,
            "redirect_uri": effective_redirect,
            "client_id": client_id,
        }

        token_url = f"{self.base_url}/token"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                token_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )

            if resp.status_code != 200:
                err_data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                err_msg = err_data.get("error_description") or err_data.get("error") or f"HTTP {resp.status_code}"
                raise ValueError(f"Swiggy token exchange failed: {err_msg}")

            token_data = resp.json()
            if "access_token" not in token_data:
                raise ValueError("Swiggy token exchange response missing 'access_token'.")

            token_data["customer_id"] = pending_flow.customer_id
            token_data["client_id"] = client_id
            return token_data

    async def revoke_session(self, access_token: str) -> bool:
        """Revoke active session on Swiggy server (POST /auth/logout)."""
        logout_url = f"{self.base_url}/logout"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    logout_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                return res.status_code in (200, 204)
        except Exception as exc:
            logger.warning("Failed to revoke session with Swiggy: %s", exc)
            return False


# Default singleton instance
default_oauth_manager = SwiggyOAuthManager(
    client_id_override=settings.SWIGGY_CLIENT_ID,
)
