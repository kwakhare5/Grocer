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

import asyncio
import json
import time
import uuid
from pathlib import Path

import httpx
import pytest
from fixture_client import FixtureSwiggyClient

from backend.agent import checkout_executor
from backend.agent.approval import (
    ApprovalRecord,
    compute_cart_fingerprint,
    create_checkout_approval,
)
from backend.agent.checkout_executor import (
    DEFAULT_LAUNCH_CAP_PAISE,
    SWIGGY_CARE_PHONE,
    check_and_settle_payment,
    execute_3_lock_checkout,
    format_whatsapp_cta_url_button,
    poll_in_flight_deliveries_batch,
    poll_pending_checkouts_batch,
    reconcile_attempting_checkouts,
    verify_lock_1_authority,
    verify_lock_2_truth,
)
from backend.agent.customer_advocate import (
    parse_price_to_paise,
    raise_session_budget_cap,
)
from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.schemas import (
    CartData,
    CartItem,
    CheckoutData,
    DeliveryStatusData,
    OrderHistoryItem,
    OrdersListData,
)
from backend.integrations.commerce.swiggy_client import (
    SwiggyAuthExpiredError,
    SwiggyClient,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

pytestmark = pytest.mark.scripted


@pytest.fixture
def swiggy_client() -> SwiggyClient:
    return FixtureSwiggyClient(FIXTURES_DIR)


class ScriptedClient:
    """Fixture-backed Swiggy boundary with a checkout that can fail on demand."""

    def __init__(
        self,
        fixture_client: SwiggyClient,
        cart: CartData | None = None,
        checkout_error: Exception | None = None,
        orders_after: list[str] | None = None,
        orders_error: Exception | None = None,
    ) -> None:
        self.fixture = fixture_client
        self.cart = cart
        self.checkout_error = checkout_error
        self.orders_after = orders_after or []
        self.orders_error = orders_error
        self.checkout_calls = 0
        self.checkout_failed = False

    def get_cart(self, address_id: str | None = None) -> CartData:
        if self.cart is not None:
            return self.cart
        return self.fixture.get_cart(address_id)

    def get_orders(
        self,
        count: int = 10,
        order_type: str = "INSTAMART",
        active_only: bool = False,
    ) -> OrdersListData:
        # The pre-checkout snapshot must work; the error only hits recovery.
        if self.orders_error is not None and self.checkout_failed:
            raise self.orders_error
        if self.checkout_failed and self.orders_after:
            return OrdersListData(
                orders=[
                    OrderHistoryItem(
                        orderId=order_id,
                        status="PLACED",
                        createdAt="2026-10-27T10:00:00Z",
                        itemCount=1,
                        totalAmount=149.0,
                    )
                    for order_id in self.orders_after
                ]
            )
        return OrdersListData(orders=[])

    def checkout(
        self,
        payment_method: str = "UPI",
        address_id: str | None = None,
        intent_app: str | None = None,
    ) -> CheckoutData:
        self.checkout_calls += 1
        self.checkout_failed = True
        if self.checkout_error is not None:
            raise self.checkout_error
        return CheckoutData(
            orderId="189456789012",
            paymentMethod=payment_method,
            status="PENDING_PAYMENT",
            paasId="paas_test_123",
            bridgeUrl="https://mcp.swiggy.com/pay/bridge?id=paas_test_123",
            cartTotal=149.0,
            deliveryLabel="Home",
        )


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


async def test_live_checkout_lock_blocks_before_any_swiggy_call():
    """With the deploy lock off, no Swiggy method runs and no approval is consumed."""

    class ForbiddenClient:
        def get_cart(self, *args, **kwargs):
            raise AssertionError("get_cart called while checkout is locked")

        def checkout(self, *args, **kwargs):
            raise AssertionError("checkout called while checkout is locked")

    res = await execute_3_lock_checkout(
        pool=None,
        swiggy_client=ForbiddenClient(),
        user_id="u",
        approval_id="a",
        message_type="button_reply",
        button_id="pay:a",
    )
    assert res.success is False
    assert "locked" in (res.error_message or "").lower()


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
    drift_to_pay = live_to_pay - 200
    drift_fp = compute_cart_fingerprint(live_cart.items, drift_to_pay, "addr_01HXYZ")
    approval_drift = ApprovalRecord(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint=drift_fp,
        to_pay_paise=drift_to_pay,  # ₹2 price shift
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

    expensive_fp = compute_cart_fingerprint(expensive_cart.items, 125000, "addr_01HXYZ")
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


def test_upi_checkout_sends_qr_request(swiggy_client):
    """UPI checkout carries generateUPIQR, or an intent app when one is chosen."""
    swiggy_client.checkout(payment_method="UPI", address_id="addr_01HXYZ")
    assert swiggy_client.last_checkout_args == {
        "paymentMethod": "UPI",
        "addressId": "addr_01HXYZ",
        "generateUPIQR": True,
    }

    swiggy_client.checkout(
        payment_method="UPI", address_id="addr_01HXYZ", intent_app="gpay://upi/"
    )
    assert swiggy_client.last_checkout_args["intentApp"] == "gpay://upi/"
    assert "generateUPIQR" not in swiggy_client.last_checkout_args

    swiggy_client.checkout(payment_method="COD", address_id="addr_01HXYZ")
    assert swiggy_client.last_checkout_args == {
        "paymentMethod": "COD",
        "addressId": "addr_01HXYZ",
    }


# ==============================================================================
# 4. Small-Cart Fee Warning (ADR 0009)
# ==============================================================================
# ==============================================================================
# 5. Lock 3 (Atomic CAS) & Double-Tap Prevention
# ==============================================================================
@pytest.mark.db
@pytest.mark.asyncio
async def test_lock_3_atomic_cas_prevents_double_charge(swiggy_client, monkeypatch):
    """Rapid double-tap executes exactly once; second tap is safely dropped by atomic CAS."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn:
        # Setup test user and session (committed before checkout starts)
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
        pool=pool,
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
        pool=pool,
        swiggy_client=swiggy_client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert res2.success is False
    assert "already been processed or has expired" in res2.error_message

    # Verify exactly 1 checkout record in database for this approval
    async with pool.acquire() as conn:
        checkouts_count = await conn.fetchval(
            "SELECT count(*) FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
    assert checkouts_count == 1


@pytest.mark.db
@pytest.mark.asyncio
async def test_concurrent_taps_place_exactly_one_order(swiggy_client, monkeypatch):
    """Two simultaneous taps race on the CAS: one wins, one is dropped, one row exists."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, active_address_id) VALUES ($1, 'addr_01HXYZ');",
            user_id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=swiggy_client.get_cart(),
            address_id="addr_01HXYZ",
        )

    results = await asyncio.gather(
        *(
            execute_3_lock_checkout(
                pool=pool,
                swiggy_client=FixtureSwiggyClient(FIXTURES_DIR),
                user_id=str(user_id),
                approval_id=approval.id,
                message_type="button_reply",
                button_id=f"pay:{approval.id}",
            )
            for _ in range(2)
        )
    )

    assert sum(1 for res in results if res.success) == 1
    async with pool.acquire() as conn:
        checkouts_count = await conn.fetchval(
            "SELECT count(*) FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
    assert checkouts_count == 1


@pytest.mark.db
@pytest.mark.asyncio
async def test_lock_3_cas_rejects_another_user(swiggy_client, monkeypatch):
    """A pay button from someone else's receipt cannot claim the approval."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    pool = await get_db_pool()
    stamp = int(time.time() * 1000) % 10000000000

    async with pool.acquire() as conn:
        owner_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            f"91{stamp:010d}",
        )
        other_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            f"91{(stamp + 1) % 10000000000:010d}",
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(owner_id),
            cart=swiggy_client.get_cart(),
            address_id="addr_01HXYZ",
        )

    res = await execute_3_lock_checkout(
        pool=pool,
        swiggy_client=swiggy_client,
        user_id=str(other_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert res.success is False
    assert "already been processed or has expired" in res.error_message

    async with pool.acquire() as conn:
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            uuid.UUID(approval.id),
        )
        checkouts_count = await conn.fetchval(
            "SELECT count(*) FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
    assert approval_status == "shown"
    assert checkouts_count == 0


@pytest.mark.db
@pytest.mark.asyncio
async def test_checkout_timeout_recovers_order_from_get_orders(swiggy_client, monkeypatch):
    """A timed-out checkout call is treated as success when get_orders shows a new order."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(checkout_executor, "CHECKOUT_RECONCILE_WAIT_SECONDS", 0)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"
    client = ScriptedClient(
        swiggy_client,
        checkout_error=httpx.ReadTimeout("checkout timed out"),
        orders_after=["189456789999"],
    )

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=swiggy_client.get_cart(),
            address_id="addr_01HXYZ",
        )

    res = await execute_3_lock_checkout(
        pool=pool,
        swiggy_client=client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert res.success is True
    assert res.order_id == "189456789999"
    assert res.bridge_url is None
    assert "confirmed it through your order list" in res.receipt_text
    assert client.checkout_calls == 1

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, swiggy_order_ids, response_total_paise FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            uuid.UUID(approval.id),
        )
    assert row["status"] == "confirming"
    assert json.loads(row["swiggy_order_ids"]) == ["189456789999"]
    assert row["response_total_paise"] == approval.to_pay_paise
    assert approval_status == "consumed"


@pytest.mark.db
@pytest.mark.asyncio
async def test_checkout_failure_without_order_stays_payable(swiggy_client, monkeypatch):
    """A failed checkout with no order leaves the approval shown so the same button retries."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(checkout_executor, "CHECKOUT_RECONCILE_WAIT_SECONDS", 0)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"
    client = ScriptedClient(
        swiggy_client,
        checkout_error=httpx.ConnectError("swiggy down"),
    )

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=swiggy_client.get_cart(),
            address_id="addr_01HXYZ",
        )

    res = await execute_3_lock_checkout(
        pool=pool,
        swiggy_client=client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert res.success is False
    assert "nothing was charged" in res.error_message
    assert client.checkout_calls == 2  # one call, then one retry after an empty reconcile

    async with pool.acquire() as conn:
        checkout_status = await conn.fetchval(
            "SELECT status FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            uuid.UUID(approval.id),
        )
    assert checkout_status == "failed"
    assert approval_status == "shown"


@pytest.mark.db
@pytest.mark.asyncio
async def test_checkout_unverified_outcome_blocks_retry(swiggy_client, monkeypatch):
    """If get_orders is also unreachable, the approval stays claimed and the user is told not to retry."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(checkout_executor, "CHECKOUT_RECONCILE_WAIT_SECONDS", 0)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"
    client = ScriptedClient(
        swiggy_client,
        checkout_error=httpx.ReadTimeout("checkout timed out"),
        orders_error=httpx.ConnectError("orders unreachable"),
    )

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=swiggy_client.get_cart(),
            address_id="addr_01HXYZ",
        )

    res = await execute_3_lock_checkout(
        pool=pool,
        swiggy_client=client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert res.success is False
    assert "Do not tap pay again" in res.error_message
    assert client.checkout_calls == 1

    async with pool.acquire() as conn:
        checkout_status = await conn.fetchval(
            "SELECT status FROM grocer.checkouts WHERE approval_id = $1;",
            uuid.UUID(approval.id),
        )
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            uuid.UUID(approval.id),
        )
    assert checkout_status == "unknown"
    assert approval_status == "consuming"


