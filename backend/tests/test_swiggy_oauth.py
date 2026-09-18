"""Unit tests for Swiggy OAuth 2.1 PKCE, DCR, and TokenVault (Phase A)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from cryptography.fernet import Fernet

from backend.integrations.commerce.swiggy_oauth import (
    PostgresPendingAuthFlowStore,
    SwiggyOAuthManager,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from backend.integrations.commerce.token_vault import SwiggyTokenEntry, SwiggyTokenVault


class _TokenPool:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    async def fetch(self, query: str) -> list[dict[str, object]]:
        del query
        return list(self.rows.values())

    async def execute(self, query: str, *args: object) -> str:
        if "INSERT INTO grocer_internal.oauth_tokens" in query:
            customer_id, ciphertext, expires_at = args
            self.rows[str(customer_id)] = {
                "customer_id": customer_id,
                "ciphertext": ciphertext,
                "expires_at": expires_at,
            }
            return "INSERT 0 1"
        if "DELETE FROM grocer_internal.oauth_tokens" in query:
            self.rows.pop(str(args[0]), None)
            return "DELETE 1"
        raise AssertionError("Unexpected query")


class _FlowPool:
    def __init__(self) -> None:
        self.rows: dict[bytes, bytes] = {}

    async def execute(self, query: str, *args: object) -> str:
        if "DELETE FROM grocer_internal.oauth_pending_flows" in query:
            return "DELETE 0"
        assert "INSERT INTO grocer_internal.oauth_pending_flows" in query
        state_hash, ciphertext, _expires_at = args
        self.rows[bytes(state_hash)] = bytes(ciphertext)
        return "INSERT 0 1"

    async def fetchrow(self, query: str, state_hash: bytes) -> dict[str, bytes] | None:
        assert "DELETE FROM grocer_internal.oauth_pending_flows" in query
        ciphertext = self.rows.pop(state_hash, None)
        return {"ciphertext": ciphertext} if ciphertext else None


def test_pkce_verifier_and_challenge() -> None:
    """Test PKCE verifier generation and S256 challenge computation."""
    verifier = generate_code_verifier(32)
    assert len(verifier) >= 43  # RFC 7636 min length
    assert "-" in verifier or "_" in verifier or verifier.isalnum()

    challenge1 = generate_code_challenge(verifier)
    challenge2 = generate_code_challenge(verifier)
    assert challenge1 == challenge2
    assert len(challenge1) >= 43


def test_state_generation() -> None:
    """Test cryptographically secure state token generation."""
    state1 = generate_state(16)
    state2 = generate_state(16)
    assert state1 != state2
    assert len(state1) >= 16


def test_token_vault_masking_and_lifecycle() -> None:
    """TokenVault must never leak tokens in repr/str and handle expiration buffer."""
    vault = SwiggyTokenVault()
    secret = "secret_access_token_xyz"
    entry = vault.store_token("cust-1", secret, expires_in=300)

    assert secret not in repr(entry)
    assert secret not in str(entry)
    assert "***" in repr(entry)
    assert entry.access_token == secret
    assert vault.is_authenticated("cust-1") is True
    assert vault.get_token("cust-1") == secret

    # Test expired token with 60s buffer
    vault.store_token("cust-2", secret, expires_in=50)  # expires_in < 60s -> already considered expired
    assert vault.get_token("cust-2") is None
    assert vault.is_authenticated("cust-2") is False

    # Test revocation
    revoked = vault.revoke_token("cust-1")
    assert revoked == secret
    assert vault.is_authenticated("cust-1") is False


@pytest.mark.asyncio
async def test_durable_token_vault_encrypts_at_rest_and_survives_restart() -> None:
    pool = _TokenPool()
    key = Fernet.generate_key().decode("ascii")
    secret = "never-store-this-token-in-plaintext"
    first = SwiggyTokenVault()
    await first.configure_postgres(pool, key)

    await first.store_token_durable("cust-1", secret, expires_in=300)

    ciphertext = bytes(pool.rows["cust-1"]["ciphertext"])
    assert secret.encode() not in ciphertext
    restarted = SwiggyTokenVault()
    await restarted.configure_postgres(pool, key)
    assert restarted.get_token("cust-1") == secret


@pytest.mark.asyncio
async def test_postgres_pkce_flow_is_single_use_across_manager_instances() -> None:
    pool = _FlowPool()
    store = PostgresPendingAuthFlowStore(pool, Fernet.generate_key().decode("ascii"))
    first = SwiggyOAuthManager(
        base_url="https://mcp.swiggy.com/auth",
        client_id_override="test-client",
        flow_store=store,
    )
    _, state = await first.initiate_flow(customer_id="cust-restart")

    restarted = SwiggyOAuthManager(
        base_url="https://mcp.swiggy.com/auth",
        client_id_override="test-client",
        flow_store=store,
    )
    flow = await restarted._flow_store.consume(state)

    assert flow is not None
    assert flow.customer_id == "cust-restart"
    assert await restarted._flow_store.consume(state) is None


@pytest.mark.asyncio
async def test_oauth_dcr_registration() -> None:
    """Dynamic Client Registration (RFC 7591) at POST /auth/register."""
    manager = SwiggyOAuthManager(base_url="https://mcp.swiggy.com/auth")

    mock_resp = httpx.Response(
        status_code=201,
        json={"client_id": "swiggy-registered-client-999"},
        request=httpx.Request("POST", "https://mcp.swiggy.com/auth/register"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        client_id = await manager.get_or_register_client_id()
        assert client_id == "swiggy-registered-client-999"


@pytest.mark.asyncio
async def test_oauth_initiate_flow() -> None:
    """Initiate flow creates valid PKCE S256 authorization URL and records state."""
    manager = SwiggyOAuthManager(base_url="https://mcp.swiggy.com/auth", client_id_override="test-client")
    auth_url, state = await manager.initiate_flow(
        customer_id="cust-test",
        redirect_uri="https://grocerr.vercel.app",
    )

    assert "https://mcp.swiggy.com/auth/authorize?" in auth_url
    assert "code_challenge_method=S256" in auth_url
    assert f"state={state}" in auth_url
    assert "client_id=test-client" in auth_url
    assert "redirect_uri=https%3A%2F%2Fgrocerr.vercel.app" in auth_url


@pytest.mark.asyncio
async def test_oauth_exchange_code_success() -> None:
    """Code exchange verifies PKCE verifier and stores token."""
    manager = SwiggyOAuthManager(base_url="https://mcp.swiggy.com/auth", client_id_override="test-client")
    _, state = await manager.initiate_flow(customer_id="cust-test")

    mock_token_resp = httpx.Response(
        status_code=200,
        json={
            "access_token": "valid_token_123",
            "token_type": "Bearer",
            "expires_in": 432000,
            "scope": "mcp:tools",
        },
        request=httpx.Request("POST", "https://mcp.swiggy.com/auth/token"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_token_resp
        data = await manager.exchange_code(code="test-auth-code", state=state)
        assert data["access_token"] == "valid_token_123"
        assert data["customer_id"] == "cust-test"


@pytest.mark.asyncio
async def test_oauth_exchange_code_invalid_state_or_missing_verifier() -> None:
    """Code exchange with unknown state or missing verifier raises ValueError."""
    manager = SwiggyOAuthManager()
    with pytest.raises(ValueError) as exc:
        await manager.exchange_code(code="code", state="unknown-state")
    assert "state is invalid" in str(exc.value)

    with pytest.raises(ValueError, match="state is invalid"):
        await manager.exchange_code(
            code="code",
            state="attacker-state",
            code_verifier="attacker-verifier",
            redirect_uri="https://attacker.invalid/callback",
        )
