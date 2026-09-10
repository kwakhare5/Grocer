"""Regressions for independently confirmed provider-contract merge blockers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.integrations.commerce.exceptions import (
    CommerceError,
    ProviderAuthError,
    ProviderSessionRevokedError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    DeliveryAddress,
    DeliveryStatusResult,
    DeliveryTrackingStatus,
    PaymentOption,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.session import ConversationState, OrchestratorSessionStore


class ControlledSwiggyAdapter(SwiggyMCPAdapter):
    """Swiggy-typed adapter with deterministic, non-network commerce behavior."""

    def __init__(
        self,
        addresses: list[DeliveryAddress],
        *,
        address_error: Exception | None = None,
    ) -> None:
        super().__init__(auth_token="test-token")
        self._mock = MockCommerceAdapter()
        self._addresses = addresses
        self._address_error = address_error
        self.search_calls = 0
        self.update_calls = 0

    async def get_addresses(self, customer_id: str) -> list[DeliveryAddress]:
        del customer_id
        if self._address_error is not None:
            raise self._address_error
        return self._addresses

    async def search_products(self, address_id: str, query: str):  # type: ignore[no-untyped-def]
        self.search_calls += 1
        return await self._mock.search_products(address_id, query)

    async def update_cart(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.update_calls += 1
        return await self._mock.update_cart(*args, **kwargs)

    async def get_cart(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._mock.get_cart(*args, **kwargs)

    async def get_go_to_items(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._mock.get_go_to_items(*args, **kwargs)

    async def get_payment_options(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._mock.get_payment_options(*args, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addresses",
    [
        [DeliveryAddress(id="addr-bandra-1", label="Home", street="Bandra")],
        [
            DeliveryAddress(id="addr-bandra-1", label="Home", street="Bandra"),
            DeliveryAddress(id="addr-office", label="Work", street="BKC"),
        ],
    ],
    ids=["one-address", "multiple-addresses"],
)
async def test_saved_addresses_require_choice_before_commerce(
    addresses: list[DeliveryAddress],
) -> None:
    adapter = ControlledSwiggyAdapter(addresses)
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    result = await orchestrator.handle_turn(
        "address-choice",
        "customer",
        "get 1L milk",
    )

    assert result.conversation_state == ConversationState.NEEDS_DECISION
    assert result.events == ["NEEDS_ADDRESS_SELECTION"]
    assert adapter.search_calls == 0
    assert adapter.update_calls == 0
    session = store.get("address-choice")
    assert session is not None
    assert session.address_id is None


@pytest.mark.asyncio
async def test_saved_address_choice_resumes_original_request_with_exact_id() -> None:
    adapter = ControlledSwiggyAdapter(
        [DeliveryAddress(id="addr-bandra-1", label="Home", street="Bandra")]
    )
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    prompted = await orchestrator.handle_turn(
        "address-resume",
        "customer",
        "get 1L milk",
    )
    assert prompted.conversation_state == ConversationState.NEEDS_DECISION

    selected = await orchestrator.handle_turn("address-resume", "customer", "1")

    assert selected.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert "ADDRESS_SELECTED id=addr-bandra-1" in selected.events
    assert any("ITEM_RESOLVED name='milk'" in event for event in selected.events)
    assert store.get("address-resume").address_id == "addr-bandra-1"  # type: ignore[union-attr]
    assert adapter.search_calls == 1
    assert adapter.update_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_event"),
    [
        (ProviderAuthError("secret provider detail"), "PROVIDER_REAUTH_REQUIRED"),
        (ProviderSessionRevokedError("secret provider detail"), "PROVIDER_SESSION_REVOKED"),
        (UpstreamTimeoutError("secret provider detail"), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
        (CommerceError("secret provider detail"), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
    ],
)
async def test_address_provider_failures_are_not_reported_as_empty(
    error: Exception,
    expected_event: str,
) -> None:
    adapter = ControlledSwiggyAdapter([], address_error=error)
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=OrchestratorSessionStore(),
    )

    result = await orchestrator.handle_turn("address-failure", "customer", "get milk")

    assert result.conversation_state == ConversationState.FAILED
    assert expected_event in result.events
    assert "no delivery address" not in result.user_message.lower()
    assert "secret provider detail" not in result.user_message


class SearchFailureAdapter(MockCommerceAdapter):
    def __init__(self, error: Exception | None) -> None:
        super().__init__()
        self.error = error

    async def search_products(self, address_id: str, query: str):  # type: ignore[no-untyped-def]
        del address_id, query
        if self.error is not None:
            raise self.error
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_event"),
    [
        (ProviderAuthError(), "PROVIDER_REAUTH_REQUIRED"),
        (ProviderSessionRevokedError(), "PROVIDER_SESSION_REVOKED"),
        (UpstreamTimeoutError(), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
        (OSError("network down"), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
    ],
)
async def test_search_provider_failures_are_not_reported_as_no_match(
    error: Exception,
    expected_event: str,
) -> None:
    orchestrator = GrocerOrchestrator(
        commerce_adapter=SearchFailureAdapter(error),
        session_store=OrchestratorSessionStore(),
    )

    result = await orchestrator.handle_turn(
        "search-failure",
        "customer",
        "get milk",
        address_id="addr-bandra-1",
    )

    assert result.conversation_state == ConversationState.FAILED
    assert expected_event in result.events
    assert "no matching products" not in result.user_message.lower()


@pytest.mark.asyncio
async def test_genuinely_empty_search_remains_distinct() -> None:
    orchestrator = GrocerOrchestrator(
        commerce_adapter=SearchFailureAdapter(None),
        session_store=OrchestratorSessionStore(),
    )

    result = await orchestrator.handle_turn(
        "empty-search",
        "customer",
        "get milk",
        address_id="addr-bandra-1",
    )

    assert result.conversation_state == ConversationState.FAILED
    assert "no matching products" in result.user_message.lower()
    assert not any(event.startswith("PROVIDER_") for event in result.events)


class RecoveryCatalogFailureAdapter(MockCommerceAdapter):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    async def get_go_to_items(self, address_id: str):  # type: ignore[no-untyped-def]
        del address_id
        raise self.error

    async def search_products(self, address_id: str, query: str):  # type: ignore[no-untyped-def]
        del address_id, query
        raise self.error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_event"),
    [
        (ProviderAuthError(), "PROVIDER_REAUTH_REQUIRED"),
        (UpstreamTimeoutError(), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
    ],
)
async def test_recovery_catalog_failures_preserve_provider_type(
    error: Exception,
    expected_event: str,
) -> None:
    orchestrator = GrocerOrchestrator(
        commerce_adapter=RecoveryCatalogFailureAdapter(error),
        session_store=OrchestratorSessionStore(),
    )

    result = await orchestrator.handle_turn(
        "recovery-catalog-failure",
        "customer",
        "get 1L milk under ₹50",
        address_id="addr-bandra-1",
    )

    assert result.conversation_state == ConversationState.FAILED
    assert expected_event in result.events
    assert "no matching products" not in result.user_message.lower()


class PaymentOptionsAdapter(MockCommerceAdapter):
    def __init__(
        self,
        options: list[PaymentOption] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.options = options or []
        self.error = error
        self.checkout_calls = 0
        self.checkout_kwargs: dict[str, object] = {}

    async def get_payment_options(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        if self.error is not None:
            raise self.error
        return self.options

    async def checkout(self, cart_id: str, **kwargs):  # type: ignore[no-untyped-def]
        self.checkout_calls += 1
        self.checkout_kwargs = kwargs
        return await super().checkout(cart_id, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_event"),
    [
        (ProviderAuthError(), "PROVIDER_REAUTH_REQUIRED"),
        (ProviderSessionRevokedError(), "PROVIDER_SESSION_REVOKED"),
        (UpstreamTimeoutError(), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
        (OSError("network down"), "PROVIDER_TEMPORARILY_UNAVAILABLE"),
    ],
)
async def test_payment_option_failures_are_not_reported_as_empty(
    error: Exception,
    expected_event: str,
) -> None:
    orchestrator = GrocerOrchestrator(
        commerce_adapter=PaymentOptionsAdapter(error=error),
        session_store=OrchestratorSessionStore(),
    )

    result = await orchestrator.handle_turn(
        "payment-options-failure",
        "customer",
        "get 1L milk",
        address_id="addr-bandra-1",
    )

    assert result.conversation_state == ConversationState.FAILED
    assert expected_event in result.events
    assert "no payment option" not in result.user_message.lower()


def _multi_payment_options() -> list[PaymentOption]:
    return [
        PaymentOption(
            method="UPI",
            label="Google Pay",
            id="gpay-provider-id",
            kind="intent",
        ),
        PaymentOption(
            method="UPI",
            label="PhonePe",
            id="phonepe-provider-id",
            kind="intent",
        ),
        PaymentOption(method="Cash", label="Cash", id="cash", kind=None),
    ]


@pytest.mark.asyncio
async def test_multiple_payment_options_require_explicit_selection() -> None:
    adapter = PaymentOptionsAdapter(_multi_payment_options())
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    result = await orchestrator.handle_turn(
        "multi-payment",
        "customer",
        "get 1L milk",
        address_id="addr-bandra-1",
    )

    assert result.conversation_state == ConversationState.NEEDS_DECISION
    assert result.requires_confirmation is False
    assert [option.id for option in result.payment_options] == [
        "gpay-provider-id",
        "phonepe-provider-id",
        "cash",
    ]
    assert result.payment_choice_nonce
    session = store.get("multi-payment")
    assert session is not None
    assert session.pending_confirmation is None
    assert session.pending_payment_choice is not None
    assert adapter.checkout_calls == 0


@pytest.mark.asyncio
async def test_selected_payment_option_is_bound_exactly_to_fresh_confirmation() -> None:
    adapter = PaymentOptionsAdapter(_multi_payment_options())
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    prompted = await orchestrator.handle_turn(
        "pick-payment",
        "customer",
        "get 1L milk",
        address_id="addr-bandra-1",
    )

    selected = await orchestrator.handle_payment_choice(
        "pick-payment",
        "phonepe-provider-id",
        prompted.payment_choice_nonce,
    )

    assert selected.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert selected.basket_summary is not None
    assert selected.basket_summary.selected_payment_option_id == "phonepe-provider-id"
    assert selected.basket_summary.selected_payment_option_kind == "intent"
    assert selected.basket_summary.selected_payment_method == "UPI"
    confirmation_nonce = selected.basket_summary.confirmation_nonce

    placed = await orchestrator.handle_confirm(
        "pick-payment",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=confirmation_nonce,
    )

    assert placed.conversation_state == ConversationState.ORDERED
    assert adapter.checkout_kwargs["payment_option_id"] == "phonepe-provider-id"
    assert adapter.checkout_kwargs["payment_option_kind"] == "intent"


@pytest.mark.asyncio
async def test_stale_payment_selection_is_rejected_without_checkout() -> None:
    adapter = PaymentOptionsAdapter(_multi_payment_options())
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=OrchestratorSessionStore(),
    )
    prompted = await orchestrator.handle_turn(
        "stale-payment",
        "customer",
        "get 1L milk",
        address_id="addr-bandra-1",
    )

    stale = await orchestrator.handle_payment_choice(
        "stale-payment",
        "phonepe-provider-id",
        "stale-payment-choice-nonce",
    )

    assert stale.conversation_state == ConversationState.NEEDS_DECISION
    assert stale.events == ["STALE_PAYMENT_CHOICE_REJECTED"]
    assert stale.payment_choice_nonce == prompted.payment_choice_nonce
    assert adapter.checkout_calls == 0


@pytest.mark.asyncio
async def test_changed_payment_method_invalidates_prior_confirmation() -> None:
    adapter = PaymentOptionsAdapter(_multi_payment_options())
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=OrchestratorSessionStore(),
    )
    prompted = await orchestrator.handle_turn(
        "change-payment",
        "customer",
        "get 1L milk",
        address_id="addr-bandra-1",
    )
    selected = await orchestrator.handle_payment_choice(
        "change-payment",
        "gpay-provider-id",
        prompted.payment_choice_nonce,
    )
    assert selected.basket_summary is not None
    old_nonce = selected.basket_summary.confirmation_nonce

    changed = await orchestrator.handle_confirm(
        "change-payment",
        payment_method="Cash",
        explicit_confirmation=True,
        confirmation_nonce=old_nonce,
    )

    assert changed.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert changed.basket_summary is not None
    assert changed.basket_summary.selected_payment_option_id == "cash"
    assert changed.basket_summary.confirmation_nonce != old_nonce
    assert adapter.checkout_calls == 0


class TrackingAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.track_calls = 0
        self.delivery_calls = 0
        self.track_args: tuple[str, float | None, float | None] | None = None

    async def track_order(
        self,
        order_id: str,
        lat: float | None = None,
        lng: float | None = None,
    ) -> DeliveryTrackingStatus:
        self.track_calls += 1
        self.track_args = (order_id, lat, lng)
        return DeliveryTrackingStatus(
            order_id=order_id,
            status="OUT_FOR_DELIVERY",
            raw_status="Rider is out for delivery",
            eta_minutes=8,
            eta_text="8 minutes",
            status_message="Your order is nearby",
            store_name="Instamart Bandra",
            polling_interval_seconds=15,
        )

    async def get_delivery_status(
        self,
        order_id: str,
        address_id: str,
    ) -> DeliveryStatusResult:
        del address_id
        self.delivery_calls += 1
        return DeliveryStatusResult(
            order_id=order_id,
            status_text="Packing",
            eta_text="12 minutes",
            poll_interval_sec=15,
        )


@pytest.mark.asyncio
async def test_conversational_tracking_uses_primary_tool_with_trusted_coordinates() -> None:
    adapter = TrackingAdapter()
    store = OrchestratorSessionStore()
    session = store.get_or_create("rich-tracking", "customer")
    session.conversation_state = ConversationState.ORDERED
    session.order_id = "order-1"
    session.address_id = "addr-bandra-1"
    session.delivery_latitude = 19.0596
    session.delivery_longitude = 72.8295
    store.save(session)
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    result = await orchestrator.handle_delivery_status("rich-tracking")

    assert result.events == ["ORDER_TRACKING_READ"]
    assert adapter.track_args == ("order-1", 19.0596, 72.8295)
    assert adapter.track_calls == 1
    assert adapter.delivery_calls == 0
    assert "Rider is out for delivery" in result.user_message
    assert "8 minutes" in result.user_message


@pytest.mark.asyncio
async def test_missing_coordinates_uses_explicit_delivery_status_fallback() -> None:
    adapter = TrackingAdapter()
    store = OrchestratorSessionStore()
    session = store.get_or_create("tracking-fallback", "customer")
    session.conversation_state = ConversationState.ORDERED
    session.order_id = "order-1"
    session.address_id = "addr-bandra-1"
    store.save(session)
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)

    result = await orchestrator.handle_delivery_status("tracking-fallback")

    assert result.events == ["ORDER_TRACKING_FALLBACK_DELIVERY_STATUS"]
    assert adapter.track_calls == 0
    assert adapter.delivery_calls == 1
    assert "detailed rider tracking is unavailable" in result.user_message.lower()
    assert "Packing" in result.user_message
    assert "12 minutes" in result.user_message


@pytest.mark.asyncio
async def test_poll_cap_finalization_is_not_repeated_after_unknown_result() -> None:
    from backend.integrations.commerce.models import CommerceOrderResult
    from backend.tests.test_payment_order_lifecycle import PendingPaymentAdapter

    class AmbiguousFinalizationAdapter(PendingPaymentAdapter):
        async def confirm_order(self, order_id: str, paas_id: str):  # type: ignore[no-untyped-def]
            self.confirm_calls += 1
            return CommerceOrderResult(
                order_id=order_id,
                cart_id="payment-cart",
                status="ORDER_STATE_UNKNOWN",
                raw_status="PENDING",
                payment_method="UPI",
                grand_total=101,
                delivery_address=DeliveryAddress(id="addr-bandra-1"),
                paas_id=paas_id,
            )

    adapter = AmbiguousFinalizationAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    basket = await orchestrator.handle_turn("poll-cap", "customer", "get 1L milk")
    assert basket.basket_summary is not None
    await orchestrator.handle_confirm(
        "poll-cap",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )
    session = store.get("poll-cap")
    assert session is not None
    session.payment_poll_deadline = datetime.now(timezone.utc) - timedelta(seconds=1)

    expired = await orchestrator.handle_payment_status("poll-cap")
    repeated = await orchestrator.handle_payment_status("poll-cap")

    assert expired.conversation_state == ConversationState.ORDER_STATE_UNKNOWN
    assert expired.events == ["PAYMENT_POLL_CAP_CONFIRM_ATTEMPTED", "CHECKOUT_STATE_UNKNOWN"]
    assert repeated.events == ["NO_PENDING_PAYMENT"]
    assert adapter.confirm_calls == 1
    assert adapter.payment_status_calls == 0
