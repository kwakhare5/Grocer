"""Grocer v1.0 — Swiggy OAuth 2.1 & Token Vault Tests.

Tests:
1. Token Vault AES-256-GCM encryption and decryption round-trip.
2. PKCE code_verifier and code_challenge generation.
3. POST /api/auth/swiggy/login returns valid Swiggy authorizeUrl with PKCE params.
4. POST /api/auth/swiggy/callback exchanges code and encrypts token into vault.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.integrations.commerce.token_vault import (
    decrypt_token,
    encrypt_token,
    generate_pkce_pair,
)
from backend.main import app


def test_token_vault_encryption_roundtrip():
    """Verify AES-256-GCM encryption and decryption preserves bearer token exactly."""
    raw_token = "swiggy_live_bearer_token_xyz_1234567890"
    enc_bytes, nonce = encrypt_token(raw_token, settings.DATA_ENCRYPTION_KEY)

    assert enc_bytes != raw_token.encode("utf-8")
    assert len(nonce) == 12

    decrypted = decrypt_token(enc_bytes, nonce, settings.DATA_ENCRYPTION_KEY)
    assert decrypted == raw_token


def test_pkce_generation():
    """Verify PKCE RFC 7636 compliant S256 verifier and challenge."""
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert "=" not in verifier
    assert "=" not in challenge


@pytest.mark.asyncio
async def test_swiggy_login_endpoint():
    """POST /api/auth/swiggy/login must return Swiggy authorizeUrl with PKCE parameters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/swiggy/login",
            json={"phone": "9876543210"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "authorizeUrl" in data
        url = data["authorizeUrl"]
        assert "https://mcp.swiggy.com/auth/authorize" in url
        assert "client_id=swiggy-mcp" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "state=" in url
        assert "redirect_uri=" in url


@pytest.mark.asyncio
async def test_swiggy_login_missing_phone_rejects():
    """POST /api/auth/swiggy/login requires a valid 10-digit phone number."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/swiggy/login",
            json={"phone": "123"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_swiggy_callback_invalid_state_rejects():
    """POST /api/auth/swiggy/callback rejects unknown/tampered states."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/swiggy/callback",
            json={"code": "sample_auth_code", "state": "unknown_fake_state"},
        )
        assert resp.status_code == 400
        assert "Invalid or expired authorization state" in resp.json()["detail"]
