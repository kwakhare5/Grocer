from __future__ import annotations

from contextlib import contextmanager

from backend.channels.models import (
    ChannelType,
    NormalizedIncomingMessage,
)
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.exceptions import CommerceError
from backend.integrations.commerce.models import CartItemUpdate, PaymentOption
from backend.intent.message_understanding import MessageUnderstandingService
from backend.intent.task_model import (
    DesiredBasketItem,
    MessageUnderstanding,
    ShoppingTask,
    TaskOperation,
    TaskState,
)
from backend.intent.task_repository import InMemoryShoppingTaskRepository
from backend.intent.task_service import ShoppingTaskApplicationService


def _message(
    text: str,
    *,
    message_id: str = "wamid.1",
    interactive_id: str | None = None,
) -> NormalizedIncomingMessage:
    return NormalizedIncomingMessage(
        sender_id="wa:+910000000001",
        channel=ChannelType.WHATSAPP,
        text=text,
        message_id=message_id,
        interactive_type="button_reply" if interactive_id else None,
        interactive_id=interactive_id,
    )


class RecordingCommerceAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def get_addresses(self, customer_id: str):  # type: ignore[no-untyped-def]
        self.calls.append("get_addresses")
        return await super().get_addresses(customer_id)

    async def search_products(self, address_id: str, query: str):  # type: ignore[no-untyped-def]
        self.calls.append(f"search:{query}")
        return await super().search_products(address_id, query)

    async def get_cart(self, cart_id: str | None = None):  # type: ignore[no-untyped-def]
        self.calls.append("get_cart")
        return await super().get_cart(cart_id)

    async def update_cart(
        self,
        items: list[CartItemUpdate],
        cart_id: str | None = None,
        address_id: str | None = None,
    ):
        self.calls.append("update_cart")
        return await super().update_cart(items, cart_id, address_id)

    async def checkout(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append("checkout")
        return await super().checkout(*args, **kwargs)

    async def get_payment_options(
        self, cart_id: str | None = None, address_id: str | None = None
    ) -> list[PaymentOption]:
        self.calls.append("get_payment_options")
        return [
            PaymentOption(method="COD", label="Cash on delivery", is_available=True),
            PaymentOption(method="UPI", label="UPI", is_available=True),
        ]


class CustomerScopedRecordingAdapter(RecordingCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.active_customer: str | None = None
        self.observed_customers: list[str | None] = []

    @contextmanager
    def customer_scope(self, customer_id: str):  # type: ignore[no-untyped-def]
        previous = self.active_customer
        self.active_customer = customer_id
        try:
            yield
        finally:
            self.active_customer = previous

    async def get_addresses(self, customer_id: str):  # type: ignore[no-untyped-def]
        self.observed_customers.append(self.active_customer)
        return await super().get_addresses(customer_id)


async def test_new_basket_is_only_previewed_and_duplicate_is_deduplicated() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    first = await service.handle_message(_message("1 ltr milk and 1 bread"))
    await service.mark_response_sent(_message("1 ltr milk and 1 bread"))
    duplicate = await service.handle_message(_message("1 ltr milk and 1 bread"))

    assert first.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert first.requires_confirmation
    assert "milk" in first.text.casefold() and "bread" in first.text.casefold()
    assert commerce.calls == []
    assert "already received" in duplicate.text
    assert len(repository.outbox) == 1


async def test_failed_outbound_delivery_is_retried_without_reprocessing() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")
    message = _message("1 bread", message_id="retry-delivery")

    first = await service.process_message(message)
    retry = await service.process_message(message)

    assert first.processed is True
    assert retry.processed is True
    assert retry.response == first.response
    assert len(repository.outbox) == 1

    await service.mark_response_sent(message)
    delivered_replay = await service.process_message(message)

    assert delivered_replay.processed is False
    assert "already received" in delivered_replay.response.text


async def test_first_message_creates_task_before_inbox_foreign_key() -> None:
    class ForeignKeyCheckingRepository(InMemoryShoppingTaskRepository):
        async def record_inbound_event(self, *, provider, message_id, payload, task_id):  # type: ignore[no-untyped-def]
            if task_id is not None and await self.get(task_id) is None:
                raise AssertionError("inbound event references a missing task")
            return await super().record_inbound_event(
                provider=provider,
                message_id=message_id,
                payload=payload,
                task_id=task_id,
            )

    repository = ForeignKeyCheckingRepository()
    commerce = RecordingCommerceAdapter()
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    await service.handle_message(_message("hello", message_id="first"))

    task = await repository.get("wa:+910000000001")
    assert task is not None


async def test_task_service_scopes_provider_calls_to_customer() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = CustomerScopedRecordingAdapter()
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.AWAITING_BASKET_APPROVAL,
            pending_plan={"version": 1, "items": [{"name": "Bread", "quantity": 1}]},
        )
    )
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    await service.handle_message(_message("yes", message_id="scoped-confirm"))

    assert commerce.observed_customers == ["wa:+910000000001"]
    assert commerce.active_customer is None


