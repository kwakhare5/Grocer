"""Comprehensive provider-contract tests for SwiggyMCPAdapter (Spec §5.1, §28, Phase B).

Tests the production adapter with mocked HTTP transport across:
1. Authentication: success, 401, expired token, 419 revoked session
2. Address: one address, multiple addresses, pagination, no addresses, malformed response
3. Search: products, variations, missing fields, OOS
4. Cart: successful update, partial update, stale cart, min order, unserviceable
5. Checkout: confirmation false, confirmation true, successful order, multiple orders, pending UPI, 5xx / timeout non-idempotent guard
6. Tracking: successful tracking, status mapping, polling interval
7. Token masking & zero leakage invariant
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import httpx
import pytest

from backend.integrations.commerce.exceptions import (
    CommerceError,
    AddressNotServiceableError,
    CartExpiredError,
    CommerceError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    OrderStateUnknownError,
    ProviderAuthError,
    ProviderSessionRevokedError,
    UnconfirmedCheckoutError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.models import CartItemUpdate
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
# 2. Authentication Contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_auth_success() -> None:
    """Successful tool call with valid Bearer token."""
    adapter = SwiggyMCPAdapter(auth_token="valid_jwt")
    mock_resp = httpx.Response(
        status_code=200,
        json={"success": True, "data": {"addresses": []}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        addresses = await adapter.get_addresses("cust-1")
        assert addresses == []
        assert "Authorization" in mock_post.call_args[1]["headers"]
        assert mock_post.call_args[1]["headers"]["Authorization"] == "Bearer valid_jwt"


@pytest.mark.asyncio
async def test_swiggy_adapter_auth_401_expired() -> None:
    """HTTP 401 Unauthorized maps to ProviderAuthError."""
    adapter = SwiggyMCPAdapter(auth_token="expired_token")
    mock_resp = httpx.Response(status_code=401, request=httpx.Request("POST", adapter.base_url))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ProviderAuthError):
            await adapter.get_addresses("cust-1")


@pytest.mark.asyncio
async def test_swiggy_adapter_auth_419_revoked() -> None:
    """HTTP 419 Session Revoked maps to ProviderSessionRevokedError."""
    adapter = SwiggyMCPAdapter(auth_token="revoked_token")
    mock_resp = httpx.Response(status_code=419, request=httpx.Request("POST", adapter.base_url))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ProviderSessionRevokedError):
            await adapter.get_addresses("cust-1")


@pytest.mark.asyncio
async def test_swiggy_adapter_rpc_32001_auth_error() -> None:
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
# 3. Address Handling Contract (No Fake Fallbacks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_addresses_single_and_multiple() -> None:
    """Parses real Swiggy address format without injecting fake Mumbai or pincode defaults."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "addresses": [
                    {
                        "id": "addr-indiranagar-1",
                        "addressLine": "12th Main, HAL 2nd Stage, Indiranagar",
                        "phoneNumber": "9876543210",
                        "addressCategory": "Home",
                        "city": "Bengaluru",
                        "pincode": "560038",
                    },
                    {
                        "id": "addr-whitefield-2",
                        "addressLine": "EPIP Zone, Whitefield",
                        "phoneNumber": "9876543211",
                        "addressCategory": "Work",
                        "city": "Bengaluru",
                        "pincode": "560066",
                    },
                ],
                "pagination": {"page": 1, "pageSize": 10, "total": 2, "totalPages": 1, "hasMore": False},
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        addresses = await adapter.get_addresses("cust-1")
        assert len(addresses) == 2
        assert addresses[0].id == "addr-indiranagar-1"
        assert addresses[0].city == "Bengaluru"
        assert addresses[0].postal_code == "560038"
        assert addresses[0].label == "Home"
        assert addresses[1].label == "Work"


