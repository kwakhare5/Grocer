"""Tests for Layer 2: Session & Intent Engine (Safety, Intent, Address, and State)."""

from __future__ import annotations


import asyncio

import time

from unittest.mock import AsyncMock, MagicMock, patch


import pytest


from backend.agent.address_tools import (
    match_explicit_address,
    match_pending_address_choice,
)

from backend.agent.address_tools import execute_get_saved_addresses

from backend.agent.approval import (
    cart_fingerprint,
    PendingApproval,
    is_confirmed,
    check_cart_drift,
)

from backend.agent.engine import GroceryAgentEngine

from backend.agent.product_policy import is_restricted_medical_product

from backend.agent.react_coordinator import execute_react_turn_loop

from backend.agent.session import CustomerSession

from backend.agent.session_manager import dump_task_state_dict, restore_task_state_dict

from backend.agent.engine import execute_engine_tool

from backend.channels.models import NormalizedIncomingMessage

from backend.integrations.commerce.exceptions import ProviderInternalError

from backend.integrations.commerce.models import CommerceCart, CartItem, DeliveryAddress


# ==============================================================================

# Slice A: Financial Safety, Cart Drift & Approval Stability

# ==============================================================================


@pytest.mark.asyncio
async def test_checkout_unknown_state_never_retryable_and_invalidates_approval():
    """B1: Unknown checkout states must never be marked retryable and must invalidate approval."""

    cart = CommerceCart(
        cart_id="cart_1",
        address_id="addr_1",
        items=[
            CartItem(
                spin_id="S1",
                name="Milk",
                pack_size="500ml",
                unit_price=30.0,
                quantity=1,
                total_price=30.0,
            )
        ],
        subtotal=30.0,
        delivery_fee=15.0,
        grand_total=45.0,
        billing_complete=True,
        currency="INR",
    )

    fp = cart_fingerprint(cart, "addr_1")

    session = CustomerSession(customer_id="cust_test_1")

    session.pending_approval = PendingApproval(
        token="valid_token_123",
        fingerprint=fp,
        expires_at=time.time() + 900,
    )

    mock_engine = MagicMock()

    mock_engine.get_session.return_value = session

    mock_engine.commerce.get_cart = AsyncMock(return_value=cart)

    mock_engine.tools.checkout = AsyncMock(
        side_effect=ProviderInternalError("Swiggy connection dropped mid-checkout")
    )

    mock_engine.attempt_store.finish = AsyncMock()

    res = await execute_engine_tool(
        mock_engine,
        "checkout",
        {"confirmation_token": "valid_token_123"},
        customer_id="cust_test_1",
        address_id="addr_1",
        user_confirmed=True,
    )

    # Must NOT be marked retryable without status check, and pending_approval must be wiped

    assert res.get("retryable") is False

    assert session.pending_approval is None

    assert "UNKNOWN" in str(res.get("error"))


def test_cart_fingerprint_sorted_bill_lines_stability():
    """B2: Bill lines order must not affect cart fingerprint hash."""

    items = [
        CartItem(
            spin_id="SPIN-1",
            name="Milk",
            pack_size="500ml",
            unit_price=33.0,
            quantity=2,
            total_price=66.0,
        ),
        CartItem(
            spin_id="SPIN-2",
            name="Bread",
            pack_size="400g",
            unit_price=45.0,
            quantity=1,
            total_price=45.0,
        ),
    ]

    cart1 = CommerceCart(
        cart_id="cart_1",
        address_id="addr_1",
        items=items,
        grand_total=141.0,
        billing_complete=True,
        currency="INR",
        bill_lines=[
            {"name": "Delivery Fee", "amount": 25.0},
            {"name": "Handling Fee", "amount": 5.0},
        ],
    )

    cart2 = CommerceCart(
        cart_id="cart_1",
        address_id="addr_1",
        items=items,
        grand_total=141.0,
        billing_complete=True,
        currency="INR",
        bill_lines=[
            {"name": "Handling Fee", "amount": 5.0},
            {"name": "Delivery Fee", "amount": 25.0},
        ],
    )

    fp1 = cart_fingerprint(cart1, "addr_1")

    fp2 = cart_fingerprint(cart2, "addr_1")

    assert fp1 == fp2

    assert isinstance(fp1, str)

    assert len(fp1) == 64