async def test_provider_failure_returns_safe_reply_and_preserves_basket() -> None:
    class InvalidProviderResponseAdapter(RecordingCommerceAdapter):
        async def get_addresses(self, customer_id: str):  # type: ignore[no-untyped-def]
            del customer_id
            raise CommerceError(
                "provider body must never reach the customer",
                provider="swiggy",
                code="INVALID_PROVIDER_RESPONSE",
            )

    repository = InMemoryShoppingTaskRepository()
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.AWAITING_BASKET_APPROVAL,
            pending_plan={"version": 1, "items": [{"name": "Bread", "quantity": 1}]},
        )
    )
    service = ShoppingTaskApplicationService(
        repository,
        InvalidProviderResponseAdapter(),
        checkout_mode="review",
    )

    response = await service.handle_message(_message("yes", message_id="provider-failed"))

    saved = await repository.get_required("wa:+910000000001")
    assert response.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert "basket is unchanged" in response.text.casefold()
    assert "try again" in response.text.casefold()
    assert "provider body" not in response.text
    assert saved.state == TaskState.AWAITING_BASKET_APPROVAL
    assert saved.pending_plan is not None
    assert len(repository.outbox) == 1


async def test_product_choice_after_approved_plan_updates_pending_basket() -> None:
    repository = InMemoryShoppingTaskRepository()
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.NEEDS_PRODUCT_CHOICE,
            pending_plan={
                "version": 2,
                "approved_at": "2026-09-17T04:39:00+00:00",
                "items": [
                    {"name": "dairy milk", "quantity": 5},
                    {"name": "eggs", "quantity": 2},
                ],
            },
        )
    )
    service = ShoppingTaskApplicationService(
        repository,
        RecordingCommerceAdapter(),
        checkout_mode="review",
    )

    response = await service.handle_message(
        _message(
            "Cadbury Dairy Milk",
            message_id="product-choice",
            interactive_id="select_product:dairy milk:SPIN-CADBURY-20G",
        )
    )

    saved = await repository.get_required("wa:+910000000001")
    assert response.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert "could not find" not in response.text.casefold()
    assert saved.pending_plan is not None
    dairy_milk = saved.pending_plan.items[0]
    assert dairy_milk.name == "dairy milk"
    assert dairy_milk.selected_spin_id == "SPIN-CADBURY-20G"
    assert saved.pending_plan.approved_at is None


async def test_change_address_never_falls_into_basket_parsing() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.AWAITING_CHECKOUT_CONFIRMATION,
        desired_basket=[DesiredBasketItem(name="Bread", quantity=1)],
        selected_address_id="old-address",
        selected_payment_method="cod",
        confirmation_valid=True,
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    response = await service.handle_message(_message("change address"))
    saved = await repository.get_required(task.task_id)

    assert response.conversation_state == TaskState.NEEDS_ADDRESS
    assert [action.title for action in response.interactive_actions] == ["Home", "Work"]
    assert saved.selected_address_id is None
    assert not saved.confirmation_valid
    assert saved.pending_plan is not None
    assert saved.pending_plan.cart_strategy == "start_fresh"
    assert commerce.calls == ["get_addresses"]


