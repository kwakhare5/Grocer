"""Grocer v1.0 — Phase 5 End-to-End Staging Smoke Test Suite.

Validates the complete production-hardened lifecycle:
1. Bounded coupon trial-and-reset (max 2 applicable coupons; net savings check).
2. ₹1,000 launch safety cap enforcement and 1-tap "Raise Limit" button.
3. 24-hour DPDP data minimization scrubber and "delete my data" instant purge.
4. Milestone-only delivery push notifications (Confirmed, Picked Up, Delivered).
5. Full customer staging order journey: Discovery -> Cart -> Coupon -> 3-Lock -> Settle -> Track.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.approval import (
    create_checkout_approval,
)
from backend.agent.checkout_executor import (
    check_and_settle_payment,
    execute_3_lock_checkout,
    poll_in_flight_deliveries_batch,
    verify_lock_1_authority,
    verify_lock_2_truth,
)
from backend.agent.customer_advocate import (
    check_launch_safety_cap,
    extract_cart_to_pay_paise,
    optimize_coupons,
)
from backend.agent.delivery_tracker import (
    MILESTONE_CONFIRMED,
    MILESTONE_DELIVERED,
    MILESTONE_PICKED_UP,
    format_milestone_notification,
    resolve_delivery_milestone,
    should_send_milestone_push,
)
from backend.agent.dpdp import (
    run_24h_dpdp_scrubber,
)
from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.schemas import (
    CartData,
    CartItem,
)
from backend.integrations.commerce.swiggy_client import SwiggyClient
from backend.main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return SwiggyClient(fixtures_dir=FIXTURES_DIR)


def _compute_signature(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _make_whatsapp_message_payload(
    message_id: str,
    wa_id: str = "919876543210",
    text: str | None = None,
    button_id: str | None = None,
    button_title: str | None = None,
) -> dict:
    msg: dict = {
        "from": wa_id,
        "id": message_id,
        "timestamp": str(int(time.time())),
    }
    if button_id:
        msg["type"] = "interactive"
        msg["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": button_id, "title": button_title or button_id},
        }
    elif text is not None:
        msg["type"] = "text"
        msg["text"] = {"body": text}
    else:
        msg["type"] = "text"
        msg["text"] = {"body": "hello"}

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "16505553333",
                                "phone_number_id": "333322221111",
                            },
                            "messages": [msg],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


# ==============================================================================
# 1. Bounded Coupon Optimizer & Net Savings Guardrail
# ==============================================================================
def test_e2e_coupon_optimization_bounded_trials_and_net_savings(swiggy_client):
    """Validate bounded coupon trials (<=2) and net-savings verification."""
    # Staging baseline: 3x Amul Milk has subtotal ₹216; applying INSTA50 saves ₹72
    cart = swiggy_client.update_cart([{"spinId": "spin_amul_1l", "skuId": "sku_amul_1l", "quantity": 3}])

    # Optimize coupons with real staging fixtures
    result = optimize_coupons(
        cart=cart,
        swiggy_client=swiggy_client,
        address_id="addr_01HXYZ",
        max_trials=2,
    )

    # From staging fixture: INSTA50 is applicable and saves ₹72
    assert result.trials_conducted <= 2
    assert result.applied_coupon == "INSTA50"
    assert result.savings_paise > 0
    assert "INSTA50" in (result.savings_message or "")
    assert result.final_to_pay_paise < result.original_to_pay_paise


def test_e2e_coupon_net_savings_guardrail_rejects_fee_spike(swiggy_client):
    """If a coupon does not reduce toPay, it must be reverted and discarded."""
    # Create synthetic cart where coupon does not reduce payable total
    cart = CartData(
        cartId="cart_test",
        cartTotalAmount="200.00",
        items=[
            CartItem(
                spinId="spin_1",
                skuId="sku_1",
                productId="prod_1",
                itemName="Test Item",
                quantity=1,
                isInStockAndAvailable=True,
                mrp=200,
                discountedFinalPrice=200,
            )
        ],
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹200.00"}],
            "toPay": {"label": "To Pay", "value": "₹200.00"},
        },
    )

    class DummyFeeSpikeClient:
        def list_coupons(self, address_id=None):
            from backend.integrations.commerce.schemas import (
                AvailableCoupon,
                ListCouponsData,
            )

            return ListCouponsData(
                availableCoupons=[
                    AvailableCoupon(
                        couponCode="BADCOUPON",
                        title="Discount with fee surge",
                        isApplicable=True,
                        applicabilityStatus="APPLICABLE",
                    )
                ]
            )

        def apply_coupon(self, coupon_code):
            # Coupon lowers item price by ₹20 but adds ₹30 delivery fee -> toPay increases to ₹210
            return CartData(
                cartId="cart_test",
                cartTotalAmount="180.00",
                items=cart.items,
                billBreakdown={
                    "lineItems": [
                        {"label": "Item Total", "value": "₹180.00"},
                        {"label": "Delivery Fee", "value": "₹30.00"},
                    ],
                    "toPay": {"label": "To Pay", "value": "₹210.00"},
                },
            )

    result = optimize_coupons(cart=cart, swiggy_client=DummyFeeSpikeClient(), max_trials=2)
    # Must NOT apply BADCOUPON because 210 > 200
    assert result.applied_coupon is None
    assert result.savings_paise == 0
    assert result.final_to_pay_paise == 20000


# ==============================================================================
# 2. Launch Safety Cap & 1-Tap Raise Limit
# ==============================================================================
def test_e2e_launch_safety_cap_warning_and_raise_limit():
    """Verify orders over ₹1,000 trigger warning with 1-tap Raise Limit action button."""
    # Under cap (₹850) -> No warning
    assert check_launch_safety_cap(to_pay_paise=85000, cap_paise=100000) is None

    # Over cap (₹1,450) -> Triggers warning with interactive button
    warning = check_launch_safety_cap(to_pay_paise=145000, cap_paise=100000)
    assert warning is not None
    assert warning.excess_paise == 45000
    assert "₹1000" in warning.warning_text
    assert len(warning.action_buttons) >= 1
    assert warning.action_buttons[0]["id"].startswith("budget:raise:")


@pytest.mark.asyncio
async def test_e2e_raise_budget_cap_via_button_dispatch():
    """Verify 1-tap budget raise button persists new limit into grocer.sessions."""
    transport = ASGITransport(app=app)
    wa_id = f"9197{int(time.time()) % 100000000:08d}"
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, budget_cap_paise) VALUES ($1, 100000);",
            user_id,
        )

    # Tap raise limit button to ₹2,000 (200000 paise)
    msg_id = f"wamid.raise_{int(time.time() * 1000)}"
    payload = _make_whatsapp_message_payload(
        msg_id,
        wa_id=wa_id,
        button_id="budget:raise:200000",
        button_title="Raise Limit to ₹2,000",
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "button_dispatched"
        assert data["new_limit_paise"] == 200000

    # Verify session updated in PostgreSQL
    async with pool.acquire() as conn:
        updated_cap = await conn.fetchval(
            "SELECT budget_cap_paise FROM grocer.sessions WHERE user_id = $1;",
            user_id,
        )
        assert updated_cap == 200000


# ==============================================================================
# 3. DPDP 24-Hour Scrubber & "delete my data" Instant Purge
# ==============================================================================
@pytest.mark.asyncio
async def test_e2e_dpdp_24h_scrubber_prunes_stale_data():
    """Verify 24h scrubber nulls raw_payload, cleans snapshots, and resets stale history."""
    pool = await get_db_pool()
    wa_id = f"9196{int(time.time()) % 100000000:08d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        # 1. Insert stale inbound message (>25 hours ago)
        await conn.execute(
            """
            INSERT INTO grocer.inbound_messages (
                wa_message_id, user_id, message_type, raw_payload, created_at
            )
            VALUES ($1, $2, 'text', '{"secret": "customer_address"}'::jsonb, now() - interval '25 hours');
            """,
            f"wamid.stale_{int(time.time() * 1000)}",
            user_id,
        )
        # 2. Insert stale approval snapshot (>25 hours ago)
        await conn.execute(
            """
            INSERT INTO grocer.approvals (
                user_id, fingerprint, to_pay_paise, address_id, snapshot, created_at, expires_at
            )
            VALUES ($1, '0' * 64, 15000, 'addr_01', '{"cart": "items"}'::jsonb, now() - interval '25 hours', now() - interval '24 hours');
            """,
            user_id,
        )
        # 3. Insert stale session history (>25 hours ago)
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, history, last_active_at)
            VALUES ($1, '[{"turn": 1}]'::jsonb, now() - interval '25 hours')
            ON CONFLICT (user_id) DO UPDATE SET history = '[{"turn": 1}]'::jsonb, last_active_at = now() - interval '25 hours';
            """,
            user_id,
        )

        # Run 24h DPDP scrubber
        summary = await run_24h_dpdp_scrubber(conn)
        assert summary["inbound_scrubbed"] >= 1
        assert summary["approvals_scrubbed"] >= 1
        assert summary["sessions_pruned"] >= 1

        # Verify raw_payload was nulled
        raw_payload = await conn.fetchval(
            "SELECT raw_payload FROM grocer.inbound_messages WHERE user_id = $1;",
            user_id,
        )
        assert raw_payload is None

        # Verify approval snapshot was scrubbed to empty jsonb and address was REDACTED
        snapshot = await conn.fetchval(
            "SELECT snapshot FROM grocer.approvals WHERE user_id = $1;",
            user_id,
        )
        assert json.loads(snapshot) == {}

        scrubbed_addr = await conn.fetchval(
            "SELECT address_id FROM grocer.approvals WHERE user_id = $1;",
            user_id,
        )
        assert scrubbed_addr == "REDACTED"


