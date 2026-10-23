"""Tests for Customer Advocate Engine, Auto-Coupons, Delivery Thresholds, and 1-Tap Mobile UPI."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.agent.engine import process_checkout_outcome, order_message
from backend.agent.customer_advocate import CustomerAdvocate
from backend.agent.formatters import format_cart_receipt
from backend.agent.tools import SwiggyAgentTools
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
    Coupon,
    CouponApplyResult,
)


@pytest.mark.asyncio
async def test_customer_advocate_auto_applies_best_coupon():
    """Customer Advocate auto-selects and applies highest discount coupon meeting min cart value."""
    commerce = MagicMock()
    cart = CommerceCart(
        cart_id="cart-adv-1",
        address_id="addr-1",
        items=[CartItem(spin_id="s1", sku_id="k1", name="Milk", pack_size="1L", quantity=10, unit_price=40.0, total_price=400.0)],
        item_total=400.0,
        grand_total=435.0,
        delivery_fee=35.0,
        is_serviceable=True,
    )
    coupons = [
        Coupon(code="SAVE20", description="₹20 off", discount_amount=20.0, min_cart_value=199.0, is_applicable=True),
        Coupon(code="SAVE50", description="₹50 off", discount_amount=50.0, min_cart_value=299.0, is_applicable=True),
        Coupon(code="SAVE100", description="₹100 off", discount_amount=100.0, min_cart_value=500.0, is_applicable=True),  # not met (400 < 500)
    ]
    commerce.list_coupons = AsyncMock(return_value=coupons)
    commerce.apply_coupon = AsyncMock(return_value=CouponApplyResult(applied=True, code="SAVE50", discount_amount=50.0))
    commerce.get_go_to_items = AsyncMock(return_value=[])

    advocate = CustomerAdvocate(commerce)
    opt = await advocate.optimize_cart(cart, address_id="addr-1")

    assert opt["coupon_applied"] is True
    assert opt["coupon_code"] == "SAVE50"
    assert opt["coupon_savings"] == 50.0
    assert opt["total_savings"] == 50.0
    assert cart.discount == 50.0
    assert cart.grand_total == 385.0
    commerce.apply_coupon.assert_called_once_with(code="SAVE50", cart_id="cart-adv-1")


@pytest.mark.asyncio
async def test_customer_advocate_delivery_fee_threshold_savings():
    """Customer Advocate identifies delta to free delivery and recommends real staples."""
    commerce = MagicMock()
    # Cart has ₹175 total, threshold is ₹199, delivery fee is ₹35. Adding ₹24 saves ₹35 (net gain ₹11).
    cart = CommerceCart(
        cart_id="cart-adv-2",
        address_id="addr-1",
        items=[CartItem(spin_id="s1", sku_id="k1", name="Apples", pack_size="500g", quantity=1, unit_price=175.0, total_price=175.0)],
        item_total=175.0,
        grand_total=210.0,
        delivery_fee=35.0,
        min_order_threshold=199.0,
        is_serviceable=True,
    )
    commerce.list_coupons = AsyncMock(return_value=[])
    commerce.get_go_to_items = AsyncMock(return_value=[
        CommerceProductItem(
            product_id="p-maggi",
            name="Maggi 2-Minute Noodles",
            brand="Nestle",
            category="Instant Noodles",
            variants=[ProductVariant(spin_id="sp-maggi", sku_id="sk-maggi", name="Maggi 2-Minute Noodles 70g", pack_size="70g", price=14.0, mrp=14.0, in_stock=True)],
        )
    ])

    advocate = CustomerAdvocate(commerce)
    opt = await advocate.optimize_cart(cart, address_id="addr-1")

    assert opt["delivery_savings_tip"] is not None
    assert "₹24" in opt["delivery_savings_tip"]
    assert "Maggi 2-Minute Noodles 70g" in opt["delivery_savings_tip"]
    assert len(opt["staple_suggestions"]) == 1


def test_format_cart_receipt_shows_advocate_badge():
    """Receipt includes customer advocate total savings badge and proactive tips."""
    cart = CommerceCart(
        cart_id="cart-1",
        address_id="addr-1",
        items=[CartItem(spin_id="s1", sku_id="k1", name="Milk", pack_size="500ml", quantity=1, unit_price=27.0, total_price=27.0)],
        item_total=27.0,
        grand_total=62.0,
        delivery_fee=35.0,
        is_serviceable=True,
    )
    advocate_info = {
        "total_savings": 50.0,
        "delivery_savings_tip": "Adding ₹25 more unlocks FREE delivery!",
    }
    receipt = format_cart_receipt(cart, delivery_location="Home", advocate_info=advocate_info)

    assert "🎉 *Total Saved:* ₹50" in receipt
    assert "💡 *Customer Advocate Tip:* Adding ₹25 more unlocks FREE delivery!" in receipt


def test_checkout_outcome_creates_mobile_upi_one_tap_action():
    """PAYMENT_PENDING outcome creates 1-tap mobile UPI interactive action."""
    checkout_res = {
        "success": True,
        "status": "PAYMENT_PENDING",
        "order_id": "ORD_12345",
        "grand_total": 250.0,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&pn=SwiggyInstamart&am=250.00&tr=ORD_12345&cu=INR",
    }
    state, text, actions, order_id, total, bridge = process_checkout_outcome(
        engine=None,
        customer_id="cust-1",
        checkout_executed=True,
        checkout_result=checkout_res,
        last_cart_receipt=None,
        current_cart=None,
        addr_lbl="Home",
        final_text="",
        actions=[],
        pending_request_needs_retry=False,
    )
    assert state == "AWAITING_PAYMENT"
    assert len(actions) == 1
    assert actions[0].action_type == "url"
    assert "upi://pay" in actions[0].url
    assert "ORD_12345" in text
    assert "250.00" in text


@pytest.mark.asyncio
async def test_tools_coupon_methods():
    """SwiggyAgentTools correctly exposes list_available_coupons and apply_cart_coupon."""
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    list_res = await tools.list_available_coupons()
    assert list_res["success"] is True
    assert len(list_res["coupons"]) >= 1

    apply_res = await tools.apply_cart_coupon("INSTA50")
    assert apply_res["success"] is True
    assert apply_res["discount_amount"] == 50.0
