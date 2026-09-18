"""Acceptance tests for the durable shopping-task command boundary."""
from backend.intent.task_model import (
    DesiredBasketItem,
    MessageUnderstanding,
    ShoppingTask,
    TaskOperation,
    TaskState,
)
from backend.intent.task_reducer import InvalidTaskTransition, apply_understanding
from backend.intent.task_repository import InMemoryShoppingTaskRepository, TaskVersionConflict
from backend.intent.message_understanding import MessageUnderstandingService
from backend.intent.catalog_resolution import CatalogResolutionKind, CatalogResolver
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.intent.cart_adoption import record_cart_adoption, require_cart_adoption
from backend.integrations.commerce.models import CartItem, CommerceCart


def _understanding(
    operation: TaskOperation,
    *items: DesiredBasketItem,
    confidence: float = 1.0,
    missing_details: list[str] | None = None,
) -> MessageUnderstanding:
    return MessageUnderstanding(
        operation=operation,
        items=list(items),
        confidence=confidence,
        missing_details=missing_details or [],
        source="rules",
    )


def test_confirmed_preferences_require_basket_approval_before_provider_sync() -> None:
    task = ShoppingTask(task_id="task-1", customer_id="customer-1")
    milk = DesiredBasketItem(
        name="Amul Taaza Milk",
        quantity=1,
        unit="L",
        preference_source="confirmed_preference",
    )
    bread = DesiredBasketItem(
        name="Whole Wheat Brown Bread",
        quantity=1,
        preference_source="confirmed_preference",
    )

    previewed = apply_understanding(
        task, _understanding(TaskOperation.START_TASK, milk, bread)
    )

    assert previewed.state == TaskState.AWAITING_BASKET_APPROVAL
    assert previewed.pending_plan is not None
    assert [item.name for item in previewed.pending_plan.items] == [
        "Amul Taaza Milk",
        "Whole Wheat Brown Bread",
    ]
    assert previewed.desired_basket == []

    approved = apply_understanding(
        previewed, _understanding(TaskOperation.CONFIRM_BASKET)
    )
    assert approved.state == TaskState.SYNCHRONIZING_CART
    assert approved.pending_plan is not None
    assert approved.pending_plan.approved_at is not None


def test_ambiguous_free_text_never_creates_a_basket_plan() -> None:
    task = ShoppingTask(task_id="task-2", customer_id="customer-2")
    coke = DesiredBasketItem(name="Coke", quantity=3, unit="units")

    result = apply_understanding(
        task,
        _understanding(
            TaskOperation.START_TASK,
            coke,
            confidence=0.6,
            missing_details=["whether you mean cans, bottles, or multipacks for Coke"],
        ),
    )

    assert result.state == TaskState.NEEDS_DETAILS
    assert result.pending_plan is None
    assert "cans, bottles, or multipacks" in (result.pending_question or "")


def test_keep_only_replaces_desired_basket_with_preview_not_provider_mutation() -> None:
    task = ShoppingTask(
        task_id="task-3",
        customer_id="customer-3",
        desired_basket=[
            DesiredBasketItem(name="Coke", quantity=1),
            DesiredBasketItem(name="Vicks", quantity=1),
            DesiredBasketItem(name="Milk", quantity=1, unit="L"),
        ],
    )

    result = apply_understanding(
        task,
        _understanding(
            TaskOperation.KEEP_ONLY_ITEMS,
            DesiredBasketItem(name="Milk", quantity=1, unit="L"),
            DesiredBasketItem(name="Bread", quantity=1),
        ),
    )

    assert result.state == TaskState.AWAITING_BASKET_APPROVAL
    assert result.pending_plan is not None
    assert [item.name for item in result.pending_plan.items] == ["Milk", "Bread"]
    assert [item.name for item in result.desired_basket] == ["Coke", "Vicks", "Milk"]


def test_basket_confirmation_without_preview_is_rejected() -> None:
    task = ShoppingTask(task_id="task-4", customer_id="customer-4")

    try:
        apply_understanding(task, _understanding(TaskOperation.CONFIRM_BASKET))
    except InvalidTaskTransition as exc:
        assert "no proposed basket" in str(exc)
    else:
        raise AssertionError("Basket confirmation without a preview must be rejected.")