@pytest.mark.asyncio
async def test_swiggy_adapter_addresses_empty_and_malformed() -> None:
    """Empty address list returns [] without crashing; malformed addresses are safely ignored."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "addresses": [
                    {"invalid": "no id field"},
                    {"id": "valid-1", "addressLine": "Connaught Place", "city": "Delhi"},
                ],
                "pagination": {"page": 1, "pageSize": 10, "total": 1, "totalPages": 1, "hasMore": False},
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        addresses = await adapter.get_addresses("cust-1")
        assert len(addresses) == 1
        assert addresses[0].id == "valid-1"
        assert addresses[0].city == "Delhi"


# ---------------------------------------------------------------------------
# 4. Search Products & Variations Contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_search_products_variations_and_pricing() -> None:
    """Parses real Swiggy Instamart variation price objects {mrp, offerPrice} and stock."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "nextOffset": "offset-2",
                "products": [
                    {
                        "productId": "prod-amul-milk",
                        "displayName": "Amul Taaza Homogenised Toned Milk",
                        "brand": "Amul",
                        "variations": [
                            {
                                "spinId": "spin-amul-500ml",
                                "skuId": "sku-101",
                                "displayName": "Amul Taaza 500 ml",
                                "quantityDescription": "500 ml",
                                "price": {"mrp": 35.0, "offerPrice": 34.0},
                                "isInStockAndAvailable": True,
                            },
                            {
                                "spinId": "spin-amul-1l",
                                "skuId": "sku-102",
                                "displayName": "Amul Taaza 1 L",
                                "quantityDescription": "1 L",
                                "price": {"mrp": 68.0, "offerPrice": 66.0},
                                "isInStockAndAvailable": False,
                            },
                        ],
                    }
                ],
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        products = await adapter.search_products("addr-1", "milk")
        assert len(products) == 1
        assert products[0].name == "Amul Taaza Homogenised Toned Milk"
        assert len(products[0].variants) == 2
        v1 = products[0].variants[0]
        assert v1.spin_id == "spin-amul-500ml"
        assert v1.price == 34.0
        assert v1.mrp == 35.0
        assert v1.in_stock is True
        assert v1.pack_size == "500 ml"

        v2 = products[0].variants[1]
        assert v2.in_stock is False