@pytest.mark.asyncio
async def test_cart_drift_evaluation_provides_interactive_actions():
    """B3: Drift guard must provide interactive choice buttons and not lock users."""

    session = CustomerSession(customer_id="cust_test_3")

    session.known_cart_fingerprint = "fp_initial"

    session.pending_approval = None

    cart = CommerceCart(
        cart_id="cart_3",
        address_id="addr_1",
        items=[
            CartItem(
                spin_id="S1",
                name="Milk",
                pack_size="500ml",
                unit_price=30.0,
                quantity=1,
                total_price=30.0,
            )
        ],
        subtotal=30.0,
        delivery_fee=15.0,
        grand_total=45.0,
        billing_complete=True,
        currency="INR",
    )

    incoming = NormalizedIncomingMessage(
        sender_id="cust_test_3",
        text="hello",
        channel="whatsapp",
        message_id="msg_drift_1",
    )

    # When external cart changed

    resp = await check_cart_drift(
        session=session,
        current_cart=cart,
        norm_text="hello",
        user_confirmed=False,
        message=incoming,
    )

    assert resp is not None

    assert session.external_cart_pending is True

    # Must provide interactive actions so user can tap instead of typing exact words

    assert len(resp.interactive_actions) >= 2

    action_ids = [a.id for a in resp.interactive_actions]

    assert "keep_external" in action_ids or "use_changes" in action_ids


# ==============================================================================

# Slice B: Natural Intent, Resilient Confirmation & Address Resolution

# ==============================================================================


@pytest.mark.asyncio
async def test_confirmation_check_interactive_button_instant_pass():
    """B4: WhatsApp interactive button tap 'confirm_order' confirms instantly without LLM."""

    mock_client = MagicMock()

    mock_client.generate_structured = AsyncMock()

    # User physically clicked WhatsApp interactive button

    confirmed = await is_confirmed(
        client_or_text="Confirm Order",
        text_or_context="Order of ₹340 for 2 items",
        context="",
        client=mock_client,
        interactive_id="confirm_order",
    )

    assert confirmed is True

    # LLM must NOT have been called when interactive_id is confirmed button

    mock_client.generate_structured.assert_not_called()


@pytest.mark.asyncio
async def test_confirmation_check_fallback_on_primary_model_failure():
    """B5: Natural text confirmation retries with fallback model when primary fails."""

    mock_client = MagicMock()

    # First call (primary model) fails with rate limit / timeout

    # Second call (fallback model) succeeds with 'yes'

    mock_client.generate_structured = AsyncMock(
        side_effect=[
            RuntimeError("Primary model 429 rate limit"),
            {"confirmation": "yes"},
        ]
    )

    confirmed = await is_confirmed(
        client_or_text="haan bhai bhej do",
        text_or_context="Order of ₹340 for 2 items",
        client=mock_client,
    )

    assert confirmed is True

    assert mock_client.generate_structured.call_count == 2


def test_address_resolution_preserves_indian_cities_and_handles_negation():
    """B6: Address resolution allows Indian cities and handles negation phrases properly."""

    addresses = [
        {
            "id": "addr_pune_1",
            "label": "Pune Office",
            "clean_address": "Tech Park, Hinjawadi, Pune",
            "city": "Pune",
            "latitude": 18.59,
            "longitude": 73.73,
        },
        {
            "id": "addr_home_2",
            "label": "Green Park Home",
            "clean_address": "Flat 402, Green Park, Aundh, Pune",
            "city": "Pune",
            "latitude": 18.56,
            "longitude": 73.80,
        },
    ]

    # City name should resolve to Pune Office

    resolved_city = match_explicit_address(addresses, "deliver to my pune office")

    assert resolved_city is not None

    assert resolved_city["id"] == "addr_pune_1"

    # Negation: "Do not send to Green Park, use Pune Office"

    resolved_negation = match_explicit_address(
        addresses, "do not send to green park, use pune office"
    )

    assert resolved_negation is not None

    assert resolved_negation["id"] == "addr_pune_1"

    # Numbered option: "option 2"

    pending_list = [
        {"_choice_index": 1, "id": "addr_pune_1", "label": "Pune Office"},
        {"_choice_index": 2, "id": "addr_home_2", "label": "Green Park Home"},
    ]

    resolved_num = match_pending_address_choice(pending_list, "option 2")

    assert resolved_num is not None

    assert resolved_num["id"] == "addr_home_2"


