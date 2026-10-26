"""Grocer v1.0 — Durable AES-256-GCM Token Vault & PKCE Engine.

Handles:
1. RFC 7636 PKCE S256 verifier and challenge generation.
2. AES-256-GCM token encryption with 12-byte cryptographically secure nonces.
3. Durable token storage in grocer.oauth_tokens.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.config import settings
from backend.database import get_db_pool

logger = logging.getLogger("grocer.token_vault")

# In-memory PKCE state cache: state -> {"verifier": verifier, "phone": phone, "created_at": datetime}
_PKCE_SESSIONS: dict[str, dict[str, Any]] = {}

# Serializes refresh-token rotation per user. Swiggy rotates the refresh token on
# every exchange, so two concurrent refreshes would invalidate each other.
_REFRESH_LOCKS: dict[str, asyncio.Lock] = {}


def _refresh_lock(user_id: uuid.UUID) -> asyncio.Lock:
    key = str(user_id)
    lock = _REFRESH_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _REFRESH_LOCKS[key] = lock
    return lock


def generate_pkce_pair() -> tuple[str, str]:
    """Generate RFC 7636 compliant code_verifier and code_challenge."""
    verifier_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")

    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    return code_verifier, code_challenge


def encrypt_token(raw_token: str, key_b64: str) -> tuple[bytes, bytes]:
    """Encrypt bearer token using AES-256-GCM with a fresh 12-byte nonce."""
    key = base64.urlsafe_b64decode(key_b64)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    encrypted_bytes = aesgcm.encrypt(nonce, raw_token.encode("utf-8"), None)
    return encrypted_bytes, nonce


def decrypt_token(encrypted_bytes: bytes, nonce: bytes, key_b64: str) -> str:
    """Decrypt AES-256-GCM ciphertext back into plain text bearer token."""
    key = base64.urlsafe_b64decode(key_b64)
    aesgcm = AESGCM(key)
    decrypted_bytes = aesgcm.decrypt(nonce, encrypted_bytes, None)
    return decrypted_bytes.decode("utf-8")


def store_pkce_session(state: str, verifier: str, phone: str) -> None:
    """Record pending PKCE authorization state."""
    _PKCE_SESSIONS[state] = {
        "verifier": verifier,
        "phone": phone,
        "created_at": datetime.now(timezone.utc),
    }


def consume_pkce_session(state: str) -> dict[str, Any] | None:
    """Consume and invalidate PKCE session by state (one-time use)."""
    return _PKCE_SESSIONS.pop(state, None)


async def store_user_token(
    user_id: uuid.UUID,
    access_token: str,
    refresh_token: str | None = None,
    expires_in_seconds: int = 432000,
    key_b64: str = settings.DATA_ENCRYPTION_KEY,
) -> None:
    """Save encrypted access token (and rotated refresh token) to Supabase grocer.oauth_tokens."""
    encrypted_bytes, nonce = encrypt_token(access_token, key_b64)
    encrypted_refresh: bytes | None = None
    refresh_nonce: bytes | None = None
    if refresh_token:
        encrypted_refresh, refresh_nonce = encrypt_token(refresh_token, key_b64)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    pool = await get_db_pool()
    query = """
        INSERT INTO grocer.oauth_tokens AS stored (
            user_id, key_version, encrypted_token, nonce,
            refresh_token, refresh_nonce, expires_at, updated_at
        )
        VALUES ($1, 1, $2, $3, $4, $5, $6, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            encrypted_token = EXCLUDED.encrypted_token,
            nonce = EXCLUDED.nonce,
            refresh_token = COALESCE(EXCLUDED.refresh_token, stored.refresh_token),
            refresh_nonce = COALESCE(EXCLUDED.refresh_nonce, stored.refresh_nonce),
            expires_at = EXCLUDED.expires_at,
            updated_at = NOW();
    """
    await pool.execute(
        query,
        user_id,
        encrypted_bytes,
        nonce,
        encrypted_refresh,
        refresh_nonce,
        expires_at,
    )


async def get_user_token(
    user_id: uuid.UUID,
    key_b64: str = settings.DATA_ENCRYPTION_KEY,
) -> str | None:
    """Retrieve and decrypt active token from Supabase if not expired."""
    pool = await get_db_pool()
    query = """
        SELECT encrypted_token, nonce, expires_at
        FROM grocer.oauth_tokens
        WHERE user_id = $1 AND expires_at > NOW();
    """
    row = await pool.fetchrow(query, user_id)
    if not row:
        return None

    return decrypt_token(row["encrypted_token"], row["nonce"], key_b64)


async def get_refresh_token(
    user_id: uuid.UUID,
    key_b64: str = settings.DATA_ENCRYPTION_KEY,
) -> str | None:
    """Retrieve and decrypt the stored refresh token from Supabase."""
    pool = await get_db_pool()
    query = """
        SELECT refresh_token, refresh_nonce
        FROM grocer.oauth_tokens
        WHERE user_id = $1 AND refresh_token IS NOT NULL;
    """
    row = await pool.fetchrow(query, user_id)
    if not row or not row["refresh_token"]:
        return None

    return decrypt_token(row["refresh_token"], row["refresh_nonce"], key_b64)


async def resolve_user_token(
    user_id: uuid.UUID,
    key_b64: str = settings.DATA_ENCRYPTION_KEY,
) -> str | None:
    """Return a usable access token: current token if valid, else one silent refresh.

    Returns None only when there is no refresh token or Swiggy rejects it, which
    is the caller's signal to ask the customer to reconnect.
    """
    token = await get_user_token(user_id, key_b64)
    if token:
        return token
    return await refresh_user_token(user_id, key_b64)


async def refresh_user_token(
    user_id: uuid.UUID,
    key_b64: str = settings.DATA_ENCRYPTION_KEY,
    force: bool = False,
) -> str | None:
    """Exchange the stored refresh token for a fresh access token via /auth/token.

    Args:
        force: Refresh even if the stored access token still looks valid. Used
            after Swiggy returns 401 on a token our clock still trusts.

    Returns the new access token, or None if no refresh token exists or the
    exchange fails (caller falls back to full re-authorization).
    """
    async with _refresh_lock(user_id):
        if not force:
            current = await get_user_token(user_id, key_b64)
            if current:
                return current

        refresh_token = await get_refresh_token(user_id, key_b64)
        if not refresh_token:
            return None

        token_url = f"{settings.SWIGGY_MCP_BASE_URL}/auth/token"
        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(token_url, json=payload)
                if resp.status_code != 200:
                    logger.warning("Swiggy refresh token exchange failed: HTTP %s", resp.status_code)
                    return None
                data: dict[str, Any] = resp.json()
        except httpx.RequestError as exc:
            logger.warning("Swiggy refresh token exchange network error: %s", exc)
            return None

        access_token = data.get("access_token")
        if not access_token:
            return None

        new_refresh = data.get("refresh_token") or refresh_token
        expires_in = int(data.get("expires_in", 432000))
        await store_user_token(
            user_id=user_id,
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in_seconds=expires_in,
            key_b64=key_b64,
        )
        return access_token