async def test_task_repository_rejects_duplicate_events_and_stale_writes() -> None:
    repository = InMemoryShoppingTaskRepository()
    task = ShoppingTask(task_id="task-5", customer_id="customer-5")
    await repository.create(task)

    assert await repository.record_inbound_event(
        provider="meta_whatsapp", message_id="wamid.1", payload={}, task_id=task.task_id
    )
    assert not await repository.record_inbound_event(
        provider="meta_whatsapp", message_id="wamid.1", payload={}, task_id=task.task_id
    )

    current = await repository.get_required(task.task_id)
    current.version += 1
    await repository.save(current, expected_version=1)

    try:
        await repository.save(task, expected_version=1)
    except TaskVersionConflict:
        pass
    else:
        raise AssertionError("A stale task write must not overwrite a newer turn.")


def test_natural_language_keep_only_and_ltr_are_understood_without_robotic_input() -> None:
    understanding = MessageUnderstandingService()

    keep_only = understanding.interpret("cancel other just have 1 ltr milk and 1 bread")

    assert keep_only.operation == TaskOperation.KEEP_ONLY_ITEMS
    assert [(item.name.casefold(), item.quantity, item.unit) for item in keep_only.items] == [
        ("milk", 1.0, "L"),
        ("bread", 1.0, "units"),
    ]


def test_human_language_variants_map_to_safe_basket_operations() -> None:
    understanding = MessageUnderstandingService()

    cases = {
        "remove everything except milk and bread": TaskOperation.KEEP_ONLY_ITEMS,
        "forget the rest, only keep milk": TaskOperation.KEEP_ONLY_ITEMS,
        "actually leave it": TaskOperation.CANCEL_PENDING_STEP,
        "start fresh with milk": TaskOperation.START_FRESH_CART,
        "add one more bread": TaskOperation.ADD_ITEMS,
        "replace coke with pepsi": TaskOperation.REPLACE_ITEM,
    }

    for message, operation in cases.items():
        assert understanding.interpret(message).operation == operation


def test_add_one_more_increments_a_preview_instead_of_overwriting_quantity() -> None:
    task = ShoppingTask(
        task_id="task-6",
        customer_id="customer-6",
        desired_basket=[DesiredBasketItem(name="Bread", quantity=1)],
    )
    result = apply_understanding(
        task,
        _understanding(TaskOperation.ADD_ITEMS, DesiredBasketItem(name="Bread", quantity=1)),
    )

    assert result.pending_plan is not None
    assert result.pending_plan.items[0].quantity == 2
    assert result.desired_basket[0].quantity == 1


def test_replace_edits_the_visible_basket_preview_before_provider_sync() -> None:
    task = ShoppingTask(
        task_id="task-replace",
        customer_id="customer-replace",
        desired_basket=[DesiredBasketItem(name="Coke", quantity=1)],
    )

    result = apply_understanding(
        task,
        MessageUnderstanding(
            operation=TaskOperation.REPLACE_ITEM,
            target_item="Coke",
            items=[DesiredBasketItem(name="Pepsi", quantity=1)],
            confidence=1,
            source="rules",
        ),
    )

    assert result.state == TaskState.AWAITING_BASKET_APPROVAL
    assert [item.name for item in result.pending_plan.items] == ["Pepsi"]


def test_start_fresh_records_an_explicit_cart_strategy_for_later_sync() -> None:
    task = ShoppingTask(task_id="task-fresh", customer_id="customer-fresh")

    result = apply_understanding(
        task,
        _understanding(TaskOperation.START_FRESH_CART, DesiredBasketItem(name="Milk", quantity=1)),
    )

    assert result.pending_plan is not None
    assert result.pending_plan.cart_strategy == "start_fresh"


