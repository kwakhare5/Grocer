"""Grocer v1.0 — Phase 4 3-Lock Payment Safety Gate & Checkout Test Suite.

Strictly verified against committed real Swiggy MCP staging fixtures and live Supabase PostgreSQL.
Enforces:
1. Lock 1 (Authority): Physical button ID required; text "yes" strictly rejected.
2. Lock 2 (Truth): Live cart re-verification, 100% stock, integer paise, ₹1 price drift abort, launch cap.
3. Lock 3 (Exactly-Once): Atomic PostgreSQL CAS on grocer.approvals; double-tap creates exactly one checkout.
4. WhatsApp CTA URL Button: HTTPS bridgeUrl enforced; upi:// schemes rejected.
5. Small-Cart Fee Shock Warning (ADR 0009): Warns customer when fees exceed 35% of item total.
6. Background Poller & Post-Payment Session Reset (ADR 0010): check_payment_status confirms and resets basket.
7. Real-Time GPS Tracking: track_order transitions to live rider and map URL upon settlement.
8. Multi-Store Split Orders (ADR 0007): Unified WhatsApp receipt + split tracking links.
9. Order Cancellation Escalation (ADR 0007): Phone escalation to Swiggy Care 080-67466729.
10. Post-Order Additions (ADR 0009): Dark store locked order protection + separate 1-tap reorder.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import pytest

from backend.agent.approval import (
    ApprovalRecord,
    check_small_cart_fee,
    compute_cart_fingerprint,
    create_checkout_approval,
    parse_price_to_paise,
)
from backend.agent.checkout_executor import (
    DEFAULT_LAUNCH_CAP_PAISE,
    SWIGGY_CARE_PHONE,
    check_and_settle_payment,
    execute_3_lock_checkout,
    format_multi_store_split_receipt,
    format_whatsapp_cta_url_button,
    get_order_cancellation_instructions,
    handle_post_order_addition,
    poll_pending_checkouts_batch,
    verify_lock_1_authority,
    verify_lock_2_truth,
)
from backend.database import get_db_pool
from backend.integrations.commerce.schemas import (
    CartData,
    CartItem,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return SwiggyClient(fixtures_dir=FIXTURES_DIR)


# ==============================================================================
# 1. Lock 1 (Authority) Tests
# ==============================================================================
def test_lock_1_physical_button_authority_and_text_yes_rejection():
    """Text 'yes', 'confirm', or 'proceed' is strictly rejected; only physical pay: button passes."""
    # Physical interactive button tap passes
    valid_button = verify_lock_1_authority(message_type="button_reply", button_id="pay:appr_01HXYZ")
    assert valid_button.passed is True
    assert valid_button.lock_name == "Lock 1 (Authority)"

    # Text 'yes' is strictly rejected
    text_yes = verify_lock_1_authority(message_type="text", button_id=None)
    assert text_yes.passed is False
    assert "physically tapping the WhatsApp payment button" in text_yes.reason
    assert "yes" in text_yes.reason.lower()

    # Non-pay button (e.g. cart clear) is rejected
    non_pay_button = verify_lock_1_authority(message_type="button_reply", button_id="cart:clear")
    assert non_pay_button.passed is False

    # Mismatched approval ID is rejected
    mismatched_btn = verify_lock_1_authority(
        message_type="button_reply",
        button_id="pay:appr_OTHER_ID",
        expected_approval_id="appr_01HXYZ",
    )
    assert mismatched_btn.passed is False
    assert "does not match the active receipt approval" in mismatched_btn.reason


# ==============================================================================
# 2. Lock 2 (Truth) Tests
# ==============================================================================
def test_lock_2_price_drift_aborts_checkout(swiggy_client):
    """If store price drifts by >= ₹1 (100 paise), checkout is aborted immediately."""
    live_cart = swiggy_client.get_cart()
    live_to_pay = 14900  # ₹149.00 from staging get_cart fixture

    # Approval with matching price passes
    matching_fp = compute_cart_fingerprint(live_cart.items, live_to_pay, "addr_01HXYZ")
    approval_valid = ApprovalRecord(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint=matching_fp,
        to_pay_paise=live_to_pay,
        address_id="addr_01HXYZ",
        snapshot={},
        status="shown",
        expires_at=None,
    )
    res_valid = verify_lock_2_truth(approval_valid, live_cart)
    assert res_valid.passed is True

    # Approval where price shifted by ₹2.00 (200 paise) aborts
    approval_drift = ApprovalRecord(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint=matching_fp,
        to_pay_paise=live_to_pay - 200,  # ₹2 price shift
        address_id="addr_01HXYZ",
        snapshot={},
        status="shown",
        expires_at=None,
    )
    res_drift = verify_lock_2_truth(approval_drift, live_cart)
    assert res_drift.passed is False
    assert "price shifted" in res_drift.reason.lower()


def test_lock_2_out_of_stock_aborts_checkout(swiggy_client):
    """If an item is marked unavailable or removed, Lock 2 aborts."""
    unavailable_cart = CartData(
        cartId="cart_unavail",
        cartTotalAmount="144.00",
        items=[
            CartItem(
                spinId="spin_oos",
                skuId="sku_oos",
                productId="prod_oos",
                itemName="Fresh Toned Milk 1L",
                quantity=1,
                isInStockAndAvailable=False,
                mrp=74.0,
                discountedFinalPrice=72.0,
            )
        ],
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹72.00"}],
            "toPay": {"label": "To Pay", "value": "₹72.00"},
        },
        removedOutOfStockItems=[],
    )

    approval = ApprovalRecord(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint="dummy_fp",
        to_pay_paise=7200,
        address_id="addr_01HXYZ",
        snapshot={},
        status="shown",
        expires_at=None,
    )

    res = verify_lock_2_truth(approval, unavailable_cart)
    assert res.passed is False
    assert "unavailable" in res.reason.lower()


def test_lock_2_launch_safety_cap_enforced(swiggy_client):
    """Orders exceeding the ₹1,000 launch safety cap (100,000 paise) are blocked."""
    expensive_cart = CartData(
        cartId="cart_expensive",
        cartTotalAmount="1250.00",
        items=[
            CartItem(
                spinId="spin_olive_oil",
                skuId="sku_oil",
                productId="prod_oil",
                itemName="Extra Virgin Olive Oil 1L",
                quantity=1,
                isInStockAndAvailable=True,
                mrp=1300.0,
                discountedFinalPrice=1250.0,
            )
        ],
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹1250.00"}],
            "toPay": {"label": "To Pay", "value": "₹1250.00"},
        },
    )

    expensive_fp = compute_cart_fingerprint(expensive_cart.items, "addr_01HXYZ")
    approval = ApprovalRecord(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint=expensive_fp,
        to_pay_paise=125000,
        address_id="addr_01HXYZ",
        snapshot={},
        status="shown",
        expires_at=None,
    )

    res = verify_lock_2_truth(approval, expensive_cart, max_launch_cap_paise=DEFAULT_LAUNCH_CAP_PAISE)
    assert res.passed is False
    assert "launch safety limit" in res.reason.lower()


def test_lock_2_fingerprint_mismatch_aborts(swiggy_client):
    """If cart items are changed after approval generation, fingerprint mismatch aborts."""
    live_cart = swiggy_client.get_cart()
    live_to_pay = 14900

    approval = ApprovalRecord(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint="tampered_different_fingerprint_hash_value_1234567890abcdef",
        to_pay_paise=live_to_pay,
        address_id="addr_01HXYZ",
        snapshot={},
        status="shown",
        expires_at=None,
    )

    res = verify_lock_2_truth(approval, live_cart)
    assert res.passed is False
    assert "basket contents changed" in res.reason.lower()


# ==============================================================================
# 3. WhatsApp CTA URL Button Tests
# ==============================================================================
def test_whatsapp_cta_url_button_formatting_and_scheme_guard():
    """Swiggy HTTPS bridgeUrl is formatted into WhatsApp CTA URL button; upi:// is rejected."""
    # Valid HTTPS bridgeUrl
    btn = format_whatsapp_cta_url_button(
        bridge_url="https://mcp.swiggy.com/pay/bridge?id=paas_01HZ123456789",
        amount_paise=14900,
    )
    assert btn["type"] == "cta_url"
    assert btn["parameters"]["display_text"] == "Pay ₹149 (UPI / Card)"
    assert btn["parameters"]["url"].startswith("https://")

    # upi:// scheme must raise ValueError
    with pytest.raises(ValueError, match="Strict scheme violation"):
        format_whatsapp_cta_url_button(
            bridge_url="upi://pay?pa=swiggy@icici&am=149.00",
            amount_paise=14900,
        )


