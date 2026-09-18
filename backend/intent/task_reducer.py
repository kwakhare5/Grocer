"""Deterministic transition rules for durable shopping tasks."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.intent.task_model import (
    BasketPlan,
    DesiredBasketItem,
    MessageUnderstanding,
    ShoppingTask,
    TaskOperation,
    TaskState,
)


class InvalidTaskTransition(ValueError):
    """Raised when a proposed language meaning is unsafe in the current task state."""


def apply_understanding(task: ShoppingTask, understanding: MessageUnderstanding) -> ShoppingTask:
    """Apply a safe language proposal without touching an external provider.

    This reducer intentionally creates a full basket *preview*. It never calls
    Swiggy and never treats uncertain language as authority to mutate a cart.
    """
    if understanding.needs_clarification:
        task.state = TaskState.NEEDS_DETAILS
        task.pending_question = _clarification_question(understanding)
        return _advance(task)

    task.requested_action = None

    if understanding.operation == TaskOperation.CLARIFY:
        task.state = TaskState.NEEDS_DETAILS
        task.pending_question = "I want to get this right. Could you say that another way?"
        return _advance(task)

    if understanding.operation in {TaskOperation.START_TASK, TaskOperation.SET_ITEMS}:
        return _preview(task, understanding.items)

    if understanding.operation == TaskOperation.START_FRESH_CART:
        return _preview(task, understanding.items, cart_strategy="start_fresh")

    if understanding.operation == TaskOperation.ADD_ITEMS:
        return _preview(task, _add_to_basket(_effective_basket(task), understanding.items))

    if understanding.operation == TaskOperation.KEEP_ONLY_ITEMS:
        return _preview(task, understanding.items)

    if understanding.operation == TaskOperation.REMOVE_ITEMS:
        target_names = {item.name.casefold() for item in understanding.items}
        basket = _effective_basket(task)
        remaining = [
            item for item in basket if item.name.casefold() not in target_names
        ]
        if len(remaining) == len(basket):
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "I could not tell which basket item you want to remove."
            return _advance(task)
        return _preview(task, remaining)

    if understanding.operation == TaskOperation.REPLACE_ITEM:
        if not understanding.target_item:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "Which basket item would you like to replace?"
            return _advance(task)
        basket = _effective_basket(task)
        target = understanding.target_item.casefold().strip()
        remaining = [item for item in basket if item.name.casefold() != target]
        if len(remaining) == len(basket):
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = (
                f"I could not find '{understanding.target_item}' in this shopping task. "
                "Please choose an item from the basket to replace."
            )
            return _advance(task)
        return _preview(task, _add_to_basket(remaining, understanding.items))

    if understanding.operation == TaskOperation.SET_QUANTITY:
        if not understanding.target_item or understanding.quantity is None:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "Which item and quantity would you like to change?"
            return _advance(task)
        basket = [item.model_copy(deep=True) for item in _effective_basket(task)]
        target = understanding.target_item.casefold().strip()
        selected = next((item for item in basket if item.name.casefold() == target), None)
        if selected is None:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = (
                f"I could not find '{understanding.target_item}' in your basket."
            )
            return _advance(task)
        selected.quantity = understanding.quantity
        selected.quantity_is_explicit = True
        return _preview(task, basket)

    if understanding.operation == TaskOperation.SELECT_PRODUCT:
        if not understanding.target_item or not understanding.selection_value:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "Which product would you like to choose?"
            return _advance(task)
        basket = [item.model_copy(deep=True) for item in _effective_basket(task)]
        target = understanding.target_item.casefold().strip()
        selected = next((item for item in basket if item.name.casefold() == target), None)
        if selected is None:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = (
                f"I could not find '{understanding.target_item}' in your basket."
            )
            return _advance(task)
        selected.selected_spin_id = understanding.selection_value
        selected.selected_sku_id = understanding.selected_sku_id
        return _preview(task, basket)

    if understanding.operation == TaskOperation.CHANGE_ADDRESS:
        _invalidate_confirmation(task)
        task.selected_address_id = None
        task.state = TaskState.NEEDS_ADDRESS
        task.pending_question = "Which saved address would you like to use?"
        return _advance(task)

    if understanding.operation == TaskOperation.SELECT_ADDRESS:
        if not understanding.selection_value:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "Which saved address would you like to use?"
            return _advance(task)
        _invalidate_confirmation(task)
        task.selected_address_id = understanding.selection_value
        task.state = TaskState.NEEDS_PAYMENT
        task.pending_question = "How would you like to pay?"
        return _advance(task)

    if understanding.operation == TaskOperation.CHANGE_PAYMENT:
        _invalidate_confirmation(task)
        task.selected_payment_method = None
        task.state = TaskState.NEEDS_PAYMENT
        task.pending_question = "How would you like to pay?"
        return _advance(task)

    if understanding.operation == TaskOperation.SELECT_PAYMENT:
        if not understanding.selection_value:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "Which payment method would you like to use?"
            return _advance(task)
        _invalidate_confirmation(task)
        task.selected_payment_method = understanding.selection_value
        task.state = TaskState.AWAITING_CHECKOUT_CONFIRMATION
        task.pending_question = None
        return _advance(task)

    if understanding.operation == TaskOperation.CANCEL_PENDING_STEP:
        task.pending_plan = None
        task.pending_stock_recovery = None
        task.pending_question = None
        task.state = TaskState.READY if not task.desired_basket else TaskState.NEEDS_DETAILS
        return _advance(task)

    if understanding.operation == TaskOperation.CANCEL_TASK:
        _invalidate_confirmation(task)
        task.pending_plan = None
        task.pending_stock_recovery = None
        task.pending_question = None
        task.state = TaskState.CANCELLED
        return _advance(task)

    if understanding.operation == TaskOperation.ASK_FOR_HELP:
        task.pending_question = (
            "Tell me what groceries you need, or ask to change your basket, address, "
            "payment, or order status."
        )
        return _advance(task)

    if understanding.operation == TaskOperation.TRACK_ORDER:
        task.requested_action = TaskOperation.TRACK_ORDER
        return _advance(task)

    if understanding.operation == TaskOperation.CONFIRM_BASKET:
        if task.state != TaskState.AWAITING_BASKET_APPROVAL or task.pending_plan is None:
            raise InvalidTaskTransition("There is no proposed basket to approve.")
        task.pending_plan.approved_at = datetime.now(timezone.utc)
        task.state = TaskState.SYNCHRONIZING_CART
        task.pending_question = None
        return _advance(task)

    if understanding.operation == TaskOperation.CONFIRM_CHECKOUT:
        if task.state != TaskState.AWAITING_CHECKOUT_CONFIRMATION:
            raise InvalidTaskTransition("There is no checkout summary to confirm.")
        task.confirmation_valid = True
        task.state = TaskState.PAYMENT_PENDING
        task.pending_question = None
        return _advance(task)

    raise InvalidTaskTransition(
        f"{understanding.operation.value} is not handled by the basket reducer."
    )


def _preview(
    task: ShoppingTask,
    items: list[DesiredBasketItem],
    *,
    cart_strategy: str = "reuse",
) -> ShoppingTask:
    _invalidate_confirmation(task)
    task.pending_stock_recovery = None
    if not items:
        task.state = TaskState.NEEDS_DETAILS
        task.pending_question = "What would you like to keep in your basket?"
        return _advance(task)
    next_version = task.version + 1
    task.pending_plan = BasketPlan(
        version=next_version,
        items=items,
        cart_strategy=cart_strategy,
    )
    task.state = TaskState.AWAITING_BASKET_APPROVAL
    task.pending_question = None
    return _advance(task)


def _add_to_basket(
    existing: list[DesiredBasketItem], additions: list[DesiredBasketItem]
) -> list[DesiredBasketItem]:
    by_name = {item.name.casefold(): item for item in existing}
    for item in additions:
        current = by_name.get(item.name.casefold())
        if current is not None and current.unit == item.unit:
            current.quantity += item.quantity
        else:
            by_name[item.name.casefold()] = item
    return list(by_name.values())


def _effective_basket(task: ShoppingTask) -> list[DesiredBasketItem]:
    """Use the outstanding plan until its basket projection has been verified."""
    if task.pending_plan is not None:
        return [item.model_copy(deep=True) for item in task.pending_plan.items]
    return [item.model_copy(deep=True) for item in task.desired_basket]


def _clarification_question(understanding: MessageUnderstanding) -> str:
    details = understanding.missing_details or understanding.ambiguities
    if details:
        return f"I want to get this right. Please clarify: {details[0]}."
    return "I want to get this right. Could you say that another way?"


def _advance(task: ShoppingTask) -> ShoppingTask:
    # Choices belong only to the question that displayed them. The response
    # renderer records the next visible set before the task is persisted.
    task.offered_choices = []
    task.version += 1
    task.updated_at = datetime.now(timezone.utc)
    return task


def _invalidate_confirmation(task: ShoppingTask) -> None:
    task.confirmation_valid = False
    task.checkout_confirmation = None