# ---------------------------------------------------------------------------
# 5. Cart Lifecycle & Error Taxonomy Contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_update_cart_selected_address() -> None:
    """update_cart sends selectedAddressId and item array per official Instamart schema."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "cartId": "cart-999",
                "selectedAddress": "addr-101",
                "cartTotalAmount": "102.0",
                "items": [
                    {
                        "spinId": "spin-amul-500ml",
                        "itemName": "Amul Taaza 500 ml",
                        "discountedFinalPrice": 34.0,
                        "mrp": 35.0,
                        "quantity": 3,
                        "isInStockAndAvailable": True,
                    }
                ],
                "billBreakdown": {
                    "lineItems": [
                        {"label": "Item Total", "value": "₹102.0"},
                        {"label": "Delivery Fee", "value": "₹0.0"},
                    ],
                    "toPay": {"label": "To Pay", "value": "₹102.0"},
                },
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        cart = await adapter.update_cart(
            items=[
                CartItemUpdate(
                    spin_id="spin-amul-500ml",
                    sku_id="sku-amul-500ml",
                    quantity=3,
                )
            ],
            cart_id="cart-999",
            address_id="addr-101",
        )
        assert cart.cart_id == "cart-999"
        assert cart.grand_total == 102.0
        assert len(cart.items) == 1
        assert cart.items[0].total_price == 102.0

        # Assert exact documented mutation arguments followed by canonical cart fetch.
        assert mock_post.call_count == 2
        assert mock_post.call_args_list[0].kwargs["json"]["params"]["arguments"] == {
            "selectedAddressId": "addr-101",
            "items": [
                {
                    "spinId": "spin-amul-500ml",
                    "skuId": "sku-amul-500ml",
                    "quantity": 3,
                }
            ],
        }
        assert mock_post.call_args_list[1].kwargs["json"]["params"]["arguments"] == {}


@pytest.mark.asyncio
async def test_swiggy_adapter_update_cart_requires_provider_address() -> None:
    adapter = SwiggyMCPAdapter()

    with pytest.raises(CommerceError, match="provider address ID"):
        await adapter.update_cart(
            items=[CartItemUpdate(spin_id="spin-amul-500ml", quantity=1)],
            cart_id="cart-999",
            address_id=None,
        )


def test_swiggy_adapter_drops_malformed_products_instead_of_fabricating() -> None:
    adapter = SwiggyMCPAdapter()

    products = adapter._parse_products(
        [
            {"variations": [{"price": 42}]},
            {
                "productId": "valid-product",
                "displayName": "Milk",
                "variations": [{"displayName": "Milk", "price": 42}],
            },
        ]
    )

    assert products == []


def test_swiggy_adapter_drops_malformed_cart_items_instead_of_fabricating() -> None:
    adapter = SwiggyMCPAdapter()

    cart = adapter._build_commerce_cart(
        {"cartId": "cart-1", "items": [{"quantity": 1, "price": 42}]}
    )

    assert cart.items == []


@pytest.mark.asyncio
async def test_swiggy_adapter_envelope_errors() -> None:
    """Envelope errors properly map to domain taxonomy."""
    adapter = SwiggyMCPAdapter()

    # OOS
    resp_oos = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Selected item is out of stock in dark store"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_oos
        with pytest.raises(ItemOutOfStockError):
            await adapter.get_cart("cart-1")

    # Unserviceable
    resp_srv = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Address not serviceable by any dark store"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_srv
        with pytest.raises(AddressNotServiceableError):
            await adapter.get_cart("cart-1")

    # Min order
    resp_min = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Minimum order not met for checkout"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_min
        with pytest.raises(MinOrderNotMetError):
            await adapter.get_cart("cart-1")

    # Cart expired
    resp_exp = httpx.Response(
        status_code=200,
        json={"success": False, "error": {"message": "Cart session has expired"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_exp
        with pytest.raises(CartExpiredError):
            await adapter.get_cart("cart-1")


# ---------------------------------------------------------------------------
# 6. Checkout & Non-Idempotent Failure Recovery Contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_requires_explicit_confirmation() -> None:
    """checkout() must strictly reject execution if explicit_confirmation is False."""
    adapter = SwiggyMCPAdapter()
    with pytest.raises(UnconfirmedCheckoutError):
        await adapter.checkout(cart_id="swiggy-cart-1", explicit_confirmation=False)


@pytest.mark.asyncio
async def test_swiggy_adapter_maps_exact_upi_intent_choice() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={"success": True, "data": {"orderId": "order-1", "status": "CONFIRMED"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        await adapter.checkout(
            cart_id="cart-1",
            payment_method="UPI",
            payment_option_id="google-pay-provider-id",
            payment_option_kind="intent",
            explicit_confirmation=True,
            address_id="addr-1",
        )

    assert post.call_args.kwargs["json"]["params"]["arguments"] == {
        "addressId": "addr-1",
        "paymentMethod": "UPI",
        "intentApp": "google-pay-provider-id",
    }


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("UNSUCCESSFUL", "PAYMENT_FAILED"),
        ("UNPAID", "PAYMENT_FAILED"),
        ("PAID", "PAYMENT_CONFIRMED"),
    ],
)
def test_swiggy_payment_status_normalization_does_not_invert_negatives(
    raw_status: str,
    expected: str,
) -> None:
    assert SwiggyMCPAdapter._normalize_payment_status(raw_status) == expected


def test_swiggy_existing_order_status_preserves_out_for_delivery() -> None:
    assert (
        SwiggyMCPAdapter._normalize_existing_order_status("OUT_FOR_DELIVERY")
        == "OUT_FOR_DELIVERY"
    )


def test_swiggy_order_status_does_not_treat_unsuccessful_as_success() -> None:
    assert SwiggyMCPAdapter._normalize_order_status(
        "UNSUCCESSFUL",
        order_count=1,
        success_count=0,
        failure_count=0,
        all_succeeded=False,
    ) == "FAILED"


@pytest.mark.parametrize("raw_status", ["UNCONFIRMED", "NOT_PLACED", "SUCCESS_LATER"])
def test_swiggy_order_status_unknown_values_never_match_success_substrings(
    raw_status: str,
) -> None:
    assert SwiggyMCPAdapter._normalize_order_status(
        raw_status,
        order_count=1,
        success_count=0,
        failure_count=0,
        all_succeeded=False,
    ) == "ORDER_STATE_UNKNOWN"


@pytest.mark.asyncio
async def test_swiggy_checkout_without_order_id_is_unknown() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={"success": True, "data": {"status": "CONFIRMED"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        result = await adapter.checkout(
            cart_id="cart-1",
            payment_method="COD",
            explicit_confirmation=True,
            address_id="addr-1",
        )

    assert result.order_id is None
    assert result.status == "ORDER_STATE_UNKNOWN"


@pytest.mark.asyncio
async def test_swiggy_failed_child_overrides_contradictory_top_level_success() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "status": "CONFIRMED",
                "orderId": "parent",
                "orders": [{"orderId": "child", "status": "FAILED", "success": "false"}],
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        result = await adapter.checkout(
            cart_id="cart",
            payment_method="COD",
            explicit_confirmation=True,
            address_id="addr",
        )

    assert result.status == "FAILED"
    assert result.orders[0].success is False


@pytest.mark.asyncio
async def test_swiggy_unknown_child_prevents_complete_success() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "status": "CONFIRMED",
                "orderId": "parent",
                "orders": [
                    {"orderId": "A", "status": "CONFIRMED"},
                    {"orderId": "B", "status": "UNRECOGNIZED_PROVIDER_STATE"},
                ],
                "allSucceeded": True,
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        result = await adapter.checkout(
            cart_id="cart",
            payment_method="COD",
            explicit_confirmation=True,
            address_id="addr",
        )

    assert result.status == "PARTIAL_ORDER"
    assert result.success_count == 1
    assert result.all_succeeded is False


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_multi_store_and_upi_pending() -> None:
    """Handles multi-store orders and UPI PENDING_PAYMENT flows."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "orderId": "SWIGGY-MULTI-101",
                "message": "Complete payment securely on Swiggy.",
                "status": "PENDING_PAYMENT",
                "paymentMethod": "UPI",
                "paasId": "paas-token-xyz",
                "bridgeUrl": "https://mcp.swiggy.com/pay/bridge-123",
                "cartTotal": 540.0,
                "orders": [
                    {"orderId": "SWIGGY-STORE-A", "status": "PENDING_PAYMENT"},
                    {"orderId": "SWIGGY-STORE-B", "status": "PENDING_PAYMENT"},
                ],
                "orderCount": 2,
                "allSucceeded": True,
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await adapter.checkout(
            cart_id="cart-multi",
            payment_method="UPI",
            payment_option_id="google-pay-provider-id",
            payment_option_kind="intent",
            explicit_confirmation=True,
            address_id="addr-1",
        )
        assert result.order_id == "SWIGGY-MULTI-101"
        assert result.status == "PAYMENT_PENDING"
        assert result.paas_id == "paas-token-xyz"
        assert result.bridge_url == "https://mcp.swiggy.com/pay/bridge-123"
        assert result.provider_message == "Complete payment securely on Swiggy."
        assert result.order_count == 2
        assert len(result.orders) == 2


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_timeout_does_not_accept_unrelated_order() -> None:
    """An uncorrelated historical order cannot prove that this checkout succeeded."""
    adapter = SwiggyMCPAdapter()

    # First call (checkout) raises TimeoutException
    # Second call (get_orders probe) returns order that was placed upstream
    mock_probe_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "orders": [
                    {"orderId": "SWIGGY-RECOVERED-999", "orderTotal": 350.0}
                ]
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.ReadTimeout("Checkout upstream timeout"),
            mock_probe_resp,
        ]

        with pytest.raises(OrderStateUnknownError):
            await adapter.checkout(
                cart_id="cart-test",
                payment_method="UPI",
                payment_option_id="google-pay-provider-id",
                payment_option_kind="intent",
                explicit_confirmation=True,
                address_id="addr-1",
            )


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_unrecovered_timeout_raises_order_state_unknown() -> None:
    """When checkout times out and order cannot be confirmed upstream, raises OrderStateUnknownError."""
    adapter = SwiggyMCPAdapter()

    mock_probe_resp = httpx.Response(
        status_code=200,
        json={"success": True, "data": {"orders": []}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.ReadTimeout("Checkout upstream timeout"),
            mock_probe_resp,
        ]

        with pytest.raises(OrderStateUnknownError):
            await adapter.checkout(
                cart_id="cart-test",
                payment_method="UPI",
                payment_option_id="google-pay-provider-id",
                payment_option_kind="intent",
                explicit_confirmation=True,
                address_id="addr-1",
            )


# ---------------------------------------------------------------------------
# 7. Order Tracking Contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_adapter_track_order() -> None:
    """Parses real Swiggy track_order schema with status mapping and ETA."""
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "orderId": "SWIGGY-OD-1",
                "status": {"statusMessage": "Rider is out for delivery", "etaMinutes": 12},
                "pollingIntervalSeconds": 15,
                "storeInfo": {"name": "Swiggy Instamart Indiranagar"},
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        tracking = await adapter.track_order("SWIGGY-OD-1", lat=12.9716, lng=77.5946)
        assert tracking.order_id == "SWIGGY-OD-1"
        assert tracking.status == "OUT_FOR_DELIVERY"
        assert tracking.eta_minutes == 12
        assert tracking.polling_interval_seconds == 15
        assert tracking.store_name == "Swiggy Instamart Indiranagar"


@pytest.mark.asyncio
async def test_swiggy_adapter_track_order_preserves_rich_provider_facts() -> None:
    adapter = SwiggyMCPAdapter()
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "orderId": "SWIGGY-OD-RICH",
                "orderTitle": "Instamart order",
                "orderSubtitle": "Arriving soon",
                "status": {
                    "statusMessage": "Rider is out for delivery",
                    "subStatusMessage": "Your order is nearby",
                    "etaMinutes": 7,
                    "etaText": "7 minutes",
                },
                "storeInfo": {
                    "name": "Swiggy Instamart Indiranagar",
                    "address": "100 Feet Road, Bengaluru",
                },
                "deliveryInfo": {
                    "addressLabel": "Home",
                    "fullAddress": "12th Main, Bengaluru",
                },
                "items": [{"name": "Milk", "quantity": 2, "price": "₹132"}],
                "itemCount": 2,
                "placedAt": "2026-09-09T10:00:00Z",
                "paymentInfo": {"message": "Paid via UPI", "amount": "₹132"},
                "mapInfo": {
                    "storeLocation": {"latitude": 12.9716, "longitude": 77.5946},
                    "storeAnnotation": "Store",
                    "deliveryLocation": {"latitude": 12.9816, "longitude": 77.6046},
                    "deliveryAnnotation": "Home",
                    "riderLocation": {"latitude": 12.9766, "longitude": 77.5996},
                },
                "pollingIntervalSeconds": 15,
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        tracking = await adapter.track_order(
            "SWIGGY-OD-RICH", lat=12.9816, lng=77.6046
        )

    arguments = mock_post.call_args.kwargs["json"]["params"]["arguments"]
    assert arguments == {
        "orderId": "SWIGGY-OD-RICH",
        "lat": 12.9816,
        "lng": 77.6046,
    }
    assert tracking.status == "OUT_FOR_DELIVERY"
    assert tracking.raw_status == "Rider is out for delivery"
    assert tracking.sub_status_message == "Your order is nearby"
    assert tracking.order_title == "Instamart order"
    assert tracking.order_subtitle == "Arriving soon"
    assert tracking.store_name == "Swiggy Instamart Indiranagar"
    assert tracking.store_address == "100 Feet Road, Bengaluru"
    assert tracking.delivery_address_label == "Home"
    assert tracking.delivery_address == "12th Main, Bengaluru"
    assert tracking.items[0].name == "Milk"
    assert tracking.items[0].quantity == 2
    assert tracking.items[0].price == "₹132"
    assert tracking.item_count == 2
    assert tracking.placed_at == "2026-09-09T10:00:00Z"
    assert tracking.payment_message == "Paid via UPI"
    assert tracking.payment_amount == "₹132"
    assert tracking.store_location.latitude == 12.9716
    assert tracking.delivery_location.longitude == 77.6046
    assert tracking.rider_location.latitude == 12.9766
    assert tracking.store_annotation == "Store"
    assert tracking.delivery_annotation == "Home"
    assert tracking.polling_interval_seconds == 15


# ---------------------------------------------------------------------------
# 8. Address Selection Workflow in Orchestrator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swiggy_orchestrator_multi_address_prompts_user() -> None:
    """When Swiggy account has multiple addresses and none selected, prompt user to choose."""
    from backend.intent.orchestrator import GrocerOrchestrator
    from backend.intent.session import ConversationState

    adapter = SwiggyMCPAdapter()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter)

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "addresses": [
                    {"id": "addr-home", "addressCategory": "Home", "addressLine": "12th Main Indiranagar"},
                    {"id": "addr-office", "addressCategory": "Work", "addressLine": "EPIP Zone Whitefield"},
                ],
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await orchestrator.handle_turn(
            session_id="session-multi-addr",
            customer_id="cust-multi-1",
            message="get milk and bread",
        )
        assert result.conversation_state == ConversationState.NEEDS_DECISION
        assert "Which address would you like to use" in result.user_message
        assert "Home" in result.user_message
        assert "Work" in result.user_message
        assert "NEEDS_ADDRESS_SELECTION" in result.events