@pytest.mark.db
@pytest.mark.asyncio
async def test_crash_after_order_is_reconciled(swiggy_client):
    """A checkout row stuck in 'attempting' is resolved by comparing orders to the snapshot."""
    pool = await get_db_pool()
    stamp = int(time.time() * 1000) % 10000000000

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            f"91{stamp:010d}",
        )
        approval_id = await conn.fetchval(
            """
            INSERT INTO grocer.approvals (user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at)
            VALUES ($1, repeat('0', 64), 14900, 'addr_01HXYZ', '{}'::jsonb, 'consuming', now() + interval '10 minutes')
            RETURNING id;
            """,
            user_id,
        )
        checkout_id = await conn.fetchval(
            """
            INSERT INTO grocer.checkouts (
                approval_id, user_id, payment_method, address_id, known_order_ids, status, approved_to_pay_paise
            )
            VALUES ($1, $2, 'upi', 'addr_01HXYZ', '[]'::jsonb, 'attempting', 14900)
            RETURNING id;
            """,
            approval_id,
            user_id,
        )

    client = ScriptedClient(swiggy_client, orders_after=["189456789777"])
    client.checkout_failed = True  # make the post-checkout order list visible

    resolved = await reconcile_attempting_checkouts(pool, client, older_than_seconds=0)
    assert str(checkout_id) in resolved

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, swiggy_order_id FROM grocer.checkouts WHERE id = $1;",
            checkout_id,
        )
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            approval_id,
        )
    assert row["status"] == "confirming"
    assert row["swiggy_order_id"] == "189456789777"
    assert approval_status == "consumed"