async def test_catalogue_resolution_requires_a_choice_for_ambiguous_human_requests() -> None:
    resolver = CatalogResolver(MockCommerceAdapter())
    results = await resolver.resolve_basket(
        "addr-bandra-1",
        [
            DesiredBasketItem(name="Milk", quantity=1, unit="units"),
            DesiredBasketItem(name="Coke", quantity=3, unit="units"),
            DesiredBasketItem(name="Bread", quantity=1, unit="units"),
            DesiredBasketItem(name="Bhindi", quantity=1, unit="units"),
        ],
    )

    assert [result.kind for result in results] == [
        CatalogResolutionKind.AMBIGUOUS,
        CatalogResolutionKind.AMBIGUOUS,
        CatalogResolutionKind.EXACT,
        CatalogResolutionKind.UNAVAILABLE,
    ]


async def test_catalogue_resolution_accepts_a_single_exact_litre_pack() -> None:
    resolver = CatalogResolver(MockCommerceAdapter())

    result = await resolver.resolve_item(
        "addr-bandra-1", DesiredBasketItem(name="Milk", quantity=1, unit="L")
    )

    assert result.kind == CatalogResolutionKind.EXACT
    assert result.selected is not None
    assert result.selected.spin_id == "SPIN-MILK-1L"


def test_existing_provider_cart_requires_explicit_adoption_before_use() -> None:
    task = ShoppingTask(task_id="task-7", customer_id="customer-7")
    provider_cart = CommerceCart(
        cart_id="swiggy-active-cart",
        items=[
            CartItem(
                spin_id="SPIN-OLD-VICKS",
                name="Vicks Vaporub",
                pack_size="25 g",
                quantity=1,
                unit_price=109,
                total_price=109,
            )
        ],
    )

    assert not require_cart_adoption(task, provider_cart)
    assert task.state == TaskState.NEEDS_CART_ADOPTION
    assert "already in your Swiggy basket" in (task.pending_question or "")

    record_cart_adoption(task, TaskOperation.ADOPT_PROVIDER_CART)
    assert task.provider_cart.adopted_by_customer
    assert task.state == TaskState.READY


def test_address_change_invalidates_checkout_confirmation_and_requests_an_address() -> None:
    task = ShoppingTask(
        task_id="task-address",
        customer_id="customer-address",
        state=TaskState.AWAITING_CHECKOUT_CONFIRMATION,
        selected_address_id="address-old",
        confirmation_valid=True,
    )

    result = apply_understanding(task, _understanding(TaskOperation.CHANGE_ADDRESS))

    assert result.state == TaskState.NEEDS_ADDRESS
    assert result.selected_address_id is None
    assert not result.confirmation_valid


def test_selecting_address_uses_the_same_operation_for_text_and_buttons() -> None:
    service = MessageUnderstandingService()
    typed = service.interpret("use address 2")
    button = service.from_interactive(
        operation=TaskOperation.SELECT_ADDRESS,
        selection_value="address-2",
    )

    assert typed.operation == button.operation == TaskOperation.SELECT_ADDRESS
    assert typed.selection_value == "2"
    assert button.selection_value == "address-2"


def test_address_and_payment_selection_invalidate_any_previous_confirmation() -> None:
    address_task = ShoppingTask(
        task_id="task-select-address",
        customer_id="customer-select-address",
        state=TaskState.AWAITING_CHECKOUT_CONFIRMATION,
        confirmation_valid=True,
    )
    address_result = apply_understanding(
        address_task,
        MessageUnderstanding(
            operation=TaskOperation.SELECT_ADDRESS,
            selection_value="address-2",
            confidence=1,
            source="interactive",
        ),
    )
    assert address_result.selected_address_id == "address-2"
    assert address_result.state == TaskState.NEEDS_PAYMENT
    assert not address_result.confirmation_valid

    payment_result = apply_understanding(
        address_result,
        MessageUnderstanding(
            operation=TaskOperation.SELECT_PAYMENT,
            selection_value="cod",
            confidence=1,
            source="interactive",
        ),
    )
    assert payment_result.selected_payment_method == "cod"
    assert payment_result.state == TaskState.AWAITING_CHECKOUT_CONFIRMATION
    assert not payment_result.confirmation_valid