@pytest.mark.asyncio
async def test_swiggy_orchestrator_address_selection_persists() -> None:
    """When user selects address by number/label, session records it and proceeds."""
    from backend.intent.orchestrator import GrocerOrchestrator

    adapter = SwiggyMCPAdapter()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter)

    mock_addr_resp = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "addresses": [
                    {"id": "addr-home", "addressCategory": "Home", "addressLine": "12th Main Indiranagar"},
                    {"id": "addr-office", "addressCategory": "Work", "addressLine": "EPIP Zone Whitefield"},
                ],
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    # The address choice is valid only after the provider's offered set is stored.
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_addr_resp
        prompted = await orchestrator.handle_turn(
            session_id="session-multi-addr-2",
            customer_id="cust-multi-2",
            message="get milk",
        )
        assert "NEEDS_ADDRESS_SELECTION" in prompted.events

        result = await orchestrator.handle_turn(
            session_id="session-multi-addr-2",
            customer_id="cust-multi-2",
            message="Home",
        )
        assert "ADDRESS_SELECTED id=addr-home" in result.events


@pytest.mark.asyncio
async def test_swiggy_orchestrator_no_address_fails_cleanly() -> None:
    """When Swiggy account has 0 addresses, inform user clearly."""
    from backend.intent.orchestrator import GrocerOrchestrator
    from backend.intent.session import ConversationState

    adapter = SwiggyMCPAdapter()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter)

    mock_empty_resp = httpx.Response(
        status_code=200,
        json={"success": True, "data": {"addresses": []}},
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_empty_resp
        result = await orchestrator.handle_turn(
            session_id="session-zero-addr",
            customer_id="cust-zero",
            message="get milk",
        )
        assert result.conversation_state == ConversationState.FAILED
        assert "No delivery address found" in result.user_message
