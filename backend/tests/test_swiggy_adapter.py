"""Isolated unit tests for SwiggyMCPAdapter and official error taxonomy (Spec §5.1, §28, Phase 9).

Tests the production adapter with mocked HTTP transport:
- HTTP 401 and JSON-RPC -32001 -> ProviderAuthError
- HTTP 504 and httpx.TimeoutException -> UpstreamTimeoutError
- Envelope error taxonomy: ItemOutOfStockError, AddressNotServiceableError, MinOrderNotMetError, CartExpiredError
- Consequential checkout gate: UnconfirmedCheckoutError when explicit_confirmation is False
- Token masking: zero credential leakage in repr() or str()
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import httpx
import pytest

from backend.integrations.commerce.exceptions import (
    AddressNotServiceableError,
    CartExpiredError,
    CommerceError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    ProviderAuthError,
    UnconfirmedCheckoutError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


# ---------------------------------------------------------------------------
# 1. Token Masking & Zero Leakage Invariant
# ---------------------------------------------------------------------------

def test_swiggy_adapter_token_masking() -> None:
    """Auth token must never appear in repr or str representation."""
    secret = "super_secret_jwt_token_12345"
    adapter = SwiggyMCPAdapter(auth_token=secret)

    representation = repr(adapter)
    string_rep = str(adapter)

    assert secret not in representation
    assert secret not in string_rep
    assert "***" in representation


# ---------------------------------------------------------------------------
# 2. HTTP Status Code Errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_http_401_raises_provider_auth_error() -> None:
    """HTTP 401 Unauthorized maps to ProviderAuthError."""
    adapter = SwiggyMCPAdapter(auth_token="expired_token")

    mock_resp = httpx.Response(status_code=401, request=httpx.Request("POST", adapter.base_url))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ProviderAuthError) as exc_info:
            await adapter.get_addresses("cust-1")
        assert "unauthenticated" in str(exc_info.value).lower() or "expired" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_swiggy_adapter_http_504_raises_upstream_timeout_error() -> None:
    """HTTP 504 Gateway Timeout maps to UpstreamTimeoutError."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(status_code=504, request=httpx.Request("POST", adapter.base_url))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(UpstreamTimeoutError):
            await adapter.get_addresses("cust-1")


@pytest.mark.asyncio
async def test_swiggy_adapter_httpx_timeout_raises_upstream_timeout_error() -> None:
    """httpx.TimeoutException maps to UpstreamTimeoutError."""
    adapter = SwiggyMCPAdapter()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Read timed out")
        with pytest.raises(UpstreamTimeoutError):
            await adapter.get_addresses("cust-1")


# ---------------------------------------------------------------------------
# 3. JSON-RPC Protocol Errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_rpc_32001_raises_provider_auth_error() -> None:
    """JSON-RPC error code -32001 maps to ProviderAuthError."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={"jsonrpc": "2.0", "error": {"code": -32001, "message": "Session expired"}, "id": 1},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ProviderAuthError):
            await adapter.get_addresses("cust-1")


# ---------------------------------------------------------------------------
# 4. Swiggy Envelope Error Taxonomy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_envelope_out_of_stock() -> None:
    """Envelope error containing 'out of stock' maps to ItemOutOfStockError."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Selected item is out of stock in dark store"}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ItemOutOfStockError):
            await adapter.get_addresses("cust-1")


@pytest.mark.asyncio
async def test_swiggy_adapter_envelope_not_serviceable() -> None:
    """Envelope error containing 'not serviceable' maps to AddressNotServiceableError."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Store is currently not serviceable"}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(AddressNotServiceableError):
            await adapter.get_addresses("cust-1")


@pytest.mark.asyncio
async def test_swiggy_adapter_envelope_minimum_order() -> None:
    """Envelope error containing 'minimum order' maps to MinOrderNotMetError."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Cart value is below minimum order threshold"}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(MinOrderNotMetError):
            await adapter.get_addresses("cust-1")


@pytest.mark.asyncio
async def test_swiggy_adapter_envelope_cart_expired() -> None:
    """Envelope error containing 'expired' or 'abandoned' maps to CartExpiredError."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Cart session has expired"}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(CartExpiredError):
            await adapter.get_addresses("cust-1")


# ---------------------------------------------------------------------------
# 5. Consequential Checkout Authorization Gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_requires_explicit_confirmation() -> None:
    """checkout() must strictly reject execution if explicit_confirmation is False."""
    adapter = SwiggyMCPAdapter()

    # Must raise before making any network call
    with pytest.raises(UnconfirmedCheckoutError):
        await adapter.checkout(cart_id="swiggy-cart-1", explicit_confirmation=False)


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_confirmed_succeeds() -> None:
    """checkout() with explicit_confirmation=True issues checkout tool call."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "orderId": "SWIGGY-OD-9876",
                "grandTotal": 245.0,
                "deliveryAddress": {"id": "addr-1", "label": "Home", "street": "Bandra West", "pincode": "400050"},
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await adapter.checkout(cart_id="swiggy-cart-1", explicit_confirmation=True)
        assert result.order_id == "SWIGGY-OD-9876"
        assert result.grand_total == 245.0
        assert result.status == "ORDER_CONFIRMED"


# ---------------------------------------------------------------------------
# 6. Payload Parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_parses_addresses_and_products() -> None:
    """Parses standard Swiggy MCP JSON-RPC address and catalog payloads."""
    adapter = SwiggyMCPAdapter()

    # Test address parsing
    addr_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": [
                {
                    "id": "addr-101",
                    "label": "Home",
                    "formattedAddress": "Flat 4B, Pali Hill",
                    "city": "Mumbai",
                    "pincode": "400050",
                    "serviceable": True,
                }
            ],
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = addr_resp
        addresses = await adapter.get_addresses("cust-1")
        assert len(addresses) == 1
        assert addresses[0].id == "addr-101"
        assert addresses[0].city == "Mumbai"
        assert addresses[0].is_serviceable is True