def test_set_quantity_changes_only_the_named_item_and_invalidates_confirmation() -> None:
    task = ShoppingTask(
        task_id="task-quantity",
        customer_id="customer-quantity",
        state=TaskState.AWAITING_CHECKOUT_CONFIRMATION,
        desired_basket=[
            DesiredBasketItem(name="Milk", quantity=1, unit="L"),
            DesiredBasketItem(name="Bread", quantity=1),
        ],
        confirmation_valid=True,
    )

    result = apply_understanding(
        task,
        MessageUnderstanding(
            operation=TaskOperation.SET_QUANTITY,
            target_item="Bread",
            quantity=3,
            confidence=1,
            source="rules",
        ),
    )

    assert result.state == TaskState.AWAITING_BASKET_APPROVAL
    assert [(item.name, item.quantity) for item in result.pending_plan.items] == [
        ("Milk", 1),
        ("Bread", 3),
    ]
    assert not result.confirmation_valid


def test_product_choice_updates_the_requested_item_and_invalidates_confirmation() -> None:
    task = ShoppingTask(
        task_id="task-product-choice",
        customer_id="customer-product-choice",
        state=TaskState.NEEDS_PRODUCT_CHOICE,
        desired_basket=[DesiredBasketItem(name="Milk", quantity=1)],
        confirmation_valid=True,
    )

    result = apply_understanding(
        task,
        MessageUnderstanding(
            operation=TaskOperation.SELECT_PRODUCT,
            target_item="Milk",
            selection_value="SPIN-MILK-1L",
            selected_sku_id="SKU-MILK-1L",
            confidence=1,
            source="interactive",
        ),
    )

    assert result.pending_plan is not None
    assert result.pending_plan.items[0].selected_spin_id == "SPIN-MILK-1L"
    assert result.pending_plan.items[0].selected_sku_id == "SKU-MILK-1L"
    assert not result.confirmation_valid


def test_cancel_task_is_terminal_while_help_and_tracking_preserve_state() -> None:
    task = ShoppingTask(
        task_id="task-control",
        customer_id="customer-control",
        state=TaskState.NEEDS_PAYMENT,
        desired_basket=[DesiredBasketItem(name="Bread", quantity=1)],
    )

    helped = apply_understanding(
        task.model_copy(deep=True), _understanding(TaskOperation.ASK_FOR_HELP)
    )
    tracked = apply_understanding(
        task.model_copy(deep=True), _understanding(TaskOperation.TRACK_ORDER)
    )
    cancelled = apply_understanding(task, _understanding(TaskOperation.CANCEL_TASK))

    assert helped.state == TaskState.NEEDS_PAYMENT
    assert helped.pending_question is not None
    assert tracked.state == TaskState.NEEDS_PAYMENT
    assert tracked.requested_action == TaskOperation.TRACK_ORDER
    assert cancelled.state == TaskState.CANCELLED
    assert cancelled.pending_plan is None
    assert not cancelled.confirmation_valid


def test_unknown_or_low_confidence_text_clarifies_instead_of_starting_a_task() -> None:
    service = MessageUnderstandingService()

    unknown = service.interpret("do the usual thing maybe")
    low_confidence = service.interpret("something for tonight")

    assert unknown.operation == TaskOperation.CLARIFY
    assert unknown.needs_clarification
    assert low_confidence.operation == TaskOperation.CLARIFY
    assert low_confidence.needs_clarification


def test_common_control_language_maps_to_typed_operations() -> None:
    service = MessageUnderstandingService()

    cases = {
        "change address": TaskOperation.CHANGE_ADDRESS,
        "change payment method": TaskOperation.CHANGE_PAYMENT,
        "pay by cash on delivery": TaskOperation.SELECT_PAYMENT,
        "make bread 3": TaskOperation.SET_QUANTITY,
        "cancel my order": TaskOperation.CANCEL_TASK,
        "help": TaskOperation.ASK_FOR_HELP,
        "track my order": TaskOperation.TRACK_ORDER,
    }

    for message, expected in cases.items():
        assert service.interpret(message).operation == expected
