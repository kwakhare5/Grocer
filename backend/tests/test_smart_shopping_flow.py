"""Tests for the Smart 4-Stage Conversational Shopping Flow.

Covers:
1. Smart payment method grouping (collapsing 11 gateways into clean categories).
2. Transparent receipt math and fee reconciliation (Fees & Taxes line, purged debug notes).
3. Human address badge formatting.
4. Conversational item swapping ("make it jim jam", "replace X with Y").
5. Conversational item removal ("remove milk", "drop bread").
6. Natural affirmation verbs ("ok", "haan", "done", "sure", "kardo").
7. Payment choice non-trapping behavior.
"""
from __future__ import annotations

import pytest

from backend.channels.base import BaseChannelAdapter
from backend.channels.models import ChannelType, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItem,
    CartItemUpdate,
    CommerceCart,
    CommerceProductItem,
    DeliveryAddress,
    PaymentOption,
    ProductVariant,
)
from datetime import datetime, timezone

from backend.intent.models import IntentContract, IntentItem
from backend.intent.orchestrator import (
    GrocerOrchestrator,
    _detect_removal_request,
    _detect_swap_request,
    _display_address,
    _group_payment_options,
    _msg_confirmation_basket,
)
from backend.intent.session import (
    BasketItem,
    BasketSummary,
    ConversationState,
    OrchestratorSessionStore,
    PendingPaymentChoice,
)


# ---------------------------------------------------------------------------
# 1. Payment Categorization Tests
# ---------------------------------------------------------------------------

def test_group_payment_options_collapses_raw_gateways() -> None:
    raw_11 = [
        PaymentOption(method="UPI", label="Google Pay", id="GPAY_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="PhonePe UPI", id="PHONEPE_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="Paytm UPI", id="PAYTM_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="BHIM", id="BHIM_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="CRED UPI", id="CRED_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="super.money", id="SUPER_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="FamApp UPI", id="FAMAPP_INTENT", kind="intent"),
        PaymentOption(method="UPI", label="Pay with QR", id="QR", kind="qr"),
        PaymentOption(method="Cash", label="Pay on delivery", id="COD"),
        PaymentOption(method="SwiggyPay", label="Swiggy Money", id="SWIGGY_MONEY"),
        PaymentOption(method="Cash", label="Cash on Delivery", id="CASH"),
    ]

    grouped = _group_payment_options(raw_11)

    # Must collapse to at most 3 or 4 smart consumer options
    assert len(grouped) <= 4
    labels = [opt.label for opt in grouped]
    assert any("UPI" in l for l in labels)
    assert any("Pay on Delivery" in l for l in labels)
    assert any("Net Banking" in l or "Wallet" in l or "Swiggy" in l for l in labels)


def test_group_payment_options_preserves_short_lists() -> None:
    short_3 = [
        PaymentOption(method="UPI", label="Google Pay", id="gpay"),
        PaymentOption(method="UPI", label="PhonePe", id="phonepe"),
        PaymentOption(method="Cash", label="Cash", id="cash"),
    ]
    # Short lists (<=4) are preserved so existing contract regression tests pass
    assert _group_payment_options(short_3) == short_3


# ---------------------------------------------------------------------------
# 2. Receipt Math & Fee Reconciliation Tests
# ---------------------------------------------------------------------------

def test_fee_reconciliation_math_is_transparent() -> None:
    basket = BasketSummary(
        session_id="test-session",
        items=[
            BasketItem(spin_id="SPIN-1", name="Sunfeast Nice Biscuits", quantity=3, unit_price=9.0, line_total=27.0, pack_size="64 g"),
            BasketItem(spin_id="SPIN-2", name="Amul Lactose Free Milk", quantity=5, unit_price=26.0, line_total=130.0, pack_size="250 ml"),
        ],
        item_total=157.0,
        delivery_fee=0.0,
        packaging_fee=0.0,
        discount=0.0,
        grand_total=178.0,  # ₹21 extra handling/platform fees from Swiggy
        address_display="Home (Nashik)",
        selected_payment_method="UPI",
        selected_payment_option_label="BHIM",
        confirmation_nonce="nonce_test_123",
        confirmation_expires_at=datetime.now(timezone.utc),
        interpretation_notes=["I found biscuit sold as 64 g retail packs..."],
    )

    msg = _msg_confirmation_basket(basket)

    # 1. Extra fees must be explicitly itemized
    assert "Fees & Taxes: ₹21" in msg
    assert "Items: ₹157" in msg
    assert "Total: ₹178" in msg
    # 2. Leaking robotic interpretation debug notes must be purged
    assert "Interpretation:" not in msg
    assert "I found biscuit sold as 64 g" not in msg


# ---------------------------------------------------------------------------
# 3. Human Address Formatting Tests
# ---------------------------------------------------------------------------

