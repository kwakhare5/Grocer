"""Layer 4 Verification Tests: Commerce Gateway, Product Policy & Physical Checkout Gate.

Verifies the 5 hard checkout locks:
1. Conversation state is AWAITING_CONFIRMATION
2. Dual confirmation check (user confirmed)
3. Budget limit check (grand total <= budget_limit)
4. Live cart fingerprint match (zero price drift or OOS silent changes)
5. Zero restricted medical products in basket (Swiggy Pharmacy aisle with OTC first-aid allowance)

Also verifies:
- 1-tap mobile UPI deep linking (upi://pay)
- Durable checkout attempt hold tracking (preventing double-charging)
"""
from __future__ import annotations

import pytest

from backend.agent.approval import cart_fingerprint
from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.product_policy import is_restricted_medical_product
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem


class DummyCheckoutAttemptStore:
    """In-memory attempt store matching PostgresCheckoutAttemptStore interface."""

    def __init__(self, block_customer_id: str | None = None) -> None:
        self.block_customer_id = block_customer_id
        self.started_attempts: list[dict] = []
        self.finished_attempts: list[tuple[str, dict]] = []

    async def start(
        self,
        customer_id: str,
        cart_id: str,
        address_id: str,
        fingerprint: str,
        total: float,
    ) -> str | None:
        if customer_id == self.block_customer_id:
            return None  # Unresolved hold exists
        attempt_id = f"attempt-{len(self.started_attempts) + 1}"
        self.started_attempts.append({
            "id": attempt_id,
            "customer_id": customer_id,
            "cart_id": cart_id,
            "address_id": address_id,
            "fingerprint": fingerprint,
            "total": total,
        })
        return attempt_id

    async def finish(self, attempt_id: str, result: dict) -> None:
        self.finished_attempts.append((attempt_id, result))


@pytest.mark.asyncio
async def test_checkout_gate_lock1_state_not_confirming_blocks_order():
    """Lock 1: Checkout blocked if conversation state is not AWAITING_CONFIRMATION."""
    adapter = MockCommerceAdapter()
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id="cart-1",
        address_id="addr-bandra-1",
        conversation_state="READY",
        is_user_confirmed=True,
    )
    assert res["success"] is False
    assert res["error"] == "STATE_NOT_CONFIRMING"


@pytest.mark.asyncio
async def test_checkout_gate_lock2_unconfirmed_user_blocks_order():
    """Lock 2: Checkout blocked if user has not explicitly confirmed."""
    adapter = MockCommerceAdapter()
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id="cart-1",
        address_id="addr-bandra-1",
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=False,
    )
    assert res["success"] is False
    assert res["error"] == "CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_checkout_gate_lock3_budget_exceeded_blocks_order():
    """Lock 3: Checkout blocked if grand total exceeds session budget limit."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-budget-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-BREAD-400G", name="Whole Wheat Bread 400g", pack_size="400 g", unit_price=50.0, quantity=3, total_price=150.0)
        ])
        cart = await adapter.get_cart()

    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=cart.address_id or "addr-bandra-1",
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        budget_inr=100.0,
    )
    assert res["success"] is False
    assert res["error"] == "BUDGET_EXCEEDED"
    assert res["grand_total"] > 100.0
    assert res["budget_inr"] == 100.0


@pytest.mark.asyncio
async def test_checkout_gate_lock3_invalid_budget_blocks_order():
    """Lock 3: Checkout blocked if budget limit is negative or non-finite."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-invalid-budget"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-BREAD-400G", name="Whole Wheat Bread 400g", pack_size="400 g", unit_price=50.0, quantity=1, total_price=50.0)
        ])
        cart = await adapter.get_cart()

    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=cart.address_id or "addr-bandra-1",
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        budget_inr=-20.0,
    )
    assert res["success"] is False
    assert res["error"] == "INVALID_BUDGET"


@pytest.mark.asyncio
async def test_checkout_gate_lock4_fingerprint_mismatch_blocks_order():
    """Lock 4: Checkout blocked if live cart fingerprint differs from approved fingerprint."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-drift-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-MILK-500ML", name="Amul Taaza Milk 500ml", pack_size="500 ml", unit_price=34.0, quantity=2, total_price=68.0)
        ])
        cart = await adapter.get_cart()

    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=cart.address_id or "addr-bandra-1",
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        expected_cart_fingerprint="tampered-or-stale-fingerprint-sha256",
    )
    assert res["success"] is False
    assert res["error"] == "CART_CHANGED"


@pytest.mark.asyncio
async def test_checkout_gate_lock5_restricted_pharmacy_item_blocks_order():
    """Lock 5: Checkout blocked if basket contains clinical pharmacy products."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-pharma-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-CROCIN-15TAB", name="Crocin Advance Paracetamol (15 Tablets)", pack_size="15 tabs", unit_price=32.0, quantity=1, total_price=32.0)
        ])
        cart = await adapter.get_cart()

    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=cart.address_id or "addr-bandra-1",
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
    )
    assert res["success"] is False
    assert res["error"] == "MEDICAL_PRODUCT_RESTRICTED"
    assert "Crocin Advance Paracetamol (15 Tablets)" in res["items"]