async def test_changed_address_requires_new_preview_before_cart_rebuild() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.AWAITING_CHECKOUT_CONFIRMATION,
        desired_basket=[DesiredBasketItem(name="Bread", quantity=1)],
        selected_address_id="addr-bandra-1",
        selected_payment_method="cod",
        confirmation_valid=True,
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    await service.handle_message(_message("change address", message_id="change"))
    preview = await service.handle_message(
        _message(
            "Work",
            message_id="select",
            interactive_id="select_address:addr-andheri-1",
        )
    )

    saved = await repository.get_required(task.task_id)
    assert preview.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert saved.selected_address_id == "addr-andheri-1"
    assert saved.pending_plan is not None
    assert saved.pending_plan.approved_at is None
    assert "update_cart" not in commerce.calls

    synced = await service.handle_message(_message("yes", message_id="reapprove"))

    assert synced.conversation_state == TaskState.NEEDS_PAYMENT
    assert commerce.calls[-3:] == ["update_cart", "get_cart", "get_payment_options"]


async def test_typed_and_button_address_selection_use_the_same_transition() -> None:
    async def run(message: NormalizedIncomingMessage) -> ShoppingTask:
        repository = InMemoryShoppingTaskRepository()
        await repository.create(
            ShoppingTask(
                task_id=message.sender_id,
                customer_id=message.sender_id,
                state=TaskState.NEEDS_ADDRESS,
            )
        )
        service = ShoppingTaskApplicationService(
            repository, RecordingCommerceAdapter(), checkout_mode="review"
        )
        await service.handle_message(message)
        return await repository.get_required(message.sender_id)

    typed = await run(_message("use address addr-bandra-1", message_id="typed"))
    button = await run(
        _message(
            "Home",
            message_id="button",
            interactive_id="select_address:addr-bandra-1",
        )
    )

    assert typed.state == button.state == TaskState.NEEDS_PAYMENT
    assert typed.selected_address_id == button.selected_address_id == "addr-bandra-1"


async def test_resolve_all_before_cart_update() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.AWAITING_BASKET_APPROVAL,
            selected_address_id="addr-bandra-1",
            pending_plan={
                "version": 2,
                "items": [
                    {"name": "Bread", "quantity": 1},
                    {"name": "Bhindi", "quantity": 1},
                ],
            },
        )
    )
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    response = await service.handle_message(_message("yes"))

    assert "Bhindi" in response.text
    assert "update_cart" not in commerce.calls


async def test_existing_provider_cart_requires_an_explicit_choice() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    await commerce.update_cart(
        [CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1)],
        address_id="addr-bandra-1",
    )
    commerce.calls.clear()
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.AWAITING_BASKET_APPROVAL,
            selected_address_id="addr-bandra-1",
            pending_plan={
                "version": 2,
                "items": [{"name": "Milk", "quantity": 1, "unit": "L"}],
            },
        )
    )
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    response = await service.handle_message(_message("yes"))

    assert response.conversation_state == TaskState.NEEDS_CART_ADOPTION
    assert [action.title for action in response.interactive_actions] == [
        "Keep",
        "Start fresh",
        "Cancel",
    ]
    assert "update_cart" not in commerce.calls


async def test_approved_sync_reads_back_and_review_mode_never_checks_out() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.AWAITING_BASKET_APPROVAL,
            selected_address_id="addr-bandra-1",
            pending_plan={
                "version": 2,
                "cart_strategy": "start_fresh",
                "items": [{"name": "Bread", "quantity": 1}],
            },
        )
    )
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    synced = await service.handle_message(_message("yes", message_id="approve"))
    assert synced.conversation_state == TaskState.NEEDS_PAYMENT
    assert commerce.calls[-3:] == ["update_cart", "get_cart", "get_payment_options"]

    final = await service.handle_message(
        _message("pay by cash on delivery", message_id="payment")
    )
    confirmed = await service.handle_message(_message("confirm", message_id="confirm"))

    assert final.conversation_state == TaskState.AWAITING_CHECKOUT_CONFIRMATION
    assert "Whole Wheat Bread 400g" in final.text
    assert "Home" in final.text
    assert "Cash on delivery" in final.text
    assert "Total: ₹85" in final.text
    assert confirmed.conversation_state == TaskState.AWAITING_CHECKOUT_CONFIRMATION
    assert "Review complete" in confirmed.text
    assert "checkout" not in commerce.calls