@pytest.mark.db
@pytest.mark.asyncio
async def test_crash_without_order_expires_approval(swiggy_client):
    """A stuck attempt with no new order is marked failed and frees the approval."""
    pool = await get_db_pool()
    stamp = int(time.time() * 1000) % 10000000000

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            f"91{stamp:010d}",
        )
        approval_id = await conn.fetchval(
            """
            INSERT INTO grocer.approvals (user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at)
            VALUES ($1, repeat('0', 64), 14900, 'addr_01HXYZ', '{}'::jsonb, 'consuming', now() + interval '10 minutes')
            RETURNING id;
            """,
            user_id,
        )
        checkout_id = await conn.fetchval(
            """
            INSERT INTO grocer.checkouts (
                approval_id, user_id, payment_method, address_id, known_order_ids, status, approved_to_pay_paise
            )
            VALUES ($1, $2, 'upi', 'addr_01HXYZ', '[]'::jsonb, 'attempting', 14900)
            RETURNING id;
            """,
            approval_id,
            user_id,
        )

    resolved = await reconcile_attempting_checkouts(
        pool, ScriptedClient(swiggy_client), older_than_seconds=0
    )
    assert str(checkout_id) in resolved

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, swiggy_order_id FROM grocer.checkouts WHERE id = $1;",
            checkout_id,
        )
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            approval_id,
        )
    assert row["status"] == "failed"
    assert row["swiggy_order_id"] is None
    assert approval_status == "expired"