@pytest.mark.asyncio
async def test_checkout_gate_lock5_otc_first_aid_allowed():
    """Lock 5: Checkout permitted for OTC first aid (Band-Aids, Vicks, etc.) even under Pharmacy category."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-first-aid-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-BANDAID-10STRIPS", name="Hansaplast Band-Aid Strips (10 Strips)", pack_size="10 strips", unit_price=30.0, quantity=1, total_price=30.0),
            CartItem(spin_id="SPIN-VICKS-25ML", name="Vicks VapoRub Relief Balm 25ml", pack_size="25 ml", unit_price=65.0, quantity=1, total_price=65.0),
        ])
        cart = await adapter.get_cart()

    addr = cart.address_id or "addr-bandra-1"
    valid_fp = cart_fingerprint(cart, addr)
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=addr,
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        expected_cart_fingerprint=valid_fp,
    )
    assert res["success"] is True
    assert res["status"] == "PAYMENT_PENDING"


@pytest.mark.asyncio
async def test_checkout_gate_1tap_mobile_upi_deep_link():
    """UPI checkout generates direct 1-tap mobile upi://pay deep link."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-upi-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-BREAD-400G", name="Whole Wheat Bread 400g", pack_size="400 g", unit_price=50.0, quantity=2, total_price=100.0)
        ])
        cart = await adapter.get_cart()

    addr = cart.address_id or "addr-bandra-1"
    valid_fp = cart_fingerprint(cart, addr)
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=addr,
        payment_method="UPI",
        payment_option_kind="qr",
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        expected_cart_fingerprint=valid_fp,
    )
    assert res["success"] is True
    assert res["status"] == "PAYMENT_PENDING"
    assert res["upi_intent_url"] is not None
    assert res["upi_intent_url"].startswith("upi://pay?")
    assert "pa=swiggy@icici" in res["upi_intent_url"]
    assert "pn=Swiggy" in res["upi_intent_url"]
    assert "am=" in res["upi_intent_url"]
    assert "tr=" in res["upi_intent_url"]


@pytest.mark.asyncio
async def test_checkout_gate_hold_tracking_unresolved_blocks_duplicate():
    """Durable hold tracking blocks duplicate checkout attempts for the same customer."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-hold-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-BREAD-400G", name="Whole Wheat Bread 400g", pack_size="400 g", unit_price=50.0, quantity=1, total_price=50.0)
        ])
        cart = await adapter.get_cart()

    addr = cart.address_id or "addr-bandra-1"
    attempt_store = DummyCheckoutAttemptStore(block_customer_id="cust-hold-test")
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=addr,
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        attempt_store=attempt_store,
        customer_id="cust-hold-test",
    )
    assert res["success"] is False
    assert res["error"] == "ATTEMPT_UNRESOLVED"


@pytest.mark.asyncio
async def test_checkout_gate_hold_tracking_lifecycle_success():
    """Attempt store starts attempt and finishes it upon successful checkout."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-lifecycle-test"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-MILK-500ML", name="Amul Taaza Milk 500ml", pack_size="500 ml", unit_price=34.0, quantity=2, total_price=68.0)
        ])
        cart = await adapter.get_cart()

    addr = cart.address_id or "addr-bandra-1"
    attempt_store = DummyCheckoutAttemptStore()
    valid_fp = cart_fingerprint(cart, addr)
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=addr,
        conversation_state="AWAITING_CONFIRMATION",
        is_user_confirmed=True,
        expected_cart_fingerprint=valid_fp,
        attempt_store=attempt_store,
        customer_id="cust-lifecycle-test",
    )
    assert res["success"] is True
    assert len(attempt_store.started_attempts) == 1
    assert len(attempt_store.finished_attempts) == 1
    attempt_id, result_payload = attempt_store.finished_attempts[0]
    assert attempt_id == "attempt-1"
    assert result_payload["success"] is True
    assert result_payload["order_id"] == res["order_id"]


@pytest.mark.asyncio
async def test_checkout_gate_all_5_locks_pass_cleanly():
    """All 5 checkout locks pass simultaneously on valid order."""
    adapter = MockCommerceAdapter()
    with adapter.customer_scope("cust-all-locks-pass"):
        await adapter.update_cart([
            CartItem(spin_id="SPIN-EGGS-6", name="Fresh Eggs 6s", pack_size="6 pcs", unit_price=55.0, quantity=1, total_price=55.0),
            CartItem(spin_id="SPIN-BREAD-400G", name="Whole Wheat Bread 400g", pack_size="400 g", unit_price=50.0, quantity=1, total_price=50.0),
            CartItem(spin_id="SPIN-BANDAID-10STRIPS", name="Hansaplast Band-Aid Strips (10 Strips)", pack_size="10 strips", unit_price=30.0, quantity=1, total_price=30.0),
        ])
        cart = await adapter.get_cart()

    addr = cart.address_id or "addr-bandra-1"
    valid_fp = cart_fingerprint(cart, addr)
    res = await execute_gated_checkout(
        commerce=adapter,
        cart_id=cart.cart_id or "cart-1",
        address_id=addr,
        payment_method="UPI",
        conversation_state="AWAITING_CONFIRMATION",  # Lock 1
        is_user_confirmed=True,                      # Lock 2
        budget_inr=300.0,                            # Lock 3 (cart total <= 300)
        expected_cart_fingerprint=valid_fp,          # Lock 4
        # Lock 5: Pharmacy item is Band-Aid (OTC first aid, allowed)
    )
    assert res["success"] is True
    assert res["status"] == "PAYMENT_PENDING"
    assert res["grand_total"] <= 300.0
    assert res["upi_intent_url"] is not None
    assert res["upi_intent_url"].startswith("upi://pay?")
