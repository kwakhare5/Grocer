"""Secure server-side token storage for Swiggy OAuth credentials.

Enforces:
- Separation of OAuth session from conversational IntentContract
- Zero token leakage in repr(), str(), and logs
- Expiration tracking with safety buffer (60s)
- Revocation handling
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("grocer.integrations.token_vault")


class SwiggyTokenEntry(BaseModel):
    """Secure server-side container for an authenticated Swiggy session."""
    access_token: str
    token_type: str = "Bearer"
    expires_at: float  # Unix epoch timestamp in seconds
    scope: str = "mcp:tools"
    client_id: Optional[str] = None
    created_at: float = Field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"SwiggyTokenEntry(expires_at={self.expires_at}, scope={self.scope!r}, token=***)"

    def __str__(self) -> str:
        return repr(self)

    @property
    def is_expired(self) -> bool:
        """Return True if token is expired or within 60s expiry safety window."""
        return time.time() >= (self.expires_at - 60.0)


class SwiggyTokenVault:
    """Thread-safe server-side in-memory token vault for Swiggy MCP credentials."""

    def __init__(self) -> None:
        self._tokens: dict[str, SwiggyTokenEntry] = {}
        self._lock = threading.Lock()

    def store_token(
        self,
        customer_id: str,
        access_token: str,
        expires_in: int,
        token_type: str = "Bearer",
        scope: str = "mcp:tools",
        client_id: Optional[str] = None,
    ) -> SwiggyTokenEntry:
        """Store or update a token entry securely."""
        expires_at = time.time() + float(expires_in)
        entry = SwiggyTokenEntry(
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at,
            scope=scope,
            client_id=client_id,
        )
        with self._lock:
            self._tokens[customer_id] = entry
        logger.info("Stored Swiggy token for customer=%s (expires_in=%ds)", customer_id, expires_in)
        return entry

    def get_token(self, customer_id: str) -> Optional[str]:
        """Return valid unexpired access token, or None if missing or expired."""
        with self._lock:
            entry = self._tokens.get(customer_id)
            if not entry:
                return None
            if entry.is_expired:
                logger.info("Swiggy token expired for customer=%s", customer_id)
                del self._tokens[customer_id]
                return None
            return entry.access_token

    def get_entry(self, customer_id: str) -> Optional[SwiggyTokenEntry]:
        """Return full token entry if valid, else None."""
        with self._lock:
            entry = self._tokens.get(customer_id)
            if not entry:
                return None
            if entry.is_expired:
                del self._tokens[customer_id]
                return None
            return entry

    def is_authenticated(self, customer_id: str) -> bool:
        """Check if customer currently has a valid, non-expired Swiggy session."""
        return self.get_token(customer_id) is not None

    def revoke_token(self, customer_id: str) -> Optional[str]:
        """Remove and return token from vault for revocation."""
        with self._lock:
            entry = self._tokens.pop(customer_id, None)
            return entry.access_token if entry else None

    def clear(self) -> None:
        """Clear all stored tokens."""
        with self._lock:
            self._tokens.clear()


# Default singleton instance
default_token_vault = SwiggyTokenVault()