async def test_payment_actions_come_only_from_live_provider_options() -> None:
    repository = InMemoryShoppingTaskRepository()
    commerce = RecordingCommerceAdapter()
    commerce.get_payment_options = MockCommerceAdapter.get_payment_options.__get__(
        commerce, RecordingCommerceAdapter
    )
    await commerce.update_cart(
        [CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1)],
        address_id="addr-bandra-1",
    )
    await repository.create(
        ShoppingTask(
            task_id="wa:+910000000001",
            customer_id="wa:+910000000001",
            state=TaskState.NEEDS_PAYMENT,
            selected_address_id="addr-bandra-1",
            provider_cart={"cart_id": "default-cart"},
            desired_basket=[DesiredBasketItem(name="Bread", quantity=1)],
        )
    )
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    unavailable = await service.handle_message(
        _message("pay by cash on delivery", message_id="cod")
    )

    assert unavailable.conversation_state == TaskState.NEEDS_PAYMENT
    assert "not currently available" in unavailable.text
    assert [action.id for action in unavailable.interactive_actions] == [
        "select_payment:upi"
    ]
    assert unavailable.interactive_actions[0].title.startswith("UPI Instant Pay")


async def test_typed_ordinal_uses_the_same_persisted_product_choice_as_a_button() -> None:
    repository = InMemoryShoppingTaskRepository()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.NEEDS_PRODUCT_CHOICE,
        pending_plan={"version": 2, "items": [{"name": "Milk", "quantity": 1}]},
        offered_choices=[
            {
                "action_id": "select_product:Milk:SPIN-MILK-1L",
                "title": "Amul Taaza 1L",
                "description": "1 L — ₹66",
            },
            {
                "action_id": "select_product:Milk:SPIN-MILK-500ML",
                "title": "Amul Taaza 500ml",
                "description": "500 ml — ₹34",
            },
        ],
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(
        repository, RecordingCommerceAdapter(), checkout_mode="review"
    )

    response = await service.handle_message(_message("the second one", message_id="ordinal"))
    saved = await repository.get_required(task.task_id)

    assert response.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert saved.pending_plan is not None
    assert saved.pending_plan.items[0].selected_spin_id == "SPIN-MILK-500ML"


async def test_typed_cheaper_choice_uses_the_visible_product_prices() -> None:
    repository = InMemoryShoppingTaskRepository()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.NEEDS_PRODUCT_CHOICE,
        pending_plan={"version": 2, "items": [{"name": "Milk", "quantity": 1}]},
        offered_choices=[
            {
                "action_id": "select_product:Milk:SPIN-MILK-1L",
                "title": "Amul Taaza 1L",
                "description": "1 L — ₹66",
            },
            {
                "action_id": "select_product:Milk:SPIN-MILK-500ML",
                "title": "Amul Taaza 500ml",
                "description": "500 ml — ₹34",
            },
        ],
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(
        repository, RecordingCommerceAdapter(), checkout_mode="review"
    )

    await service.handle_message(_message("the cheaper one", message_id="cheaper"))
    saved = await repository.get_required(task.task_id)

    assert saved.pending_plan is not None
    assert saved.pending_plan.items[0].selected_spin_id == "SPIN-MILK-500ML"


async def test_model_action_id_is_validated_against_persisted_choice() -> None:
    class FullActionModel:
        async def interpret(self, _message, *, context=None):  # type: ignore[no-untyped-def]
            del context
            return MessageUnderstanding(
                operation=TaskOperation.SELECT_PRODUCT,
                selection_value="select_product:Milk:SPIN-MILK-500ML",
                confidence=0.98,
                source="model",
            )

    repository = InMemoryShoppingTaskRepository()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.NEEDS_PRODUCT_CHOICE,
        pending_plan={"version": 2, "items": [{"name": "Milk", "quantity": 1}]},
        offered_choices=[
            {
                "action_id": "select_product:Milk:SPIN-MILK-500ML",
                "title": "Amul Taaza 500ml",
                "description": "500 ml — ₹34",
            }
        ],
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(
        repository,
        RecordingCommerceAdapter(),
        checkout_mode="review",
        understanding=MessageUnderstandingService(FullActionModel()),
    )

    response = await service.handle_message(_message("the 500 ml one", message_id="model-id"))
    saved = await repository.get_required(task.task_id)

    assert response.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert saved.pending_plan is not None
    assert saved.pending_plan.items[0].selected_spin_id == "SPIN-MILK-500ML"


