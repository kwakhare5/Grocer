"""Grocer v1.0 — Durable AES-256-GCM Token Vault & PKCE Engine.

Handles:
1. RFC 7636 PKCE S256 verifier and challenge generation.
2. AES-256-GCM token encryption with 12-byte cryptographically secure nonces.
3. Durable token storage in grocer.oauth_tokens.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.config import settings
from backend.database import get_db_pool

# In-memory PKCE state cache: state -> {"verifier": verifier, "phone": phone, "created_at": datetime}
_PKCE_SESSIONS: dict[str, dict[str, Any]] = {}


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
    expires_in_seconds: int = 432000,
    key_b64: str = settings.DATA_ENCRYPTION_KEY,
) -> None:
    """Save encrypted token to Supabase grocer.oauth_tokens."""
    encrypted_bytes, nonce = encrypt_token(access_token, key_b64)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    pool = await get_db_pool()
    query = """
        INSERT INTO grocer.oauth_tokens (user_id, key_version, encrypted_token, nonce, expires_at, updated_at)
        VALUES ($1, 1, $2, $3, $4, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            encrypted_token = EXCLUDED.encrypted_token,
            nonce = EXCLUDED.nonce,
            expires_at = EXCLUDED.expires_at,
            updated_at = NOW();
    """
    await pool.execute(query, user_id, encrypted_bytes, nonce, expires_at)


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