# ==============================================================================
# 4. Small-Cart Fee Warning (ADR 0009)
# ==============================================================================
def test_small_cart_fee_warning_adr_0009():
    """Warns customer when delivery and handling fees exceed 35% of item total."""
    # Cart with ₹14 Maggi and ₹60 delivery/handling fee (total ₹74)
    small_cart = CartData(
        cartId="cart_small",
        cartTotalAmount="14.00",
        items=[
            CartItem(
                spinId="spin_maggi",
                skuId="sku_maggi",
                productId="prod_maggi",
                itemName="Maggi 2-Minute Noodles",
                quantity=1,
                isInStockAndAvailable=True,
                mrp=14.0,
                discountedFinalPrice=14.0,
            )
        ],
        billBreakdown={
            "toPay": {"label": "To Pay", "value": "₹74.00"},
            "lineItems": [
                {"label": "Item Total", "value": "₹14.00"},
                {"label": "Delivery Fee", "value": "₹45.00"},
                {"label": "Handling Fee", "value": "₹15.00"},
            ],
        },
    )

    warning = check_small_cart_fee(small_cart, free_delivery_threshold_paise=19900)
    assert warning is not None
    assert warning.item_total_paise == 1400
    assert warning.fee_paise == 6000
    assert "Heads up" in warning.warning_text
    assert "FREE delivery" in warning.warning_text
    assert len(warning.action_buttons) == 2
    assert warning.action_buttons[0]["id"] == "cart:add_essentials"