async def test_verified_quantity_cap_requires_explicit_customer_decision() -> None:
    class QuantityCappingAdapter(RecordingCommerceAdapter):
        async def update_cart(self, items, cart_id=None, address_id=None):  # type: ignore[no-untyped-def]
            cart = await super().update_cart(items, cart_id, address_id)
            cart.items[0].quantity = 2
            cart.items[0].total_price = cart.items[0].unit_price * 2
            cart.item_total = cart.items[0].total_price
            cart.grand_total = cart.item_total + cart.delivery_fee + cart.packaging_fee
            cart.reduced_quantity_items = [{"spinId": cart.items[0].spin_id, "quantity": 2}]
            return cart

    repository = InMemoryShoppingTaskRepository()
    commerce = QuantityCappingAdapter()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.AWAITING_BASKET_APPROVAL,
        selected_address_id="addr-bandra-1",
        pending_plan={
            "version": 2,
            "cart_strategy": "start_fresh",
            "items": [{"name": "Bread", "quantity": 5}],
        },
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(repository, commerce, checkout_mode="review")

    capped = await service.handle_message(_message("yes", message_id="cap"))
    saved = await repository.get_required(task.task_id)

    assert capped.conversation_state == TaskState.NEEDS_STOCK_DECISION
    assert [action.title for action in capped.interactive_actions] == [
        "Keep 2",
        "Choose another",
        "Remove item",
    ]
    assert saved.pending_stock_recovery is not None
    assert saved.pending_stock_recovery.requested_quantity == 5
    assert saved.pending_stock_recovery.available_quantity == 2

    reapproved = await service.handle_message(_message("1", message_id="keep-two"))
    saved = await repository.get_required(task.task_id)

    assert reapproved.conversation_state == TaskState.AWAITING_BASKET_APPROVAL
    assert saved.pending_plan is not None
    assert saved.pending_plan.items[0].quantity == 2
    assert saved.pending_plan.approved_at is None
    assert commerce.calls.count("update_cart") == 1


async def test_stock_substitution_uses_only_live_alternative_variants() -> None:
    repository = InMemoryShoppingTaskRepository()
    task = ShoppingTask(
        task_id="wa:+910000000001",
        customer_id="wa:+910000000001",
        state=TaskState.NEEDS_STOCK_DECISION,
        selected_address_id="addr-bandra-1",
        pending_plan={
            "version": 2,
            "cart_strategy": "start_fresh",
            "approved_at": "2026-09-17T04:39:00+00:00",
            "items": [
                {
                    "name": "Milk",
                    "quantity": 1,
                    "selected_spin_id": "SPIN-MILK-1L",
                }
            ],
        },
        pending_stock_recovery={
            "item_name": "Milk",
            "requested_quantity": 1,
            "available_quantity": 0,
            "spin_id": "SPIN-MILK-1L",
        },
        offered_choices=[
            {
                "action_id": "stock_substitute:SPIN-MILK-1L",
                "title": "Choose another",
            }
        ],
    )
    await repository.create(task)
    service = ShoppingTaskApplicationService(
        repository, RecordingCommerceAdapter(), checkout_mode="review"
    )

    response = await service.handle_message(_message("choose another", message_id="sub"))
    saved = await repository.get_required(task.task_id)

    assert response.conversation_state == TaskState.NEEDS_PRODUCT_CHOICE
    assert [action.id for action in response.interactive_actions] == [
        "select_product:Milk:SPIN-MILK-500ML"
    ]
    assert saved.pending_stock_recovery is None
    assert saved.pending_plan is not None
    assert saved.pending_plan.approved_at is None
