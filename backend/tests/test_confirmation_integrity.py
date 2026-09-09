"""Basket-bound, one-time, concurrent checkout confirmation tests."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.session import ConversationState, OrchestratorSessionStore


class CountingCheckoutAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.checkout_attempts = 0

    async def checkout(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.checkout_attempts += 1
        await asyncio.sleep(0.01)
        return await super().checkout(*args, **kwargs)


async def _ready_basket(
    adapter: CountingCheckoutAdapter,
) -> tuple[GrocerOrchestrator, OrchestratorSessionStore, str, str, str]:
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    session_id = f"session-{uuid.uuid4()}"
    customer_id = f"customer-{uuid.uuid4()}"
    result = await orchestrator.handle_turn(
        session_id=session_id,
        customer_id=customer_id,
        message="get 1L milk",
    )
    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert result.basket_summary is not None
    assert result.basket_summary.confirmation_nonce
    return (
        orchestrator,
        store,
        session_id,
        result.basket_summary.confirmation_nonce,
        result.basket_summary.selected_payment_method,
    )


@pytest.mark.asyncio
async def test_wrong_confirmation_nonce_never_reaches_checkout() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, _store, session_id, _nonce, _method = await _ready_basket(adapter)

    result = await orchestrator.handle_confirm(
        session_id=session_id,
        explicit_confirmation=True,
        confirmation_nonce="wrong-nonce",
        payment_method="COD",
    )

    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert adapter.checkout_attempts == 0


@pytest.mark.asyncio
async def test_missing_confirmation_proof_never_reaches_checkout() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, _store, session_id, _nonce, method = await _ready_basket(adapter)

    with pytest.raises(UnconfirmedCheckoutError):
        await orchestrator.handle_confirm(
            session_id=session_id,
            payment_method=method,
        )

    assert adapter.checkout_attempts == 0


@pytest.mark.asyncio
async def test_expired_confirmation_never_reaches_checkout() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, store, session_id, nonce, method = await _ready_basket(adapter)
    session = store.get(session_id)
    assert session is not None and session.pending_confirmation is not None
    session.pending_confirmation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    result = await orchestrator.handle_confirm(
        session_id=session_id,
        payment_method=method,
        explicit_confirmation=True,
        confirmation_nonce=nonce,
    )

    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert "CONFIRMATION_REJECTED" in result.events
    assert adapter.checkout_attempts == 0


@pytest.mark.asyncio
async def test_confirmation_is_bound_to_presented_payment_method() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, _store, session_id, nonce, _method = await _ready_basket(adapter)

    result = await orchestrator.handle_confirm(
        session_id=session_id,
        explicit_confirmation=True,
        confirmation_nonce=nonce,
        payment_method="COD",
    )

    assert result.conversation_state == ConversationState.NEEDS_DECISION
    assert result.basket_summary is None
    assert "PAYMENT_METHOD_UNAVAILABLE" in result.events
    assert result.payment_options
    assert all(option.method != "COD" for option in result.payment_options)
    assert adapter.checkout_attempts == 0


class NoPaymentOptionsAdapter(CountingCheckoutAdapter):
    async def get_payment_options(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return []


@pytest.mark.asyncio
async def test_no_provider_payment_option_never_offers_checkout() -> None:
    adapter = NoPaymentOptionsAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    result = await orchestrator.handle_turn(
        session_id="no-payment-options",
        customer_id="customer",
        message="get 1L milk",
    )

    assert result.conversation_state == ConversationState.FAILED
    assert result.basket_summary is None
    assert "PAYMENT_OPTIONS_UNAVAILABLE" in result.events
    assert adapter.checkout_attempts == 0


@pytest.mark.asyncio
async def test_confirmation_message_shows_every_available_approval_bound_fact() -> None:
    result = await GrocerOrchestrator(
        commerce_adapter=CountingCheckoutAdapter(),
        session_store=OrchestratorSessionStore(),
    ).handle_turn("visible-basket", "customer", "get 1L milk")

    assert result.basket_summary is not None
    for label in (
        "Items:",
        "Delivery:",
        "Packaging:",
        "Discount:",
        "Total:",
        "Address:",
        "Payment:",
    ):
        assert label in result.user_message
    assert result.basket_summary.items[0].name in result.user_message
    assert result.basket_summary.selected_payment_option_label in result.user_message


@pytest.mark.asyncio
async def test_material_price_change_requires_new_confirmation() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, _store, session_id, nonce, method = await _ready_basket(adapter)
    adapter.inject_price_change("SPIN-MILK-1L", 80)

    result = await orchestrator.handle_confirm(
        session_id=session_id,
        explicit_confirmation=True,
        confirmation_nonce=nonce,
        payment_method=method,
    )

    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert result.requires_confirmation is True
    assert result.basket_summary is not None
    assert result.basket_summary.grand_total != 101
    assert result.basket_summary.confirmation_nonce != nonce
    assert adapter.checkout_attempts == 0


@pytest.mark.asyncio
async def test_material_fee_change_requires_new_confirmation() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, store, session_id, nonce, method = await _ready_basket(adapter)
    session = store.get(session_id)
    assert session is not None and session.cart_id is not None
    cart = await adapter.get_cart(session.cart_id)
    cart.packaging_fee += 7
    cart.grand_total += 7

    result = await orchestrator.handle_confirm(
        session_id=session_id,
        explicit_confirmation=True,
        confirmation_nonce=nonce,
        payment_method=method,
    )

    assert result.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert adapter.checkout_attempts == 0


@pytest.mark.asyncio
async def test_same_confirmation_is_consumed_once_sequentially() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, _store, session_id, nonce, method = await _ready_basket(adapter)

    first = await orchestrator.handle_confirm(
        session_id=session_id,
        explicit_confirmation=True,
        confirmation_nonce=nonce,
        payment_method=method,
    )
    second = await orchestrator.handle_confirm(
        session_id=session_id,
        explicit_confirmation=True,
        confirmation_nonce=nonce,
        payment_method=method,
    )

    assert first.conversation_state == ConversationState.ORDERED
    assert second.conversation_state == ConversationState.ORDERED
    assert adapter.checkout_attempts == 1
    assert second.order_id == first.order_id


@pytest.mark.asyncio
async def test_concurrent_confirmation_reaches_checkout_once() -> None:
    adapter = CountingCheckoutAdapter()
    orchestrator, _store, session_id, nonce, method = await _ready_basket(adapter)

    first, second = await asyncio.gather(
        orchestrator.handle_confirm(
            session_id=session_id,
            explicit_confirmation=True,
            confirmation_nonce=nonce,
            payment_method=method,
        ),
        orchestrator.handle_confirm(
            session_id=session_id,
            explicit_confirmation=True,
            confirmation_nonce=nonce,
            payment_method=method,
        ),
    )

    assert adapter.checkout_attempts == 1
    assert first.order_id == second.order_id
    assert first.conversation_state == second.conversation_state == ConversationState.ORDERED
