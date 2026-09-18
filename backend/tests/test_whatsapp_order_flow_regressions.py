"""Regression tests verifying the 5 critical WhatsApp order flow invariants.

1. Phone number normalization & customer identity parity (Web OAuth vs WhatsApp webhook).
2. Elimination of silent address defaulting (no addresses[0] fallback on non-address input).
3. Intent blackboard memory accumulation across multi-turn messages (no wipe of previous items).
4. Strict rejection of empty / ₹0 carts from confirmation and checkout.
5. Recovery candidate score clamping (score <= 1.0) and category affinity.
"""
from __future__ import annotations

import hashlib
import hmac
import pytest

from datetime import datetime, timedelta, timezone

from backend.channels.models import ChannelType
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.config import settings
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem, CommerceCart, DeliveryAddress
from backend.intent.models import IntentContract, IntentItem
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.recovery import RecoveryEngine
from backend.intent.session import (
    ConfirmationSnapshot,
    ConversationState,
    OrchestratorSession,
    OrchestratorSessionStore,
    PendingAddressChoice,
)
from backend.intent.stages.items_stage import _is_fresh_request, _merge_contracts
from backend.intent.verifier import IntentVerifier, VerificationStatus, ViolationCode


# ---------------------------------------------------------------------------
# 1. Phone number normalization and parity
# ---------------------------------------------------------------------------

def test_phone_number_hash_parity_between_web_and_whatsapp() -> None:
    """Web login (10-digit) and WhatsApp webhook (12-digit with 91) must yield identical customer IDs."""
    adapter = WhatsAppChannelAdapter(app_secret="test_secret_123")
    raw_10_digit = "9876543210"
    raw_12_digit = "919876543210"
    raw_plus_12 = "+919876543210"
    raw_with_spaces = "+91 98765 43210"

    id_10 = adapter.map_sender_to_customer_id(raw_10_digit)
    id_12 = adapter.map_sender_to_customer_id(raw_12_digit)
    id_plus = adapter.map_sender_to_customer_id(raw_plus_12)
    id_spaces = adapter.map_sender_to_customer_id(raw_with_spaces)

    assert id_10 == id_12 == id_plus == id_spaces
    assert id_10.startswith("cust_wa_")