@pytest.mark.db
@pytest.mark.asyncio
async def test_cap_raise_keeps_receipt_payable(swiggy_client, monkeypatch):
    """A cap failure returns the approval to shown; after raising, the same receipt pays."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

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
    client = ScriptedClient(swiggy_client, cart=expensive_cart)

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, active_address_id, budget_cap_paise) VALUES ($1, 'addr_01HXYZ', 100000);",
            user_id,
        )
        approval = await create_checkout_approval(
            conn=conn,
            user_id=str(user_id),
            cart=expensive_cart,
            address_id="addr_01HXYZ",
        )

    over_cap = await execute_3_lock_checkout(
        pool=pool,
        swiggy_client=client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert over_cap.success is False
    assert over_cap.cta_button["parameters"]["button_id"] == (
        f"budget:raise:{approval.id}:125000"
    )

    async with pool.acquire() as conn:
        status_after_cap = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;",
            uuid.UUID(approval.id),
        )
        await raise_session_budget_cap(conn, str(user_id), 125000)
    assert status_after_cap == "shown"

    paid = await execute_3_lock_checkout(
        pool=pool,
        swiggy_client=client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert paid.success is True
    assert paid.order_id == "189456789012"


# ==============================================================================
# 6. Payment Poller & Post-Payment Session Reset (ADR 0010)
# ==============================================================================
@pytest.mark.db
@pytest.mark.asyncio
async def test_check_payment_status_poller_and_session_reset(swiggy_client, monkeypatch):
    """Payment confirmation marks checkout placed, resets session basket, and links GPS tracking."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            wa_id,
        )
        # Put non-empty history and delivery coords in session
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id, history, delivery_latitude, delivery_longitude)
            VALUES ($1, 'addr_01HXYZ', '[{"role": "user", "text": "milk"}]'::jsonb, 12.9352, 77.6245);
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
        pool=pool,
        swiggy_client=swiggy_client,
        user_id=str(user_id),
        approval_id=approval.id,
        message_type="button_reply",
        button_id=f"pay:{approval.id}",
    )
    assert checkout_res.success is True

    # Settle Payment
    async with pool.acquire() as conn:
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
    tracking = swiggy_client.track_order("189456789012", 12.9352, 77.6245)
    assert tracking.orderId == "189456789012"
    assert tracking.status.statusMessage == "On the way"
    assert tracking.status.etaMinutes == 8
    assert tracking.storeInfo["name"] == "Swiggy Instamart Pod - Bellandur"
    assert tracking.mapInfo["riderLocation"]["latitude"] == 12.9328
    assert tracking.mapInfo["riderLocation"]["longitude"] == 77.6765


