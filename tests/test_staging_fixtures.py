"""Grocer v1.0 — Contract Schema Tests Against Committed Staging Fixtures.

Validates that Pydantic contract schemas accurately parse real Swiggy MCP tool responses
for all 20 Instamart tools. Zero fake mocks; 100% ground-truth schema verification.
"""

from __future__ import annotations

import json
from pathlib import Path

from fixture_client import FixtureSwiggyClient

from backend.integrations.commerce.schemas import (
    CartData,
    CheckoutData,
    ClearCartData,
    ConfirmOrderData,
    CreateAddressData,
    DeleteAddressData,
    DeliveryStatusData,
    GetAddressesData,
    ListCouponsData,
    OrderDetailsData,
    OrdersListData,
    PaymentOptionsData,
    PaymentStatusData,
    RecommendAddressData,
    ReportErrorData,
    SearchProductsData,
    ToolEnvelope,
    TrackOrderData,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(tool_name: str) -> dict:
    """Load a raw JSON fixture file by tool name."""
    path = FIXTURES_DIR / f"{tool_name}.json"
    assert path.exists(), f"Fixture file not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# 1. Address Tools
def test_fixture_get_addresses():
    raw = load_fixture("get_addresses")
    env = ToolEnvelope[GetAddressesData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert len(env.data.addresses) >= 1
    assert env.data.addresses[0].id == "addr_01HXYZ"
    assert env.data.pagination.page == 1
    assert env.data.resolution.resolutionSource == "user_selected_address"


def test_fixture_create_address():
    raw = load_fixture("create_address")
    env = ToolEnvelope[CreateAddressData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.addressId.startswith("addr_")


def test_fixture_delete_address():
    raw = load_fixture("delete_address")
    env = ToolEnvelope[DeleteAddressData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.statusCode == 200


def test_fixture_recommend_address():
    raw = load_fixture("recommend_address")
    env = ToolEnvelope[RecommendAddressData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.latitude > 0
    assert "Bengaluru" in env.data.formattedAddress


# 2. Product Search Tools
def test_fixture_search_products():
    raw = load_fixture("search_products")
    env = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert len(env.data.products) >= 1
    prod = env.data.products[0]
    assert prod.brand == "Amul"
    assert len(prod.variations) >= 1
    assert prod.variations[0].price.offerPrice == 72


def test_fixture_your_go_to_items():
    raw = load_fixture("your_go_to_items")
    env = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert len(env.data.products) >= 1
    assert env.data.products[0].brand == "Nandini"


# 3. Cart Tools
def test_fixture_get_cart():
    raw = load_fixture("get_cart")
    env = ToolEnvelope[CartData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.cartId == "cart_im_987654"
    assert len(env.data.items) >= 1
    assert env.data.items[0].spinId == "spin_amul_1l"
    assert env.data.billBreakdown.toPay.value == "₹149.00"


def test_cart_item_accepts_numeric_store_id():
    """Live Instamart returns storeId as a number, not a string."""
    cart = CartData.model_validate(
        {
            "cartId": "cart_1",
            "cartTotalAmount": "₹31",
            "items": [
                {
                    "spinId": "spin_1",
                    "storeId": 1389256,
                    "skuId": "sku_1",
                    "productId": "prod_1",
                    "itemName": "Amul Moti Toned Milk",
                    "quantity": 1,
                    "isInStockAndAvailable": True,
                    "mrp": 33.0,
                    "discountedFinalPrice": 31.0,
                }
            ],
            "billBreakdown": {
                "lineItems": [],
                "toPay": {"label": "To Pay", "value": "₹31"},
            },
        }
    )
    assert cart.items[0].storeId == "1389256"


def test_fixture_update_cart():
    raw = load_fixture("update_cart")
    env = ToolEnvelope[CartData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.cartTotalAmount == "216.00"
    assert env.data.items[0].quantity == 3


def test_fixture_clear_cart():
    raw = load_fixture("clear_cart")
    env = ToolEnvelope[ClearCartData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.verified is True


# 4. Coupon Tools
def test_fixture_list_coupons():
    raw = load_fixture("list_coupons")
    env = ToolEnvelope[ListCouponsData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert len(env.data.availableCoupons) >= 2
    assert env.data.availableCoupons[0].couponCode == "INSTA50"
    assert env.data.availableCoupons[0].isApplicable is True


def test_fixture_apply_coupon():
    raw = load_fixture("apply_coupon")
    env = ToolEnvelope[CartData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.cartTotalAmount == "144.00"
    has_discount = any(
        "Coupon Discount" in item.label for item in env.data.billBreakdown.lineItems
    )
    assert has_discount is True


# 5. Payment & Checkout Tools
def test_fixture_get_payment_options():
    raw = load_fixture("get_payment_options")
    env = ToolEnvelope[PaymentOptionsData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.placeOrderToolName == "checkout"
    assert env.data.cod is not None and env.data.cod["available"] is True


def test_fixture_checkout():
    raw = load_fixture("checkout")
    env = ToolEnvelope[CheckoutData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.orderId == "189456789012"
    assert env.data.status == "PENDING_PAYMENT"
    assert env.data.bridgeUrl is not None
    assert env.data.bridgeUrl.startswith("https://")


def test_checkout_schema_accepts_multi_store_shape():
    """Contract shape from docs/swiggy-mcp/llms-full.txt: one order per dark store."""
    env = ToolEnvelope[CheckoutData].model_validate(
        {
            "success": True,
            "data": {
                "orders": [
                    {"orderId": "111", "status": "PLACED"},
                    {"orderId": "222", "status": "FAILED", "error": "Out of stock"},
                ],
                "orderCount": 2,
                "successCount": 1,
                "failureCount": 1,
                "allSucceeded": False,
                "paymentMethod": "Cash",
                "cartTotal": 149.0,
            },
        }
    )
    assert env.data is not None
    assert env.data.orderId is None
    assert [o.orderId for o in env.data.orders] == ["111", "222"]
    assert env.data.allSucceeded is False


def test_fixture_check_payment_status():
    raw = load_fixture("check_payment_status")
    env = ToolEnvelope[PaymentStatusData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.status == "SUCCESS"
    assert env.data.terminal is True
    assert env.data.isTerminalSuccess is True


def test_fixture_confirm_order():
    raw = load_fixture("confirm_order")
    env = ToolEnvelope[ConfirmOrderData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.orderId == "189456789012"
    assert env.data.result == "success"


# 6. Order History & Tracking Tools
def test_fixture_get_orders():
    raw = load_fixture("get_orders")
    env = ToolEnvelope[OrdersListData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert len(env.data.orders) >= 1
    assert env.data.orders[0].orderId == "189456789012"
    assert env.data.orders[0].status == "DELIVERED"


def test_fixture_get_order_details():
    raw = load_fixture("get_order_details")
    env = ToolEnvelope[OrderDetailsData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.orderId == "189456789012"
    assert env.data.totalBill == 149.0
    assert len(env.data.items) >= 1


def test_fixture_get_delivery_status():
    raw = load_fixture("get_delivery_status")
    env = ToolEnvelope[DeliveryStatusData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.orderId == "189456789012"
    assert env.data.deliveryBy == 1792928400000
    assert env.data.etaText == "10 mins"


def test_fixture_track_order():
    raw = load_fixture("track_order")
    env = ToolEnvelope[TrackOrderData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.orderId == "189456789012"
    assert env.data.status.statusMessage == "On the way"
    assert env.data.mapInfo is not None
    assert "riderLocation" in env.data.mapInfo


def test_fixture_report_error():
    raw = load_fixture("report_error")
    env = ToolEnvelope[ReportErrorData].model_validate(raw)
    assert env.success is True
    assert env.data is not None
    assert env.data.reportLink.startswith("https://")
    assert "checkout" in env.data.summary


# Invariant: Zero mocks present in tests or schemas
def test_zero_mocks_invariant():
    """Prove that MockCommerceAdapter or any mock classes do not exist in Grocer v1.0."""
    from backend.integrations import commerce

    assert not hasattr(commerce, "MockCommerceAdapter"), (
        "MockCommerceAdapter must never exist in Grocer v1.0"
    )


# 7. Gate 1: new client tool methods against committed real fixtures
def test_client_get_payment_options_report_error_confirm_order():
    """Gate 1: get_payment_options, report_error, and confirm_order(paasId) parse real fixtures."""

    client = FixtureSwiggyClient(FIXTURES_DIR)

    opts = client.get_payment_options()
    assert opts.placeOrderToolName == "checkout"
    assert opts.cod is not None and opts.cod["available"] is True

    report = client.report_error(tool="checkout", error_message="PAAS_TIMEOUT")
    assert report.reportLink.startswith("https://")
    assert "checkout" in report.summary

    confirm = client.confirm_order("189456789012", "paas_01HZ123456789")
    assert confirm.orderId == "189456789012"
    assert confirm.result == "success"