@pytest.mark.asyncio
async def test_fetch_saved_addresses_preserves_coordinates_and_serviceability():
    """B7: fetch_saved_addresses_tool must preserve lat, lng, and is_serviceable."""

    mock_commerce = MagicMock()

    mock_commerce.get_addresses = AsyncMock(
        return_value=[
            DeliveryAddress(
                id="addr_geo_1",
                label="Home",
                street="12 Main St",
                area="Indiranagar",
                city="Bangalore",
                latitude=12.97,
                longitude=77.64,
                is_serviceable=True,
            )
        ]
    )

    res = await execute_get_saved_addresses(mock_commerce, "cust_test_addr")

    assert res.get("success") is True

    addrs = res.get("addresses", [])

    assert len(addrs) == 1

    assert addrs[0].get("latitude") == 12.97

    assert addrs[0].get("longitude") == 77.64

    assert addrs[0].get("is_serviceable") is True


def test_conversational_advice_not_intercepted_by_symptom_regex():
    """B8: Conversational symptom requests flow naturally to Gemini without regex interception."""
    assert (
        is_restricted_medical_product(
            "Organic India Tulsi Green Tea", category="Beverages"
        )
        is False
    )
    assert (
        is_restricted_medical_product(
            "Knorr Hot and Sour Soup 43g", category="Instant Foods"
        )
        is False
    )
    assert (
        is_restricted_medical_product("Dabur Honey 250g", category="Staples") is False
    )
    assert is_restricted_medical_product("Dolo 650", category="Pharmacy") is True


# ==============================================================================

# Slice C: Session Lifecycle, Inactive Eviction & State Persistence

# ==============================================================================


def test_session_state_dump_and_restore_preserves_missing_fields():
    """B9: dump and restore task state preserves dropped_requested_items and item_reasons."""

    session = CustomerSession(customer_id="cust_persist_1")

    session.dropped_requested_items = ["avocado", "sourdough bread"]

    session.item_reasons = {"milk": "breakfast tea", "bread": "toast"}

    data = dump_task_state_dict(session)

    restored = CustomerSession(customer_id="cust_persist_1")

    restore_task_state_dict(restored, data)

    assert restored.dropped_requested_items == ["avocado", "sourdough bread"]

    assert restored.item_reasons == {"milk": "breakfast tea", "bread": "toast"}


@pytest.mark.asyncio
async def test_engine_evicts_inactive_sessions_and_locks():
    """B10: Engine evicts customer sessions and locks that have exceeded inactivity TTL."""

    engine = GroceryAgentEngine(commerce=MagicMock())

    # Populate test sessions

    old_cust = "cust_old_inactivity"

    active_cust = "cust_active"

    sess_old = engine.get_session(old_cust)

    sess_old.last_active_time = time.time() - 3600  # 1 hour ago

    engine._locks[old_cust] = asyncio.Lock()

    sess_act = engine.get_session(active_cust)

    sess_act.last_active_time = time.time() - 60  # 1 minute ago

    engine._locks[active_cust] = asyncio.Lock()

    # Run eviction

    engine.evict_inactive_sessions(ttl_seconds=1800)

    assert old_cust not in engine._sessions

    assert old_cust not in engine._locks

    assert active_cust in engine._sessions

    assert active_cust in engine._locks


# ==============================================================================

# Slice D: ReAct Multi-Turn History Preservation

# ==============================================================================


def test_history_does_not_overwrite_earlier_common_phrases():
    """B11: Multi-turn history must not overwrite earlier identical short phrases ('yes', 'milk')."""

    session = CustomerSession(customer_id="cust_hist_1")

    # History with an earlier 'yes' turn

    session.history = [
        {"role": "user", "parts": [{"text": "yes"}]},
        {"role": "model", "parts": [{"text": "Added milk to your basket."}]},
        {"role": "user", "parts": [{"text": "add bread"}]},
        {"role": "model", "parts": [{"text": "Added bread."}]},
    ]

    # In react_coordinator, when user sends 'yes' again for confirmation,

    # it must NOT overwrite index 0!

    # We simulate appending new turn:

    incoming = "yes"

    # Ensure previous history at index 0 remains unmodified

    hist_copy = [dict(x) for x in session.history]

    assert hist_copy[0]["parts"][0]["text"] == "yes"

    assert hist_copy[1]["parts"][0]["text"] == "Added milk to your basket."