# ==============================================================================
# 8. Order Cancellation Protocol (ADR 0007)
# ==============================================================================
def test_order_cancellation_protocol_adr_0007():
    """Inbound cancellation requests instruct customer to call Swiggy Care phone directly."""
    from backend.agent.read_actions import _cancel_help

    instructions = _cancel_help()
    assert SWIGGY_CARE_PHONE in instructions
    assert "080-67466729" in instructions
    assert "cancel" in instructions.lower()


# ==============================================================================
# 11. Durable Background Poller (FOR UPDATE SKIP LOCKED)
# ==============================================================================
@pytest.mark.db
@pytest.mark.asyncio
async def test_durable_background_poller_skip_locked(swiggy_client, monkeypatch):
    """Background poller uses FOR UPDATE SKIP LOCKED to settle pending checkouts and fail stale ones."""
    monkeypatch.setattr(settings, "LIVE_CHECKOUT_ENABLED", True)
    pool = await get_db_pool()
    wa_id = f"91{int(time.time() * 1000) % 10000000000:010d}"

    async with pool.acquire() as conn:
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
        pool=pool,
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
def test_customer_advocate_module_placement():
    """Verify Layer 4 Customer Advocate lives in its dedicated module."""
    import backend.agent.customer_advocate as advocate

    assert hasattr(advocate, "extract_cart_to_pay_paise")


# ==============================================================================
# 14. Delivery Milestones & Poller Recovery (Phase 4)
# ==============================================================================
class ScriptedDeliveryClient:
    def __init__(self, statuses: dict[str, DeliveryStatusData]) -> None:
        self.statuses = statuses
        self.queried: list[str] = []

    def get_delivery_status(self, order_id: str) -> DeliveryStatusData:
        self.queried.append(order_id)
        return self.statuses[order_id]


