"""Grocer v1.0 — Swiggy OAuth 2.1 PKCE Flow, Callback and Parked Replay.

Endpoints:
- POST /api/auth/swiggy/login: initiates PKCE from a signed bot link, returns authorizeUrl
- POST /api/auth/swiggy/callback: stores the token and replays the parked request (ADR 0010)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.channels.link_tokens import verify_link_token
from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.token_vault import (
    consume_pkce_session,
    generate_pkce_pair,
    resolve_user_token,
    store_pkce_session,
    store_user_token,
)

logger = logging.getLogger("grocer.swiggy_auth")

router = APIRouter(prefix="/api/auth/swiggy", tags=["auth"])


class LoginRequest(BaseModel):
    token: str = Field(..., description="Signed link token from the WhatsApp bot")


class LoginResponse(BaseModel):
    authorizeUrl: str
    state: str


class CallbackRequest(BaseModel):
    code: str
    state: str


class CallbackResponse(BaseModel):
    success: bool
    message: str
    replayed: dict[str, Any] | None = None


class _SignedWebhookRequest:
    """Minimal Request stand-in for replaying a stored message through the webhook."""

    def __init__(self, body: bytes, signature: str) -> None:
        self._body = body
        self.headers = {"X-Hub-Signature-256": signature}

    async def body(self) -> bytes:
        return self._body


def _signed_replay_request(message: dict[str, Any]) -> _SignedWebhookRequest:
    fresh = dict(message)
    fresh["id"] = f"wamid.replay.{uuid.uuid4()}"
    fresh["timestamp"] = str(int(time.time()))
    envelope = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "replay",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {},
                            "messages": [fresh],
                        },
                    }
                ],
            }
        ],
    }
    body = json.dumps(envelope).encode("utf-8")
    signature = "sha256=" + hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return _SignedWebhookRequest(body, signature)


async def _replay_cart_action(user_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from backend.integrations.commerce.swiggy_client import SwiggyClient

    token = await resolve_user_token(user_id)
    if not token:
        raise RuntimeError("No Swiggy token for parked replay")
    items = (payload.get("payload") or {}).get("items") or []
    await asyncio.to_thread(SwiggyClient(auth_token=token).update_cart, items)
    return {"status": "replayed", "action": payload.get("action"), "items": len(items)}


async def replay_parked_request(
    user_id: Any,
    wa_client: Any | None = None,
    swiggy_client: Any | None = None,
) -> dict[str, Any] | None:
    """Claim the parked request and run it again through the normal pipeline."""
    from backend.agent.address_lifecycle import TokenParkedRequestManager

    manager = TokenParkedRequestManager()
    popped = await manager.pop_parked_request(user_id)
    if popped is None:
        return None
    row_id, payload = popped

    try:
        if "action" in payload:
            result = await _replay_cart_action(user_id, payload)
        else:
            from backend.channels.whatsapp import handle_webhook

            result = await handle_webhook(
                _signed_replay_request(payload),
                swiggy_client=swiggy_client,
                wa_client=wa_client,
            )
    except Exception as exc:  # noqa: BLE001 - restore the list instead of losing it
        logger.warning("Parked replay failed for %s: %s", user_id, exc)
        await manager.restore_parked(row_id)
        return None

    await manager.mark_replayed(row_id)
    return result


@router.post("/login", response_model=LoginResponse)
async def swiggy_login(req: LoginRequest) -> LoginResponse:
    """Start PKCE for the number that received the bot's link, never a caller-supplied one."""
    wa_id = verify_link_token(req.token)
    if not wa_id:
        raise HTTPException(
            status_code=400,
            detail="This link is invalid or expired. Message the bot on WhatsApp for a new one.",
        )

    verifier, challenge = generate_pkce_pair()
    state = base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8").rstrip("=")

    await store_pkce_session(state=state, verifier=verifier, phone=wa_id)

    query_params = {
        "response_type": "code",
        "client_id": "swiggy-mcp",
        "redirect_uri": settings.SWIGGY_REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "mcp:tools",
    }
    authorize_url = (
        f"{settings.SWIGGY_MCP_BASE_URL}/auth/authorize?{urlencode(query_params)}"
    )

    return LoginResponse(authorizeUrl=authorize_url, state=state)


async def finish_login(
    wa_id: str,
    token_data: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> CallbackResponse:
    """Store the token, then replay the parked list in the background."""
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 432000)

    if not access_token:
        raise HTTPException(status_code=502, detail="Swiggy response missing access_token")

    pool = await get_db_pool()
    user_row = await pool.fetchrow(
        """
        INSERT INTO grocer.users (wa_id) VALUES ($1)
        ON CONFLICT (wa_id) DO UPDATE SET updated_at = NOW()
        RETURNING id;
        """,
        wa_id,
    )
    user_id = user_row["id"]

    await store_user_token(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=expires_in,
    )

    background_tasks.add_task(replay_parked_request, user_id)

    return CallbackResponse(
        success=True,
        message=(
            "Swiggy account linked. If you had a saved list, it will resume in WhatsApp."
        ),
        replayed=None,
    )


@router.post("/callback", response_model=CallbackResponse)
async def swiggy_callback(
    req: CallbackRequest,
    background_tasks: BackgroundTasks,
) -> CallbackResponse:
    """Exchange the authorization code for a Swiggy token and finish the login."""
    session_data = await consume_pkce_session(req.state)
    if not session_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired authorization state. Please try logging in again.",
        )

    verifier = session_data["verifier"]
    wa_id = session_data["phone"]

    token_url = f"{settings.SWIGGY_MCP_BASE_URL}/auth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": req.code,
        "code_verifier": verifier,
        "redirect_uri": settings.SWIGGY_REDIRECT_URI,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_url, json=payload)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Swiggy token exchange failed: {resp.text}",
                )
            data: dict[str, Any] = resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Swiggy authentication server: {exc}",
        ) from exc

    return await finish_login(wa_id, data, background_tasks)