def test_display_address_clean_badge() -> None:
    addr = DeliveryAddress(
        id="ctg57m6bbkmgsasadhqg",
        label="Home",
        street="Flat 402, Shanti Heights",
        city="Nashik",
        postal_code="422005",
    )
    displayed = _display_address(addr)
    assert displayed == "Home (Nashik)"
    assert "ctg57m6bbkmgsasadhqg" not in displayed


# ---------------------------------------------------------------------------
# 4. Conversational Swap & Removal Regex Tests
# ---------------------------------------------------------------------------

def test_detect_swap_requests() -> None:
    assert _detect_swap_request("make it jim jam") == (None, "jim jam")
    assert _detect_swap_request("switch to amul taaza") == (None, "amul taaza")
    assert _detect_swap_request("replace nice with jim jam") == ("nice", "jim jam")
    assert _detect_swap_request("change biscuits to jim jam") == ("biscuits", "jim jam")
    assert _detect_swap_request("instead of nice, make it jim jam") == ("nice", "jim jam")
    assert _detect_swap_request("jim jam instead") == (None, "jim jam")
    assert _detect_swap_request("get 1L milk") is None


def test_detect_removal_requests() -> None:
    assert _detect_removal_request("remove milk") == "milk"
    assert _detect_removal_request("drop the biscuits") == "biscuits"
    assert _detect_removal_request("don't want milk") == "milk"
    assert _detect_removal_request("delete 2") == "2"
    assert _detect_removal_request("add bread") is None


# ---------------------------------------------------------------------------
# 5. Live Conversational Item Swapping Integration Test
# ---------------------------------------------------------------------------

class SwapTestAdapter(MockCommerceAdapter):
    """Adapter with biscuits, milk, and jim jam in its catalog."""

    def __init__(self) -> None:
        super().__init__()
        self._jim_jam_variant = ProductVariant(
            spin_id="SPIN-JIM-JAM-100G",
            sku_id="SKU-JIM-JAM",
            name="Britannia Treat Jim Jam Biscuits",
            pack_size="100 g",
            price=35.0,
            mrp=40.0,
            in_stock=True,
        )
        self._jim_jam_product = CommerceProductItem(
            product_id="PROD-JIM-JAM",
            name="Britannia Treat Jim Jam Biscuits",
            category="Snacks & Munchies",
            variants=[self._jim_jam_variant],
        )
        self._catalog_by_spin["SPIN-JIM-JAM-100G"] = (self._jim_jam_product, self._jim_jam_variant)

    async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
        if "jim" in query.lower() or "jam" in query.lower():
            return [self._jim_jam_product]
        return await super().search_products(address_id, query)


@pytest.mark.asyncio
async def test_conversational_item_swap_in_orchestrator() -> None:
    adapter = SwapTestAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    # Turn 1: Build basket with biscuits and milk
    r1 = await orchestrator.handle_turn(
        "sess-swap-1",
        "cust-1",
        "buy 1 milk and 1 bread",
        address_id="addr-1",
    )
    assert r1.conversation_state == ConversationState.AWAITING_CONFIRMATION
    item_names = [it.name.lower() for it in r1.basket_summary.items]
    assert any("milk" in name for name in item_names)
    assert any("bread" in name for name in item_names)

    # Turn 2: User says "make it jim jam" -> should replace bread or milk
    r2 = await orchestrator.handle_turn(
        "sess-swap-1",
        "cust-1",
        "make it jim jam",
        address_id="addr-1",
    )
    assert r2.conversation_state == ConversationState.AWAITING_CONFIRMATION
    updated_names = [it.name.lower() for it in r2.basket_summary.items]
    assert any("jim jam" in name for name in updated_names)


@pytest.mark.asyncio
async def test_conversational_item_removal_in_orchestrator() -> None:
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    # Turn 1: Build basket with milk and bread
    r1 = await orchestrator.handle_turn(
        "sess-rem-1",
        "cust-1",
        "buy 1 milk and 1 bread",
        address_id="addr-1",
    )
    assert len(r1.basket_summary.items) == 2

    # Turn 2: User says "remove milk"
    r2 = await orchestrator.handle_turn(
        "sess-rem-1",
        "cust-1",
        "remove milk",
        address_id="addr-1",
    )
    assert r2.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert len(r2.basket_summary.items) == 1
    assert "milk" not in r2.basket_summary.items[0].name.lower()


class SkuEnforcingAdapter(MockCommerceAdapter):
    """Adapter that strictly requires sku_id on update_cart just like Swiggy MCP."""
    async def update_cart(
        self,
        items: list[CartItemUpdate],
        cart_id: Optional[str] = None,
        address_id: Optional[str] = None,
    ) -> CommerceCart:
        for it in items:
            if not it.sku_id:
                raise ValueError("Cart update requires a catalog SKU ID for every item.")
        return await super().update_cart(items, cart_id=cart_id, address_id=address_id)