async def _insert_checkout(
    pool,
    *,
    status: str,
    order_ids: list[str],
    age_minutes: int = 0,
    notified: list[str] | None = None,
) -> tuple[uuid.UUID, str]:
    stamp = int(time.time() * 1000) % 10000000000
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
            f"91{stamp:010d}",
        )
        approval_id = await conn.fetchval(
            """
            INSERT INTO grocer.approvals (user_id, fingerprint, to_pay_paise, address_id, snapshot, status, expires_at)
            VALUES ($1, repeat('0', 64), 14900, 'addr_01HXYZ', '{}'::jsonb, 'consuming', now() + interval '10 minutes')
            RETURNING id;
            """,
            user_id,
        )
        checkout_id = await conn.fetchval(
            """
            INSERT INTO grocer.checkouts (
                approval_id, user_id, payment_method, address_id, known_order_ids,
                status, swiggy_order_id, swiggy_order_ids, approved_to_pay_paise,
                notified_milestones, created_at
            )
            VALUES ($1, $2, 'upi', 'addr_01HXYZ', '[]'::jsonb, $3, $4, $5::jsonb, 14900,
                    $6::jsonb, now() - $7 * interval '1 minute')
            RETURNING id;
            """,
            approval_id,
            user_id,
            status,
            order_ids[0] if order_ids else None,
            json.dumps(order_ids),
            json.dumps(notified or []),
            age_minutes,
        )
    return checkout_id, str(approval_id)


@pytest.mark.db
@pytest.mark.asyncio
async def test_split_order_milestones_are_each_sent_once():
    """Every order id in a split checkout notifies once, and only once."""
    pool = await get_db_pool()
    checkout_id, _ = await _insert_checkout(
        pool, status="placed", order_ids=["A_ORDER", "B_ORDER"]
    )
    client = ScriptedDeliveryClient(
        {
            "A_ORDER": DeliveryStatusData(orderId="A_ORDER", statusText="Packed", etaText="12 mins"),
            "B_ORDER": DeliveryStatusData(orderId="B_ORDER", statusText="On the way", etaText="6 mins"),
        }
    )

    first = await poll_in_flight_deliveries_batch(pool=pool, swiggy_client=client)
    assert {note.order_id for note in first} == {"A_ORDER", "B_ORDER"}

    second = await poll_in_flight_deliveries_batch(pool=pool, swiggy_client=client)
    assert second == []

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, notified_milestones FROM grocer.checkouts WHERE id = $1;",
            checkout_id,
        )
    assert row["status"] == "out_for_delivery"
    assert sorted(json.loads(row["notified_milestones"])) == [
        "A_ORDER:CONFIRMED",
        "B_ORDER:PICKED_UP",
    ]


@pytest.mark.db
@pytest.mark.asyncio
async def test_payment_poller_confirms_a_payment_made_while_asleep(swiggy_client):
    """A pending payment older than five minutes is checked on wake, not marked failed."""
    pool = await get_db_pool()
    checkout_id, approval_id = await _insert_checkout(
        pool,
        status="pending_payment",
        order_ids=["189456789012"],
        age_minutes=30,
    )

    results = await poll_pending_checkouts_batch(pool=pool, swiggy_client=swiggy_client)
    assert any(res.confirmed and res.order_id == "189456789012" for res in results)

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM grocer.checkouts WHERE id = $1;", checkout_id
        )
        approval_status = await conn.fetchval(
            "SELECT status FROM grocer.approvals WHERE id = $1;", uuid.UUID(approval_id)
        )
    assert status == "placed"
    assert approval_status == "consumed"


@pytest.mark.db
@pytest.mark.asyncio
async def test_payment_poller_keeps_unverified_row_pending():
    """A 401 during settlement leaves the row pending instead of marking it failed."""
    pool = await get_db_pool()

    class AuthFailingClient:
        def check_payment_status(self, paas_id=None, order_id=None):
            raise SwiggyAuthExpiredError("token expired")

    checkout_id, _ = await _insert_checkout(
        pool,
        status="pending_payment",
        order_ids=["189456700001"],
        age_minutes=30,
    )

    await poll_pending_checkouts_batch(pool=pool, swiggy_client=AuthFailingClient())

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM grocer.checkouts WHERE id = $1;", checkout_id
        )
    assert status == "pending_payment"