# ==============================================================================
# 5. Lock 3 (Atomic CAS) & Double-Tap Prevention
# ==============================================================================
@pytest.mark.asyncio
async def test_lock_3_atomic_cas_prevents_double_charge(swiggy_client):
    """Rapid double-tap executes exactly once; second tap is safely dropped by atomic CAS."""
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn, conn.transaction():
        # Setup test user and session
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, active_address_id) VALUES ($1, 'addr_01HXYZ');",
            user_id,
        )

        # Baseline cart from real staging fixture
        live_cart = swiggy_client.get_cart()
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=live_cart,
            address_id="addr_01HXYZ",
        )

        # First Tap: Should succeed and create exactly 1 checkout record
        res1 = await execute_3_lock_checkout(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            message_type="button_reply",
            button_id=f"pay:{approval.id}",
        )
        assert res1.success is True
        assert res1.order_id == "189456789012"
        assert res1.bridge_url.startswith("https://")
        assert res1.cta_button["type"] == "cta_url"

        # Second Tap (Rapid Double-Tap with same approval_id): Must be rejected by CAS
        res2 = await execute_3_lock_checkout(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            message_type="button_reply",
            button_id=f"pay:{approval.id}",
        )
        assert res2.success is False
        assert "already been processed or has expired" in res2.error_message

        # Verify exactly 1 checkout record in database for this approval
        checkouts_count = await conn.fetchval(
            "SELECT count(*) FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
        assert checkouts_count == 1


# ==============================================================================
# 6. Payment Poller & Post-Payment Session Reset (ADR 0010)
# ==============================================================================
@pytest.mark.asyncio
async def test_check_payment_status_poller_and_session_reset(swiggy_client):
    """Payment confirmation marks checkout placed, resets session basket, and links GPS tracking."""
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn, conn.transaction():
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        # Put non-empty history in session
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id, history)
            VALUES ($1, 'addr_01HXYZ', '[{"role": "user", "text": "milk"}]'::jsonb);
            """,
            user_id,
        )

        live_cart = swiggy_client.get_cart()
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=live_cart,
            address_id="addr_01HXYZ",
        )

        # Checkout
        checkout_res = await execute_3_lock_checkout(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            message_type="button_reply",
            button_id=f"pay:{approval.id}",
        )
        assert checkout_res.success is True

        # Settle Payment
        settle_res = await check_and_settle_payment(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            order_id=checkout_res.order_id,
            paas_id=checkout_res.paas_id,
        )

        assert settle_res.confirmed is True
        assert settle_res.order_id == "189456789012"
        assert "Payment Confirmed" in settle_res.message
        assert "swiggy.com/track/189456789012" in settle_res.message

        # Verify session history was purged to '[]' (ADR 0010 Post-Payment Reset)
        session_hist = await conn.fetchval(
            "SELECT history FROM grocer.sessions WHERE user_id = $1;",
            user_id,
        )
        assert json.loads(session_hist) == []

        # Verify approval is consumed
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            uuid.UUID(approval.id),
        )
        assert approval_status == "consumed"


# ==============================================================================
# 7. Real-Time GPS Rider Tracking Test
# ==============================================================================
def test_real_time_gps_rider_tracking(swiggy_client):
    """track_order provides real-time rider name, dark store name, ETA, and coordinates."""
    tracking = swiggy_client.track_order("189456789012")
    assert tracking.orderId == "189456789012"
    assert tracking.status.statusMessage == "On the way"
    assert tracking.status.etaMinutes == 8
    assert tracking.storeInfo["name"] == "Swiggy Instamart Pod - Bellandur"
    assert tracking.mapInfo["riderLocation"]["latitude"] == 12.9328
    assert tracking.mapInfo["riderLocation"]["longitude"] == 77.6765


# ==============================================================================
# 8. Multi-Store Split Order Handling (ADR 0007)
# ==============================================================================
def test_multi_store_split_order_receipt_adr_0007():
    """Unified WhatsApp receipt for orders split across multiple dark stores."""
    receipt = format_multi_store_split_receipt(
        order_ids=["189456789012", "189456789099"],
        store_names=["Bellandur Pod", "Koramangala Dark Store"],
        total_paise=24900,
    )
    assert "Multi-Store Order Confirmed" in receipt
    assert "2 separate deliveries" in receipt
    assert "order #189456789012" in receipt
    assert "order #189456789099" in receipt
    assert "https://swiggy.com/track/189456789012" in receipt
    assert "https://swiggy.com/track/189456789099" in receipt


# ==============================================================================
# 9. Order Cancellation Protocol (ADR 0007)
# ==============================================================================
def test_order_cancellation_protocol_adr_0007():
    """Inbound cancellation requests instruct customer to call Swiggy Care phone directly."""
    instructions = get_order_cancellation_instructions("189456789012")
    assert SWIGGY_CARE_PHONE in instructions
    assert "080-67466729" in instructions
    assert "189456789012" in instructions
    assert "Swiggy Customer Care" in instructions


# ==============================================================================
# 10. Post-Order Additions Protocol (ADR 0009)
# ==============================================================================
def test_post_order_addition_protocol_adr_0009():
    """Informing customer that active order is sealed and proposing 1-tap separate order."""
    res = handle_post_order_addition(
        order_id="189456789012",
        item_name="6 Eggs",
        item_price_paise=5500,
        order_is_packing=True,
    )
    assert "already being packed at the dark store" in res["text"]
    assert "cannot be modified" in res["text"]
    assert len(res["buttons"]) == 2
    assert "Order 6 Eggs Now" in res["buttons"][0]["title"]


# ==============================================================================
# 11. Durable Background Poller (FOR UPDATE SKIP LOCKED)
# ==============================================================================
@pytest.mark.asyncio
async def test_durable_background_poller_skip_locked(swiggy_client):
    """Background poller uses FOR UPDATE SKIP LOCKED to settle pending checkouts and fail stale ones."""
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn, conn.transaction():
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, active_address_id) VALUES ($1, 'addr_01HXYZ');",
            user_id,
        )
        live_cart = swiggy_client.get_cart()
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=live_cart,
            address_id="addr_01HXYZ",
        )

        checkout_res = await execute_3_lock_checkout(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            message_type="button_reply",
            button_id=f"pay:{approval.id}",
        )
        assert checkout_res.success is True

    # Run background batch poller with FOR UPDATE SKIP LOCKED
    settled_list = await poll_pending_checkouts_batch(
        pool=pool,
        swiggy_client=swiggy_client,
        max_age_minutes=5,
    )
    assert len(settled_list) >= 1
    assert any(s.order_id == "189456789012" and s.confirmed is True for s in settled_list)


# ==============================================================================
# 12. Float-Free Currency Parsing Integrity
# ==============================================================================
def test_parse_price_to_paise_zero_float_loss():
    """Verify currency string and integer parsing eliminates floating-point arithmetic."""
    assert parse_price_to_paise("149.00") == 14900
    assert parse_price_to_paise("₹74.50") == 7450
    assert parse_price_to_paise("₹199") == 19900
    assert parse_price_to_paise(14900) == 14900
    assert parse_price_to_paise(None) == 0


# ==============================================================================
# 13. Module Placement & Architectural Boundaries
# ==============================================================================
def test_customer_advocate_and_formatters_module_placement():
    """Verify Layer 4 Customer Advocate and formatters live in dedicated modules."""
    import backend.agent.customer_advocate as advocate
    from backend.agent import formatters

    assert hasattr(advocate, "check_small_cart_fee")
    assert hasattr(advocate, "extract_cart_to_pay_paise")
    assert hasattr(formatters, "format_multi_store_split_receipt")
    assert hasattr(formatters, "get_order_cancellation_instructions")
    assert hasattr(formatters, "handle_post_order_addition")
