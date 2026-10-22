"""Unit tests for Layer 1: Core Plumbing & Swiggy MCP compliance."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.product_policy import is_restricted_medical_product
from backend.agent.tools import SwiggyAgentTools
from backend.integrations.commerce.cart_parsers import build_commerce_cart
from backend.integrations.commerce.catalog_parsers import parse_coupons, parse_swiggy_products
from backend.integrations.commerce.exceptions import (
    CartChangedError,
    CommerceError,
    DuplicateOrderError,
    ItemOutOfStockError,
    ProviderAuthError,
    ProviderInternalError,
    ProviderRateLimitedError,
    UnconfirmedCheckoutError,
)
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    AddressRecommendation,
    CartItem,
    CartItemUpdate,
    CommerceOrderResult,
    Coupon,
    CouponApplyResult,
    DeliveryAddress,
    DeliveryTrackingStatus,
    ErrorReportResult,
)
from backend.integrations.commerce.order_parsers import (
    build_checkout_order_result,
    normalize_order_status,
    parse_delivery_addresses,
    parse_delivery_tracking_response,
)
from backend.integrations.commerce.port import SWIGGY_CUSTOMER_CARE_PHONE
from backend.integrations.commerce.swiggy_client import SwiggyMcpClient


def test_swiggy_customer_care_phone_constant():
    """Verify Swiggy cancellation/care phone number matches official spec."""
    assert SWIGGY_CUSTOMER_CARE_PHONE == "080-67466729"


def test_order_status_normalization():
    """Verify clean order status normalization without split-order dependencies."""
    assert normalize_order_status("CONFIRMED") == "ORDER_PLACED"
    assert normalize_order_status("PLACED") == "ORDER_PLACED"
    assert normalize_order_status("ORDER_PLACED") == "ORDER_PLACED"
    assert normalize_order_status("FAILED") == "FAILED"
    assert normalize_order_status("CANCELLED") == "FAILED"
    assert normalize_order_status("PENDING_PAYMENT") == "PAYMENT_PENDING"
    assert normalize_order_status("UNKNOWN_STRING") == "ORDER_STATE_UNKNOWN"
    assert normalize_order_status(None) == "ORDER_STATE_UNKNOWN"


def test_tracking_status_exact_tokens_no_substring_bug():
    """Verify tracking parser does not falsely classify 'OUT OF STOCK' as 'OUT_FOR_DELIVERY'."""
    data_out_for_del = {
        "orderId": "OD-12345",
        "status": {"statusMessage": "OUT_FOR_DELIVERY", "etaMinutes": 10},
        "deliveryInfo": {"riderName": "Suresh", "riderPhone": "+919800011111"},
    }
    parsed = parse_delivery_tracking_response(data_out_for_del, "OD-12345")
    assert parsed.status == "OUT_FOR_DELIVERY"
    assert parsed.eta_minutes == 10
    assert parsed.driver_name == "Suresh"
    assert parsed.driver_phone == "+919800011111"

    # Status message containing OUT OF STOCK should NOT be classified as OUT_FOR_DELIVERY
    data_oos = {
        "orderId": "OD-12346",
        "status": {"statusMessage": "ITEM OUT OF STOCK"},
    }
    parsed_oos = parse_delivery_tracking_response(data_oos, "OD-12346")
    assert parsed_oos.status != "OUT_FOR_DELIVERY"
    assert parsed_oos.status == "UNKNOWN"


def test_parse_delivery_addresses_coordinates():
    """Verify parse_delivery_addresses parses lat and lng properly."""
    raw = [
        {
            "id": "addr-1",
            "addressLine": "Flat 101, Palm Beach",
            "area": "Bandra West",
            "city": "Mumbai",
            "pincode": "400050",
            "latitude": 19.0596,
            "longitude": 72.8295,
            "serviceable": True,
        }
    ]
    addresses = parse_delivery_addresses(raw)
    assert len(addresses) == 1
    assert addresses[0].id == "addr-1"
    assert addresses[0].latitude == 19.0596
    assert addresses[0].longitude == 72.8295
    assert addresses[0].is_serviceable is True


def test_build_checkout_order_result_dynamic_qr():
    """Verify build_checkout_order_result extracts qr_code_url and sets is_qr_flow."""
    data = {
        "orderId": "OD-9999",
        "status": "PENDING_PAYMENT",
        "cartTotal": 299.0,
        "paasId": "paas_1234",
        "qrCodeUrl": "https://instamart.swiggy.com/pay/qr/paas_1234",
        "bridgeUrl": "https://instamart.swiggy.com/pay/bridge/paas_1234",
        "pollingIntervalInMs": 15000,
        "maxTimeToPollForInMs": 600000,
    }
    res = build_checkout_order_result(data, {}, "cart-1", "addr-1", "UPI")
    assert res.order_id == "OD-9999"
    assert res.status == "PAYMENT_PENDING"
    assert res.qr_code_url == "https://instamart.swiggy.com/pay/qr/paas_1234"
    assert res.bridge_url == "https://instamart.swiggy.com/pay/bridge/paas_1234"
    assert res.is_qr_flow is True


def test_catalog_parsers_flat_staples():
    """Verify parse_swiggy_products parses flat staple items without nested variations."""
    raw_staple = [
        {
            "id": "prod-salt",
            "name": "Tata Salt 1kg",
            "spinId": "SPIN-SALT-1KG",
            "skuId": "SKU-SALT-1KG",
            "price": 28.0,
            "mrp": 30.0,
            "inStock": True,
            "packSize": "1 kg",
            "isVeg": True,
        }
    ]
    prods = parse_swiggy_products(raw_staple)
    assert len(prods) == 1
    assert prods[0].product_id == "prod-salt"
    assert len(prods[0].variants) == 1
    assert prods[0].variants[0].spin_id == "SPIN-SALT-1KG"
    assert prods[0].variants[0].price == 28.0
    assert prods[0].variants[0].in_stock is True


def test_parse_coupons():
    """Verify parse_coupons parses coupon list accurately."""
    raw = {
        "coupons": [
            {
                "code": "INSTA50",
                "description": "₹50 off on ₹299+",
                "discountAmount": 50.0,
                "minCartValue": 299.0,
                "isApplicable": True,
            }
        ]
    }
    coupons = parse_coupons(raw)
    assert len(coupons) == 1
    assert coupons[0].code == "INSTA50"
    assert coupons[0].discount_amount == 50.0
    assert coupons[0].min_cart_value == 299.0
    assert coupons[0].is_applicable is True


def test_cart_parsers_fallback_cart_id():
    """Verify build_commerce_cart falls back to provided cart_id if provider omits it."""
    data = {"items": [], "grandTotal": 0.0}
    cart = build_commerce_cart(data, cart_id="fallback-cart-99")
    assert cart.cart_id == "fallback-cart-99"


def test_exceptions_with_diagnostics():
    """Verify CommerceError retains report_id and report_hint."""
    exc = CommerceError("Service degraded", report_id="ERR-12345", report_hint="Run report_error")
    assert exc.report_id == "ERR-12345"
    assert exc.report_hint == "Run report_error"

    p_exc = ProviderInternalError("Server crash", report_id="ERR-999")
    assert p_exc.code == "PROVIDER_INTERNAL_ERROR"
    assert p_exc.report_id == "ERR-999"


@pytest.mark.asyncio
async def test_swiggy_client_rpc_error_mapping():
    """Verify SwiggyMcpClient classifies JSON-RPC error codes -32001, -32000, -32603."""
    client = SwiggyMcpClient(base_url="https://mock.local", auth_token="mock-token")

    with pytest.raises(ProviderAuthError):
        client.parse_error_if_failed({"error": {"code": -32001, "message": "unauthenticated"}})

    with pytest.raises(DuplicateOrderError):
        client.parse_error_if_failed({"error": {"message": "duplicate order detected"}})

    with pytest.raises(CartChangedError):
        client.parse_error_if_failed({"error": {"message": "cart changed during checkout"}})


@pytest.mark.asyncio
async def test_mock_adapter_6_new_tools():
    """Verify MockCommerceAdapter implements all 6 new commerce tools."""
    adapter = MockCommerceAdapter()

    # 1. create_address
    addr = await adapter.create_address(
        customer_id="cust-1",
        label="Office",
        street="102 Corporate Park",
        area="BKC",
        city="Mumbai",
        postal_code="400051",
    )
    assert addr.label == "Office"
    assert addr.city == "Mumbai"

    # 2. delete_address
    del_ok = await adapter.delete_address("addr-1")
    assert del_ok is True

    # 3. list_coupons
    coupons = await adapter.list_coupons()
    assert len(coupons) >= 1
    assert coupons[0].code == "INSTA50"

    # 4. apply_coupon
    applied = await adapter.apply_coupon("INSTA50")
    assert applied.applied is True
    assert applied.discount_amount == 50.0

    # 5. recommend_address
    rec = await adapter.recommend_address(19.0596, 72.8295)
    assert rec.recommended_address_id is not None
    assert rec.confidence == 0.95

    # 6. report_error
    rep = await adapter.report_error("ERR-1001", {"action": "checkout"})
    assert rep.report_id == "ERR-1001"
    assert rep.status == "received"


@pytest.mark.asyncio
async def test_execute_gated_checkout_dynamic_qr_unblocked():
    """Verify execute_gated_checkout does not block dynamic UPI QR and sets smart polling intervals."""
    adapter = MockCommerceAdapter()
    customer_id = "cust-qr-test"
    with adapter.customer_scope(customer_id):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-BREAD-400G", name="Whole Wheat Bread 400g", pack_size="400 g", unit_price=50.0, quantity=3, total_price=150.0)
        ])
        cart = await adapter.get_cart()

    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id="addr-bandra-1",
        payment_method="UPI",
        payment_option_kind="qr",
        is_user_confirmed=True,
    )

    assert res["success"] is True
    assert res["status"] == "PAYMENT_PENDING"
    assert res["is_qr_flow"] is True
    assert res["qr_code_url"] is not None
    assert "https://" in res["qr_code_url"]
    assert res["polling_interval_ms"] == 15000
    assert res["max_time_to_poll_ms"] == 600000


@pytest.mark.asyncio
async def test_tools_track_order_without_lat_lng():
    """Verify tools.track_order works cleanly with only order_id."""
    adapter = MockCommerceAdapter()
    order_id = "OD-TRACK-1"
    adapter._orders[order_id] = CommerceOrderResult(
        order_id=order_id,
        status="ORDER_PLACED",
        grand_total=100.0,
    )
    tools = SwiggyAgentTools(commerce=adapter, gemini_client=MagicMock())
    track_res = await tools.track_order(order_id)
    assert track_res["success"] is True
    assert track_res["order_id"] == order_id
    assert track_res["status"] == "PACKING"
    assert track_res["driver_name"] == "Ramesh Kamble"


def test_product_policy_staples_and_first_aid():
    """Verify Instamart OTC staples are allowed while prescription drugs remain restricted."""
    # OTC first aid & staples allowed
    assert is_restricted_medical_product("Band-Aid Plastic 10s") is False
    assert is_restricted_medical_product("Dettol Antiseptic Liquid 250ml") is False
    assert is_restricted_medical_product("Eno Regular 100g") is False
    assert is_restricted_medical_product("Pudina Hara Pearls") is False
    assert is_restricted_medical_product("Digene Gel 200ml") is False
    assert is_restricted_medical_product("Moov Pain Relief Spray") is False
    assert is_restricted_medical_product("Amrutanjan Balm") is False

    # Prescription medicines restricted
    assert is_restricted_medical_product("Dolo 650 Tablet") is True
    assert is_restricted_medical_product("Paracetamol 500mg") is True
    assert is_restricted_medical_product("Crocin 650 Advance") is True
    assert is_restricted_medical_product("Amoxicillin Antibiotic") is True
    assert is_restricted_medical_product("Benadryl Cough Syrup") is True