# ---------------------------------------------------------------------------
# 2. Rejection of silent address defaulting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_matching_address_input_does_not_default_to_first_address() -> None:
    """Typing unrecognized input or item names at address prompt must NEVER default to addresses[0]."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    session_id = "test-session-addr-no-default"
    customer_id = "cust-addr-test-1"

    from backend.integrations.commerce.mock_adapter import MOCK_ADDRESSES
    addr1 = MOCK_ADDRESSES[0]
    addr2 = MOCK_ADDRESSES[1]

    session = OrchestratorSession(
        session_id=session_id,
        customer_id=customer_id,
        conversation_state=ConversationState.NEEDS_DECISION,
        pending_address_choice=PendingAddressChoice(
            addresses=[addr1, addr2],
            request_message="Please pick an address",
        ),
    )
    store.save(session)

    # 1. Non-address gibberish: must re-prompt without selecting addr1
    res = await orchestrator.handle_address_choice(
        session_id=session_id,
        address_id="some completely random text",
    )
    assert res.conversation_state == ConversationState.NEEDS_DECISION
    assert "ADDRESS_CHOICE_UNMATCHED" in res.events
    assert "couldn't match 'some completely random text'" in res.user_message

    saved = store.get(session_id)
    assert saved.address_id is None
    assert saved.address_confirmed is False

    # 2. Item input like 'coca cola' at address prompt: must route to shopping/building, not select addr1
    res2 = await orchestrator.handle_address_choice(
        session_id=session_id,
        address_id="1 coca cola",
    )
    # Routed to handle_turn -> item handled
    saved2 = store.get(session_id)
    assert saved2.address_id is None or saved2.address_id != addr1.id
    assert "ADDRESS_SELECTED id=addr-1" not in res2.events


# ---------------------------------------------------------------------------
# 3. Intent contract blackboard memory accumulation across multi-turn
# ---------------------------------------------------------------------------

def test_multi_turn_blackboard_accumulation() -> None:
    """Adding a new item must not wipe previously accumulated items on the contract."""
    contract_turn1 = IntentContract(
        session_id="sess-multi",
        goal="groceries",
        items=[IntentItem(name="vicks vaporub", quantity=5, unit="pcs")],
    )

    contract_turn2 = IntentContract(
        session_id="sess-multi",
        goal="groceries",
        items=[IntentItem(name="coca cola", quantity=1, unit="can")],
    )

    # Merging without an explicit reset phrase must accumulate
    merged = _merge_contracts(contract_turn1, contract_turn2, message="and 1 coca cola")
    assert len(merged.items) == 2
    item_names = {it.name.lower() for it in merged.items}
    assert "vicks vaporub" in item_names
    assert "coca cola" in item_names

    # Explicit reset phrase MUST reset
    reset_contract = IntentContract(
        session_id="sess-multi",
        goal="groceries",
        items=[IntentItem(name="milk", quantity=1, unit="L")],
    )
    merged_reset = _merge_contracts(merged, reset_contract, message="clear cart and get milk")
    assert len(merged_reset.items) == 1
    assert merged_reset.items[0].name == "milk"


def test_is_fresh_request_only_on_explicit_reset_keywords() -> None:
    """Verify common ordering phrases are NOT treated as fresh resets."""
    assert _is_fresh_request("clear cart") is True
    assert _is_fresh_request("start over") is True
    assert _is_fresh_request("reset") is True

    # Everyday phrasing must NEVER be treated as a reset
    assert _is_fresh_request("coca cola") is False
    assert _is_fresh_request("need 1 coke") is False
    assert _is_fresh_request("get 2 bread") is False
    assert _is_fresh_request("buy eggs") is False


# ---------------------------------------------------------------------------
# 4. Strict rejection of empty / ₹0 carts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_cart_strictly_blocked_from_confirmation_and_checkout() -> None:
    """Empty cart with ₹0 total must never reach AWAITING_CONFIRMATION or execute checkout."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    session_id = "sess-empty-cart-test"
    customer_id = "cust-empty-1"
    contract = IntentContract(session_id=session_id, goal="groceries", items=[])
    empty_cart = CommerceCart(cart_id="empty-cart-1", items=[], grand_total=0.0)

    session = OrchestratorSession(
        session_id=session_id,
        customer_id=customer_id,
        conversation_state=ConversationState.BUILDING,
        cart_id=empty_cart.cart_id,
        intent_contract=contract,
    )
    store.save(session)

    # 1. Orchestrator _make_awaiting_confirmation refuses empty cart
    res = await orchestrator._make_awaiting_confirmation(
        session=session,
        contract=contract,
        cart=empty_cart,
        recovery_notes=[],
        events=[],
    )
    assert res.conversation_state == ConversationState.BUILDING
    assert "EMPTY_CART_CONFIRMATION_BLOCKED" in res.events
    assert "empty" in res.user_message.lower()

    # 2. Verifier checkout gate rejects empty cart
    verifier = IntentVerifier()
    v_result = verifier.verify_checkout(contract, empty_cart, explicit_confirmation=True)
    assert v_result.status == VerificationStatus.FAIL
    assert any(v.violation_code == ViolationCode.EMPTY_CART for v in v_result.violations)

    # 3. Direct handle_confirm call raises UnconfirmedCheckoutError if cart is empty
    session.conversation_state = ConversationState.AWAITING_CONFIRMATION
    session.pending_confirmation = ConfirmationSnapshot(
        nonce="test-nonce",
        fingerprint="dummy",
        payment_method="UPI",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    store.save(session)

    with pytest.raises(UnconfirmedCheckoutError, match="empty basket"):
        await orchestrator.handle_confirm(
            session_id=session_id,
            explicit_confirmation=True,
            confirmation_nonce="test-nonce",
        )


# ---------------------------------------------------------------------------
# 5. Recovery candidate score clamping
# ---------------------------------------------------------------------------

def test_recovery_candidate_score_never_exceeds_one() -> None:
    """Candidate scores in min_order recovery must not exceed 1.0 (Pydantic validator)."""
    from backend.integrations.commerce.models import CommerceProductItem, ProductVariant

    cart = CommerceCart(
        cart_id="cart-min-order",
        items=[
            CartItem(
                spin_id="spin-1",
                sku_id="sku-1",
                name="Potato Chips",
                pack_size="50 g",
                unit_price=20.0,
                quantity=1,
                total_price=20.0,
                category="snacks",
            )
        ],
        subtotal=20.0,
        delivery_fee=30.0,
        grand_total=50.0,
        min_order_threshold=100.0,  # Shortfall = 50.0
    )
    contract = IntentContract(
        session_id="s",
        goal="snacks",
        items=[IntentItem(name="chips", quantity=1, unit="pack", category="snacks")],
    )
    engine = RecoveryEngine()

    catalog = [
        CommerceProductItem(
            product_id="prod-coke",
            name="Coca Cola 750ml",
            category="snacks",
            variants=[
                ProductVariant(
                    spin_id="spin-coke-1",
                    name="Coca Cola 750ml",
                    pack_size="750 ml",
                    price=50.0,
                    mrp=50.0,
                    in_stock=True,
                )
            ],
        )
    ]

    outcome = engine._handle_min_order_failure(
        contract=contract,
        cart=cart,
        available_products=catalog,
        attempt_number=1,
    )
    assert outcome is not None
    assert len(outcome.candidates_for_user) > 0
    for candidate in outcome.candidates_for_user:
        assert 0.0 <= candidate.score <= 1.0


# ---------------------------------------------------------------------------
# 6. Packaging format slot extraction & variant ranking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_packaging_format_can_prioritized_over_multipack() -> None:
    """Requesting '1 coke can only' extracts can packaging and ranks single can over 2L multipack."""
    from backend.intent.parser import IntentParser
    from backend.intent.stages.items_stage import _search_and_pick
    from backend.integrations.commerce.models import CommerceProductItem, ProductVariant

    parser = IntentParser()
    contract = parser.parse("1 coke can only", session_id="test-sess")
    assert len(contract.items) == 1
    coke_item = contract.items[0]
    assert coke_item.quantity == 1.0
    assert coke_item.unit == "can" or coke_item.pack_size_preference == "can"

    multipack_2l = CommerceProductItem(
        product_id="coke-multi-2l",
        name="Coke Zero Pet*8 Mp",
        category="beverages",
        variants=[
            ProductVariant(
                spin_id="coke-mp-1",
                name="Coke Zero Pet*8 Mp (2 ltr)",
                pack_size="2 ltr",
                price=144.0,
                mrp=144.0,
                in_stock=True,
            )
        ],
    )
    single_can = CommerceProductItem(
        product_id="coke-can-300",
        name="Coca-Cola Original Taste Can",
        category="beverages",
        variants=[
            ProductVariant(
                spin_id="coke-can-1",
                name="Coca-Cola Can (300 ml)",
                pack_size="300 ml",
                price=40.0,
                mrp=40.0,
                in_stock=True,
            )
        ],
    )

    class _Port(MockCommerceAdapter):
        async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
            return [multipack_2l, single_can]

    port = _Port()
    picked = await _search_and_pick(port, "addr-1", coke_item)
    assert picked is not None
    assert picked.spin_id == "coke-can-1"
    assert picked.quantity == 1
    assert coke_item.resolved_meaning is not None


# ---------------------------------------------------------------------------
# 7. Universal Intent Interception at address stage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_item_modification_at_address_stage_clears_pending_and_stays_building() -> None:
    """Sending '1 coke can only' while pending address choice must NOT select address."""
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    session_id = "test-session-intent-intercept"
    customer_id = "cust-intercept-1"

    from backend.integrations.commerce.mock_adapter import MOCK_ADDRESSES
    addr1 = MOCK_ADDRESSES[0]

    session = OrchestratorSession(
        session_id=session_id,
        customer_id=customer_id,
        conversation_state=ConversationState.NEEDS_DECISION,
        address_id=addr1.id,  # cached preliminary address
        pending_address_choice=PendingAddressChoice(
            addresses=[addr1],
            request_message="Please pick an address",
        ),
    )
    store.save(session)

    # Send item modification text
    res = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="1 coke can only",
    )

    # Must clear pending address choice and add Coke to cart rather than selecting address
    assert res.basket_summary is not None
    assert any("coke" in it.name.lower() for it in res.basket_summary.items)
    saved = store.get(session_id)
    assert saved.pending_address_choice is None