@pytest.mark.asyncio
async def test_clarification_choice_forwards_sku_id_to_cart_update() -> None:
    adapter = SkuEnforcingAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    from backend.intent.recovery import RecoveryCandidate
    from backend.intent.session import PendingClarification

    # Setup session in NEEDS_DECISION with a pending clarification having sku_id
    session = store.get_or_create("sess-sku-test", "cust-sku")
    session.conversation_state = ConversationState.NEEDS_DECISION
    candidate = RecoveryCandidate(
        spin_id="SPIN-MILK-500ML",
        sku_id="SKU-MILK-500ML",
        name="Amul Taaza 500ml",
        pack_size="500 ml",
        price=27.0,
        category="Dairy",
    )
    session.pending_clarification = PendingClarification(
        item_name="milk",
        candidates=[candidate],
        clarification_question="Which pack size?",
        intended_quantity=1,
    )
    # create intent contract
    contract = orchestrator._parse_intent("buy milk", session, [])
    session.intent_contract = contract
    store.save(session)

    # Call handle_choice
    result = await orchestrator.handle_choice(
        session_id="sess-sku-test",
        chosen_spin_id="SPIN-MILK-500ML",
        clarification_nonce=session.pending_clarification.nonce,
    )

    # SkuEnforcingAdapter would have thrown ValueError if sku_id was omitted
    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    updated_session = store.get("sess-sku-test")
    cart = await adapter.get_cart(updated_session.cart_id)
    assert any(ci.sku_id == "SKU-MILK-500ML" for ci in cart.items)


# ---------------------------------------------------------------------------
# 6. Natural Affirmations Verification
# ---------------------------------------------------------------------------

class DummyChannel(BaseChannelAdapter):
    def __init__(self) -> None:
        super().__init__(ChannelType.WHATSAPP)

    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        return True


@pytest.mark.asyncio
async def test_natural_affirmations_trigger_confirmation() -> None:
    from backend.intent.session import default_session_store
    channel = DummyChannel()
    adapter = MockCommerceAdapter()
    store = default_session_store
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    customer_id = channel.map_sender_to_customer_id("+919876543210")
    session_id = channel.get_or_create_session_id(customer_id)

    # Prepare session in AWAITING_CONFIRMATION
    await orchestrator.handle_turn(
        session_id,
        customer_id,
        "get 1L milk",
        address_id="addr-1",
    )
    session = store.get(session_id)
    assert session.conversation_state == ConversationState.AWAITING_CONFIRMATION

    # Test that "ok" triggers checkout
    msg = NormalizedIncomingMessage(
        message_id="msg-confirm-1",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543210",
        text="ok",
        session_id=session_id,
    )
    res = await channel.dispatch(msg, orchestrator)
    assert res.conversation_state in (ConversationState.ORDERED, ConversationState.PAYMENT_PENDING)


@pytest.mark.asyncio
async def test_payment_choice_non_trapping_on_item_change() -> None:
    from backend.intent.session import default_session_store
    channel = DummyChannel()
    adapter = SwapTestAdapter()
    store = default_session_store
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    customer_id = channel.map_sender_to_customer_id("+919876543211")
    session_id = channel.get_or_create_session_id(customer_id)

    # 1. Build initial basket with milk and bread
    await orchestrator.handle_turn(
        session_id,
        customer_id,
        "buy 1 milk and 1 bread",
        address_id="addr-1",
    )
    session = store.get(session_id)
    assert session.conversation_state == ConversationState.AWAITING_CONFIRMATION

    # 2. Simulate asking for payment choice (NEEDS_DECISION with pending_payment_choice)
    options = [
        PaymentOption(method="UPI", label="Pay via UPI", kind="intent"),
        PaymentOption(method="Cash", label="Pay on Delivery", kind="pod"),
    ]
    session.conversation_state = ConversationState.NEEDS_DECISION
    session.pending_payment_choice = PendingPaymentChoice(
        nonce="nonce-pay-123",
        options=options,
        raw_options=options,
    )
    store.save(session)

    # 3. User types "make it jim jam" instead of selecting a payment option
    msg = NormalizedIncomingMessage(
        message_id="msg-swap-1",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543211",
        text="make it jim jam",
        session_id=session_id,
    )
    res = await channel.dispatch(msg, orchestrator)
    # Ensure it didn't trap the user with an error or payment prompt rejection
    assert res.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert "jim jam" in res.text.lower()


@pytest.mark.asyncio
async def test_channel_restores_customer_address_from_manager() -> None:
    from backend.intent.session import default_session_store
    from backend.intent.stages.address_stage import default_address_manager
    channel = DummyChannel()

    customer_id = channel.map_sender_to_customer_id("+919876543299")
    default_address_manager.save_address(customer_id, "addr-saved-nashik")

    try:
        session_id = channel.get_or_create_session_id(customer_id)
        session = default_session_store.get(session_id)
        assert session is not None
        assert session.address_id == "addr-saved-nashik"
    finally:
        default_address_manager._cache.pop(customer_id, None)
        default_address_manager._save_cache()