@pytest.mark.asyncio
async def test_e2e_dpdp_delete_my_data_command():
    """Verify 'delete my data' inbound text command permanently purges tokens and credentials."""
    transport = ASGITransport(app=app)
    wa_id = f"9195{int(time.time()) % 100000000:08d}"
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id, swiggy_customer_id) VALUES ($1, 'cust_12345') RETURNING id;",
            wa_id,
        )
        await conn.execute(
            """
            INSERT INTO grocer.oauth_tokens (user_id, encrypted_token, nonce, expires_at)
            VALUES ($1, '\\x01020304', '\\x010203040506070809101112', now() + interval '5 days');
            """,
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id, history)
            VALUES ($1, 'addr_home', '[{"role": "user"}]'::jsonb);
            """,
            user_id,
        )

    # Customer texts "delete my data"
    msg_id = f"wamid.del_{int(time.time() * 1000)}"
    payload = _make_whatsapp_message_payload(msg_id, wa_id=wa_id, text="delete my data")
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/whatsapp/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "data_deleted"
        assert "permanently deleted" in data["message"]

    # Verify credentials wiped in PostgreSQL
    async with pool.acquire() as conn:
        token_count = await conn.fetchval(
            "SELECT count(*) FROM grocer.oauth_tokens WHERE user_id = $1;",
            user_id,
        )
        assert token_count == 0

        swiggy_cust = await conn.fetchval(
            "SELECT swiggy_customer_id FROM grocer.users WHERE id = $1;",
            user_id,
        )
        assert swiggy_cust is None


# ==============================================================================
# 4. Milestone-Only Delivery Push Notifications
# ==============================================================================
def test_e2e_delivery_milestone_resolution_and_antispam():
    """Verify delivery milestones: Confirmed -> Picked Up -> Delivered without polling spam."""
    # 1. Confirmed / Packing milestone
    m1 = resolve_delivery_milestone(status_text="Order received and store packing")
    assert m1 == MILESTONE_CONFIRMED

    # 2. Picked up milestone
    m2 = resolve_delivery_milestone(status_text="Rider on the way to delivery location")
    assert m2 == MILESTONE_PICKED_UP

    # 3. Delivered milestone
    m3 = resolve_delivery_milestone(delivered=True)
    assert m3 == MILESTONE_DELIVERED

    # 4. Anti-spam guardrail: Repeated polling of same status returns False
    assert should_send_milestone_push(last_milestone=None, new_milestone=MILESTONE_CONFIRMED) is True
    assert should_send_milestone_push(last_milestone=MILESTONE_CONFIRMED, new_milestone=MILESTONE_CONFIRMED) is False
    assert should_send_milestone_push(last_milestone=MILESTONE_CONFIRMED, new_milestone=MILESTONE_PICKED_UP) is True
    assert should_send_milestone_push(last_milestone=MILESTONE_PICKED_UP, new_milestone=MILESTONE_PICKED_UP) is False
    assert should_send_milestone_push(last_milestone=MILESTONE_PICKED_UP, new_milestone=MILESTONE_DELIVERED) is True

    # 5. Formatter produces clean WhatsApp copy with live GPS link on Picked Up
    note_picked_up = format_milestone_notification(
        order_id="189456789012",
        milestone=MILESTONE_PICKED_UP,
        eta_text="8 mins",
    )
    assert "🛵" in note_picked_up.message
    assert "https://swiggy.com/track/189456789012" in note_picked_up.message


# ==============================================================================
# 5. Full Staging Order Journey
# ==============================================================================
@pytest.mark.asyncio
async def test_e2e_full_staging_customer_journey(swiggy_client):
    """Full staging smoke test: Address -> Search -> Update Cart -> Coupon -> 3-Lock -> Settle -> Track."""
    pool = await get_db_pool()
    wa_id = f"9194{int(time.time()) % 100000000:08d}"

    # Step 1: User & Address Discovery
    addresses = swiggy_client.get_addresses(page=1, page_size=5)
    assert len(addresses.addresses) >= 1
    selected_address = addresses.addresses[0]

    # Step 2: Catalog Search
    search_res = swiggy_client.search_products(query="Amul Milk")
    assert len(search_res.products) >= 1
    chosen_product = search_res.products[0]

    # Step 3: Cart Assembly (3 units of milk = ₹216 subtotal, unlocks INSTA50 savings)
    cart = swiggy_client.update_cart(
        items=[{"spinId": chosen_product.variations[0].spinId, "skuId": chosen_product.variations[0].skuId, "quantity": 3}],
        address_id=selected_address.id,
    )
    assert len(cart.items) >= 1

    # Step 4: Coupon Optimization
    coupon_res = optimize_coupons(cart=cart, swiggy_client=swiggy_client, address_id=selected_address.id)
    assert coupon_res.applied_coupon == "INSTA50"
    active_cart = coupon_res.final_cart or cart
    assert extract_cart_to_pay_paise(active_cart) > 0

    # Step 5: Lock 1 Authority (rejects text yes; accepts button tap)
    assert verify_lock_1_authority("text", None).passed is False

    # Step 6: Create PostgreSQL Approval Record
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, active_address_id) VALUES ($1, $2);",
            user_id,
            selected_address.id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=active_cart,
            address_id=selected_address.id,
        )
        assert approval.id is not None

        # Step 7: Lock 2 Truth Verification
        lock_2 = verify_lock_2_truth(approval=approval, live_cart=active_cart)
        assert lock_2.passed is True

        # Step 8: Lock 3 Exactly-Once Checkout
        checkout_res = await execute_3_lock_checkout(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            message_type="button_reply",
            button_id=f"pay:{approval.id}",
        )
        assert checkout_res.success is True
        assert checkout_res.order_id == "189456789012"
        assert checkout_res.cta_button["parameters"]["url"].startswith("https://")
        assert checkout_res.bridge_url.startswith("https://")

        # Step 9: Settlement & Session Reset
        settlement = await check_and_settle_payment(
            conn=conn,
            swiggy_client=swiggy_client,
            user_id=str(user_id),
            approval_id=approval.id,
            order_id=checkout_res.order_id,
            paas_id=checkout_res.paas_id,
        )
        assert settlement.confirmed is True

        # Verify basket session cleared
        session_history = await conn.fetchval(
            "SELECT history FROM grocer.sessions WHERE user_id = $1;",
            user_id,
        )
        assert json.loads(session_history) == []

    # Step 10: Milestone Tracking Transition
    delivery_status = swiggy_client.get_delivery_status(checkout_res.order_id)
    milestone = resolve_delivery_milestone(status_text=delivery_status.statusText)
    assert milestone == MILESTONE_PICKED_UP
    notification = format_milestone_notification(
        order_id=checkout_res.order_id,
        milestone=milestone,
        eta_text=delivery_status.etaText,
    )
    assert "🛵" in notification.message


@pytest.mark.asyncio
async def test_e2e_in_flight_delivery_poller_and_milestone_transition(swiggy_client):
    """Verify background poller tracks placed orders through live milestone updates."""
    pool = await get_db_pool()
    wa_id = f"9193{int(time.time()) % 100000000:08d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        # Create an approval record
        approval_id = await conn.fetchval(
            """
            INSERT INTO grocer.approvals (user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at)
            VALUES ($1, '0'*64, 14900, 'addr_01', '{}'::jsonb, 'consumed', now() + interval '10 minutes')
            RETURNING id;
            """,
            user_id,
        )
        # Create a placed checkout record
        await conn.execute(
            """
            INSERT INTO grocer.checkouts (
                approval_id, user_id, payment_method, address_id, status, swiggy_order_id, approved_to_pay_paise
            )
            VALUES ($1, $2, 'upi', 'addr_01', 'placed', '189456789012', 14900);
            """,
            approval_id,
            user_id,
        )

    # Poll in-flight deliveries with real staging delivery status
    notifications = await poll_in_flight_deliveries_batch(pool, swiggy_client, user_id=str(user_id))
    assert len(notifications) >= 1
    assert any(n.order_id == "189456789012" and n.milestone == MILESTONE_PICKED_UP for n in notifications)

    # Verify checkout row status updated to 'out_for_delivery'
    async with pool.acquire() as conn:
        updated_status = await conn.fetchval(
            "SELECT status FROM grocer.checkouts WHERE swiggy_order_id = '189456789012' AND user_id = $1;",
            user_id,
        )
        assert updated_status == "out_for_delivery"


@pytest.mark.asyncio
async def test_e2e_pay_button_fast_path_executes_3_lock_checkout(swiggy_client):
    """Verify interactive [Pay] button tap directly executes 3-lock checkout in button_router."""
    from backend.channels.button_router import dispatch_button_action

    pool = await get_db_pool()
    wa_id = f"9192{int(time.time()) % 100000000:08d}"

    # Setup basket, addresses, and active approval
    cart = swiggy_client.get_cart()
    assert extract_cart_to_pay_paise(cart) > 0

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=cart,
            address_id="addr_01HXYZ",
        )

    # Customer physically taps [Pay] button
    btn_id = f"pay:{approval.id}"
    res = await dispatch_button_action(
        button_id=btn_id,
        wa_id=wa_id,
        pool=pool,
        swiggy_client=swiggy_client,
    )

    # Proves 3-lock checkout was executed and returned HTTPS bridgeUrl!
    assert res["status"] == "checkout_executed"
    assert res["order_id"] == "189456789012"
    assert res["bridge_url"].startswith("https://")
    assert res["cta_button"]["type"] == "cta_url"

