"""Grocer v1.0 — Swiggy OAuth 2.1 PKCE Flow & Callback Handler.

Endpoints:
- POST /api/auth/swiggy/login: Initiates PKCE flow and returns authorizeUrl
- POST /api/auth/swiggy/callback: Exchanges authorization code with Swiggy, stores token, and replays parked messages (ADR 0010)
"""

from __future__ import annotations

import base64
import os
import re
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.token_vault import (
    consume_pkce_session,
    generate_pkce_pair,
    store_pkce_session,
    store_user_token,
)

router = APIRouter(prefix="/api/auth/swiggy", tags=["auth"])


class LoginRequest(BaseModel):
    phone: str = Field(..., description="10-digit mobile number")


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


def normalize_phone(phone_str: str) -> str:
    """Extract clean 10-digit phone number with 91 country code prefix."""
    digits = re.sub(r"\D", "", phone_str)
    if len(digits) < 10:
        raise HTTPException(
            status_code=400,
            detail="Valid 10-digit mobile number required",
        )
    return f"91{digits[-10:]}"


@router.post("/login", response_model=LoginResponse)
async def swiggy_login(req: LoginRequest) -> LoginResponse:
    """Generate PKCE S256 parameters and return the official Swiggy authorizeUrl."""
    wa_id = normalize_phone(req.phone)

    # Generate PKCE verifier & challenge
    verifier, challenge = generate_pkce_pair()
    state = base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8").rstrip("=")

    # Store pending session
    store_pkce_session(state=state, verifier=verifier, phone=wa_id)

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


@router.post("/callback", response_model=CallbackResponse)
async def swiggy_callback(req: CallbackRequest) -> CallbackResponse:
    """Exchange OAuth authorization code for Swiggy access token and store in vault."""
    session_data = consume_pkce_session(req.state)
    if not session_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired authorization state. Please try logging in again.",
        )

    verifier = session_data["verifier"]
    wa_id = session_data["phone"]

    # Exchange authorization code with Swiggy
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

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 432000)

    if not access_token:
        raise HTTPException(
            status_code=502,
            detail="Swiggy response missing access_token",
        )

    # Get or create user in Supabase
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

    # Save encrypted token (and refresh token for 401 auto-refresh)
    await store_user_token(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=expires_in,
    )

    # Replay parked requests (ADR 0010)
    from backend.agent.address_lifecycle import TokenParkedRequestManager

    parked_mgr = TokenParkedRequestManager()
    replayed = await parked_mgr.pop_and_replay_request(user_id)

    return CallbackResponse(
        success=True,
        message="Swiggy account linked successfully! You can now order directly on WhatsApp.",
        replayed=replayed,
    )