# ---------------------------------------------------------------------------
# 8. Channel address selection eliminates NameError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_base_channel_no_name_error_on_address_selection() -> None:
    """Address selection in BaseChannelAdapter must not throw NameError for _customer_saved_addresses."""
    from unittest.mock import AsyncMock
    from backend.channels.whatsapp import WhatsAppChannelAdapter
    from backend.channels.models import NormalizedIncomingMessage
    from backend.intent.orchestrator import GrocerOrchestrator
    from backend.intent.session import default_session_store, OrchestratorSession, ConversationState, PendingAddressChoice
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter, MOCK_ADDRESSES

    adapter = MockCommerceAdapter()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=default_session_store)
    channel = WhatsAppChannelAdapter(app_secret="test_secret_123")
    channel.send_response = AsyncMock(return_value=True)

    customer_id = channel.map_sender_to_customer_id("919876543210")
    session_id = channel.get_or_create_session_id(customer_id)
    session = OrchestratorSession(
        session_id=session_id,
        customer_id=customer_id,
        conversation_state=ConversationState.NEEDS_DECISION,
        pending_address_choice=PendingAddressChoice(
            addresses=MOCK_ADDRESSES[:2],
            request_message="Please pick an address",
        ),
    )
    default_session_store.save(session)

    incoming = NormalizedIncomingMessage(
        sender_id="919876543210",
        message_id="msg-test-1",
        text="1",
        interactive_id="address:addr-bandra-1",
    )

    # This call must not raise NameError: name '_customer_saved_addresses' is not defined
    res = await channel.dispatch(incoming, orchestrator)
    assert res is not None
    assert res.recipient_id == "919876543210"

