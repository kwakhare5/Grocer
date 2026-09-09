"""Truthful payment, partial-order, and tracking lifecycle regressions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.exceptions import (
    CommerceError,
    OrderStateUnknownError,
    UnconfirmedCheckoutError,
)
from backend.integrations.commerce.models import (
    CommerceOrderResult,
    DeliveryAddress,
    PaymentOption,
    PaymentStatusResult,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.session import ConversationState, OrchestratorSessionStore


class PendingPaymentAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.payment_status = PaymentStatusResult(
            paas_id="paas-1",
            order_id="order-1",
            status="PENDING",
            normalized_status="PAYMENT_PENDING",
            terminal=False,
            confirmed=False,
        )
        self.confirm_calls = 0
        self.payment_status_calls = 0

    async def checkout(self, cart_id: str, **kwargs) -> CommerceOrderResult:  # type: ignore[no-untyped-def]
        cart = await self.get_cart(cart_id)
        return CommerceOrderResult(
            order_id="order-1",
            cart_id=cart_id,
            status="PAYMENT_PENDING",
            raw_status="PENDING_PAYMENT",
            items=list(cart.items),
            payment_method="UPI",
            grand_total=cart.grand_total,
            delivery_address=DeliveryAddress(id=cart.address_id or "addr-bandra-1"),
            paas_id="paas-1",
            bridge_url="https://mcp.swiggy.com/pay/test",
            polling_interval_ms=2000,
            max_time_to_poll_ms=30000,
        )

    async def check_payment_status(self, paas_id: str, order_id: str | None = None):  # type: ignore[no-untyped-def]
        self.payment_status_calls += 1
        return self.payment_status

    async def confirm_order(self, order_id: str, paas_id: str):  # type: ignore[no-untyped-def]
        self.confirm_calls += 1
        return CommerceOrderResult(
            order_id=order_id,
            cart_id="payment-cart",
            status="ORDER_PLACED",
            raw_status="CONFIRMED",
            payment_method="UPI",
            grand_total=101,
            delivery_address=DeliveryAddress(id="addr-bandra-1"),
        )


class PaymentChoiceAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.checkout_kwargs: dict[str, object] = {}

    async def get_payment_options(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return [
            PaymentOption(
                method="UPI",
                label="Google Pay",
                id="google-pay-provider-id",
                kind="intent",
            )
        ]

    async def checkout(self, cart_id: str, **kwargs) -> CommerceOrderResult:  # type: ignore[no-untyped-def]
        self.checkout_kwargs = kwargs
        return await super().checkout(cart_id, **kwargs)


class UnknownCheckoutAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.checkout_calls = 0

    async def checkout(self, cart_id: str, **kwargs) -> CommerceOrderResult:  # type: ignore[no-untyped-def]
        self.checkout_calls += 1
        raise OrderStateUnknownError("provider outcome is uncertain")


@pytest.mark.asyncio
async def test_selected_payment_option_reaches_checkout_unchanged() -> None:
    adapter = PaymentChoiceAdapter()
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=OrchestratorSessionStore(),
    )
    basket = await orchestrator.handle_turn("payment-choice", "customer", "get 1L milk")
    assert basket.basket_summary is not None

    result = await orchestrator.handle_confirm(
        "payment-choice",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )

    assert result.conversation_state == ConversationState.ORDERED
    assert adapter.checkout_kwargs["payment_option_id"] == "google-pay-provider-id"
    assert adapter.checkout_kwargs["payment_option_kind"] == "intent"


@pytest.mark.asyncio
async def test_unknown_checkout_outcome_is_not_reported_as_ordinary_failure() -> None:
    adapter = UnknownCheckoutAdapter()
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=OrchestratorSessionStore(),
    )
    basket = await orchestrator.handle_turn("unknown-checkout", "customer", "get 1L milk")
    assert basket.basket_summary is not None

    result = await orchestrator.handle_confirm(
        "unknown-checkout",
        payment_method=basket.basket_summary.selected_payment_method,
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )

    assert result.conversation_state == ConversationState.ORDER_STATE_UNKNOWN
    assert "will not retry" in result.user_message.lower()
    with pytest.raises(UnconfirmedCheckoutError):
        await orchestrator.handle_confirm(
            "unknown-checkout",
            payment_method=basket.basket_summary.selected_payment_method,
            explicit_confirmation=True,
            confirmation_nonce=basket.basket_summary.confirmation_nonce,
        )
    assert adapter.checkout_calls == 1


@pytest.mark.asyncio
async def test_orchestrator_keeps_pending_payment_out_of_ordered_state() -> None:
    adapter = PendingPaymentAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    basket = await orchestrator.handle_turn("payment-session", "customer", "get 1L milk")
    assert basket.basket_summary is not None

    result = await orchestrator.handle_confirm(
        "payment-session",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )

    assert result.conversation_state == ConversationState.PAYMENT_PENDING
    assert result.payment_status == "PAYMENT_PENDING"
    assert result.payment_url == "https://mcp.swiggy.com/pay/test"
    assert "placed" not in result.user_message.lower()


@pytest.mark.asyncio
async def test_payment_success_is_confirmed_once_before_ordered() -> None:
    adapter = PendingPaymentAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    basket = await orchestrator.handle_turn("payment-success", "customer", "get 1L milk")
    assert basket.basket_summary is not None
    await orchestrator.handle_confirm(
        "payment-success",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )
    adapter.payment_status = PaymentStatusResult(
        paas_id="paas-1",
        order_id="order-1",
        status="SUCCESS",
        normalized_status="PAYMENT_CONFIRMED",
        terminal=True,
        confirmed=False,
    )
    session = store.get("payment-success")
    assert session is not None
    session.order_id = None
    session.payment_next_poll_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    result = await orchestrator.handle_payment_status("payment-success")

    assert result.conversation_state == ConversationState.ORDERED
    assert result.order_id == "order-1"
    assert adapter.confirm_calls == 1


@pytest.mark.asyncio
async def test_payment_polling_honors_provider_cadence_and_deadline() -> None:
    adapter = PendingPaymentAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    basket = await orchestrator.handle_turn("payment-cadence", "customer", "get 1L milk")
    assert basket.basket_summary is not None
    await orchestrator.handle_confirm(
        "payment-cadence",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )

    deferred = await orchestrator.handle_payment_status("payment-cadence")
    assert deferred.conversation_state == ConversationState.PAYMENT_PENDING
    assert deferred.events == ["PAYMENT_POLL_DEFERRED"]
    assert adapter.payment_status_calls == 0

    session = store.get("payment-cadence")
    assert session is not None
    session.payment_poll_deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired = await orchestrator.handle_payment_status("payment-cadence")
    assert expired.conversation_state == ConversationState.ORDER_STATE_UNKNOWN
    assert expired.events == ["PAYMENT_POLL_WINDOW_EXHAUSTED"]
    assert adapter.payment_status_calls == 0


@pytest.mark.asyncio
async def test_failed_payment_never_confirms_order() -> None:
    adapter = PendingPaymentAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    basket = await orchestrator.handle_turn("payment-failed", "customer", "get 1L milk")
    assert basket.basket_summary is not None
    await orchestrator.handle_confirm(
        "payment-failed",
        payment_method="UPI",
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )
    adapter.payment_status = PaymentStatusResult(
        paas_id="paas-1",
        order_id="order-1",
        status="FAILED",
        normalized_status="PAYMENT_FAILED",
        terminal=True,
        is_terminal_failure=True,
    )
    session = store.get("payment-failed")
    assert session is not None
    session.payment_next_poll_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    result = await orchestrator.handle_payment_status("payment-failed")

    assert result.conversation_state == ConversationState.PAYMENT_FAILED
    assert adapter.confirm_calls == 0


@pytest.mark.asyncio
async def test_swiggy_empty_payment_options_are_not_fabricated() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={"success": True, "data": {"allMethods": [], "cod": {"available": False}}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        assert await adapter.get_payment_options(address_id="addr-1") == []


@pytest.mark.asyncio
async def test_swiggy_payment_options_preserve_exact_available_method() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "platforms": {
                    "mobile": {
                        "methods": [
                            {
                                "id": "google-pay-provider-id",
                                "displayName": "Google Pay",
                                "enabled": True,
                            }
                        ]
                    },
                    "desktop": {"methods": []},
                },
                "allMethods": [
                    {
                        "id": "google-pay-provider-id",
                        "displayName": "Google Pay",
                        "enabled": True,
                    }
                ],
                "cod": {"available": False},
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        options = await adapter.get_payment_options(address_id="must-not-be-sent")

    assert [(option.id, option.kind, option.label) for option in options] == [
        ("google-pay-provider-id", "intent", "Google Pay")
    ]
    assert post.call_args.kwargs["json"]["params"]["arguments"] == {}


@pytest.mark.asyncio
async def test_swiggy_partial_multi_store_checkout_is_not_success() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "orders": [
                    {"orderId": "A", "status": "CONFIRMED"},
                    {
                        "orderId": "B",
                        "status": "FAILED",
                        "error": {"message": "Store unavailable"},
                    },
                ],
                "orderCount": 2,
                "successCount": 1,
                "failureCount": 1,
                "allSucceeded": False,
                "status": "PARTIAL",
                "cartTotal": 400,
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        result = await adapter.checkout(
            "cart", payment_method="Cash", explicit_confirmation=True, address_id="addr-1"
        )

    assert result.status == "PARTIAL_ORDER"
    assert result.all_succeeded is False
    assert result.success_count == result.failure_count == 1
    assert [child.order_id for child in result.orders] == ["A", "B"]
    assert result.orders[1].error == "Store unavailable"


@pytest.mark.asyncio
async def test_swiggy_payment_status_and_confirmation_use_official_arguments() -> None:
    adapter = SwiggyMCPAdapter()
    pending = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "paasId": "paas-1",
                "orderId": "order-1",
                "status": "CAPTURED",
                "terminal": True,
                "isTerminalSuccess": True,
                "isTerminalFailure": False,
                "confirmed": False,
                "orderStatus": "PENDING_CONFIRMATION",
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    confirmed = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "orderId": "order-1",
                "paasId": "paas-1",
                "orderStatus": "CONFIRMED",
                "result": "success",
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.side_effect = [pending, confirmed]
        payment = await adapter.check_payment_status("paas-1", "order-1")
        order = await adapter.confirm_order("order-1", "paas-1")

    first_args = post.call_args_list[0].kwargs["json"]["params"]
    second_args = post.call_args_list[1].kwargs["json"]["params"]
    assert first_args == {
        "name": "check_payment_status",
        "arguments": {"paasId": "paas-1", "orderId": "order-1"},
    }
    assert second_args == {
        "name": "confirm_order",
        "arguments": {"orderId": "order-1", "paasId": "paas-1"},
    }
    assert payment.normalized_status == "PAYMENT_CONFIRMED"
    assert order.status == "ORDER_PLACED"


@pytest.mark.asyncio
async def test_swiggy_unknown_tracking_fields_remain_unknown() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={"success": True, "data": {"orderId": "order-1", "status": "MYSTERY"}},
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        tracking = await adapter.track_order("order-1", lat=12.9, lng=77.6)

    arguments = post.call_args.kwargs["json"]["params"]["arguments"]
    assert arguments == {"orderId": "order-1", "lat": 12.9, "lng": 77.6}
    assert tracking.status == "UNKNOWN"
    assert tracking.raw_status == "MYSTERY"
    assert tracking.eta_minutes is None
    assert tracking.polling_interval_seconds is None


@pytest.mark.asyncio
async def test_swiggy_tracking_requires_provider_coordinates() -> None:
    adapter = SwiggyMCPAdapter()

    with pytest.raises(CommerceError, match="provider-returned delivery coordinates"):
        await adapter.track_order("order-1")


@pytest.mark.asyncio
async def test_swiggy_order_details_and_delivery_status_follow_official_contract() -> None:
    adapter = SwiggyMCPAdapter()
    details_response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "orderId": "order-1",
                "status": "Delivered",
                "totalBill": 321,
                "hasRefunds": False,
                "items": [{"name": "Milk", "quantity": 2, "removed": False}],
                "bill": {
                    "lineItems": [{"name": "Item Total", "amount": "₹321"}],
                    "grandTotal": "₹321",
                },
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    delivery_response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "orderId": "order-1",
                "deliveryBy": None,
                "serverNow": 1760000000000,
                "statusText": "Packing",
                "pollIntervalSec": 15,
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.side_effect = [details_response, delivery_response]
        details = await adapter.get_order_details("order-1")
        delivery = await adapter.get_delivery_status("order-1", "addr-1")

    assert post.call_args_list[0].kwargs["json"]["params"] == {
        "name": "get_order_details",
        "arguments": {"orderId": "order-1"},
    }
    assert post.call_args_list[1].kwargs["json"]["params"] == {
        "name": "get_delivery_status",
        "arguments": {"orderId": "order-1", "addressId": "addr-1"},
    }
    assert details.items[0].final_price is None
    assert details.raw_status == "Delivered"
    assert delivery.delivery_by_ms is None
    assert delivery.status_text == "Packing"
    assert delivery.poll_interval_sec == 15


@pytest.mark.asyncio
async def test_swiggy_get_orders_preserves_unknown_optional_fields() -> None:
    adapter = SwiggyMCPAdapter()
    response = httpx.Response(
        200,
        json={
            "success": True,
            "data": {
                "orders": [
                    {
                        "orderId": "order-1",
                        "status": "MYSTERY",
                        "itemCount": 1,
                        "totalAmount": 50,
                        "orderType": "INSTAMART",
                        "isActive": True,
                        "items": [{"name": "Milk", "quantity": 1}],
                    }
                ],
                "hasMore": False,
            },
        },
        request=httpx.Request("POST", adapter.base_url),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = response
        orders = await adapter.get_orders(count=5, active_only=True)

    assert post.call_args.kwargs["json"]["params"] == {
        "name": "get_orders",
        "arguments": {"count": 5, "orderType": "INSTAMART", "activeOnly": True},
    }
    assert orders[0].normalized_status == "ORDER_STATE_UNKNOWN"
    assert orders[0].payment_method is None
    assert orders[0].items[0].name == "Milk"


@pytest.mark.asyncio
async def test_orchestrator_reports_order_details_and_delivery_without_invention() -> None:
    adapter = MockCommerceAdapter()
    store = OrchestratorSessionStore()
    orchestrator = GrocerOrchestrator(commerce_adapter=adapter, session_store=store)
    basket = await orchestrator.handle_turn("order-read", "customer", "get 1L milk")
    assert basket.basket_summary is not None
    placed = await orchestrator.handle_confirm(
        "order-read",
        payment_method=basket.basket_summary.selected_payment_method,
        explicit_confirmation=True,
        confirmation_nonce=basket.basket_summary.confirmation_nonce,
    )
    assert placed.conversation_state == ConversationState.ORDERED

    details = await orchestrator.handle_order_details("order-read")
    delivery = await orchestrator.handle_delivery_status("order-read")

    assert details.conversation_state == ConversationState.ORDERED
    assert "Amul Taaza Milk 1L Pouch" in details.user_message
    assert "₹101" in details.user_message
    assert delivery.conversation_state == ConversationState.ORDERED
    assert "Simulated packing" in delivery.user_message
    assert "12 minutes" in delivery.user_message
