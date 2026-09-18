"""Application service for one deterministic shopping-task conversation path.

This module is deliberately channel- and provider-neutral. It is the sole place
that sequences language understanding, task transitions, persistence, and
commerce side effects for the production durable route.
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
import logging
import math
import re
from dataclasses import dataclass
from typing import Literal

from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    DeliveryAddress,
    PaymentOption,
)
from backend.integrations.commerce.exceptions import (
    AddressNotServiceableError,
    CartExpiredError,
    CommerceError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    ProviderAuthError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.port import CommercePort
from backend.intent.cart_adoption import record_cart_adoption, require_cart_adoption
from backend.intent.catalog_resolution import (
    CatalogResolution,
    CatalogCandidate,
    CatalogResolutionKind,
    CatalogResolver,
)
from backend.intent.message_understanding import MessageUnderstandingService
from backend.intent.task_model import (
    BasketPlan,
    CheckoutConfirmationSnapshot,
    MessageUnderstanding,
    OfferedChoice,
    ShoppingTask,
    StockRecovery,
    TaskOperation,
    TaskState,
)
from backend.intent.task_reducer import InvalidTaskTransition, apply_understanding
from backend.intent.task_repository import ShoppingTaskRepository


logger = logging.getLogger("grocer.intent.task_service")


@dataclass(frozen=True)
class TaskTurnResult:
    """Result used by transports to suppress duplicate deliveries."""

    response: NormalizedOutgoingResponse
    processed: bool


class ShoppingTaskApplicationService:
    """Process one normalized message through one authoritative task path."""

    def __init__(
        self,
        repository: ShoppingTaskRepository,
        commerce: CommercePort,
        *,
        checkout_mode: Literal["review", "live"] = "review",
        understanding: MessageUnderstandingService | None = None,
    ) -> None:
        self._repository = repository
        self._commerce = commerce
        self._checkout_mode = checkout_mode
        self._understanding = understanding or MessageUnderstandingService()
        self._resolver = CatalogResolver(commerce)

    async def handle_message(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        """Handle a normalized turn; retained as the channel-neutral API."""
        result = await self.process_message(message)
        return result.response

    async def process_message(
        self, message: NormalizedIncomingMessage
    ) -> TaskTurnResult:
        """Handle one turn and report whether it caused a new transition."""
        task_id = message.customer_id or message.sender_id
        task = await self._repository.get(task_id)
        if task is None:
            task = await self._repository.create(
                ShoppingTask(task_id=task_id, customer_id=task_id)
            )

        is_new = await self._repository.record_inbound_event(
            provider=message.channel.value,
            message_id=message.message_id,
            payload=message.raw_payload or {"text": message.text},
            task_id=task_id,
        )
        if not is_new:
            pending_payload = await self._repository.get_pending_outbound_message(
                task_id=task_id,
                message_id=message.message_id,
            )
            if pending_payload is not None:
                return TaskTurnResult(
                    response=NormalizedOutgoingResponse.model_validate(pending_payload),
                    processed=True,
                )
            return TaskTurnResult(
                response=self._response(
                    message,
                    task.state,
                    "I already received that message, so I did not apply it again.",
                ),
                processed=False,
            )

        expected_version = task.version
        customer_scope = getattr(self._commerce, "customer_scope", None)
        scope = (
            customer_scope(task.customer_id)
            if callable(customer_scope)
            else nullcontext()
        )
        original_state = task.state
        try:
            with scope:
                return await self._process_recorded_message(
                    task,
                    message,
                    expected_version=expected_version,
                )
        except ItemOutOfStockError as exc:
            recovery = self._out_of_stock_recovery(task, exc)
            if recovery is not None:
                response = self._stock_recovery_response(task, message, recovery)
                if task.version != expected_version:
                    await self._repository.save(task, expected_version=expected_version)
                await self._repository.enqueue_outbound_message(
                    task_id=task.task_id,
                    message_id=message.message_id,
                    payload=response.model_dump(mode="json"),
                )
                return TaskTurnResult(response=response, processed=True)
            text = "That item is no longer available on Swiggy. Your basket is unchanged."
            response = self._response(message, original_state, text)
            await self._repository.enqueue_outbound_message(
                task_id=task.task_id,
                message_id=message.message_id,
                payload=response.model_dump(mode="json"),
            )
            return TaskTurnResult(response=response, processed=True)
        except CommerceError as exc:
            logger.warning(
                "Commerce operation failed for task=%s code=%s provider=%s",
                task.task_id,
                exc.code,
                exc.provider,
            )
            text = self._commerce_error_message(exc)
            response = self._response(message, original_state, text)
            await self._repository.enqueue_outbound_message(
                task_id=task.task_id,
                message_id=message.message_id,
                payload=response.model_dump(mode="json"),
            )
            return TaskTurnResult(response=response, processed=True)

    @staticmethod
    def _commerce_error_message(exc: CommerceError) -> str:
        if isinstance(exc, ProviderAuthError):
            return (
                "Your Swiggy connection needs attention. Your basket is unchanged. "
                "Please reconnect Swiggy from the Grocer website, then try again."
            )
        if isinstance(exc, AddressNotServiceableError):
            return "That saved address is not serviceable right now. Please choose another address."
        if isinstance(exc, CartExpiredError):
            return "Your Swiggy basket expired. Your grocery plan is saved; please review it again."
        if isinstance(exc, MinOrderNotMetError):
            return "Your basket is below Swiggy's minimum order value. Add another item or change it."
        if isinstance(exc, UpstreamTimeoutError):
            return (
                "Swiggy took too long to respond. I did not claim that your basket changed. "
                "Please try again so I can verify it first."
            )
        return "I could not complete that with Swiggy right now. Your basket is unchanged. Please try again."

    async def mark_response_sent(self, message: NormalizedIncomingMessage) -> None:
        task_id = message.customer_id or message.sender_id
        await self._repository.mark_outbound_sent(
            task_id=task_id,
            message_id=message.message_id,
        )

    async def _process_recorded_message(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        *,
        expected_version: int,
    ) -> TaskTurnResult:
        """Apply one already-deduplicated message within its customer scope."""
        meaning = await self._meaning_for(task, message)

        if task.state == TaskState.NEEDS_CART_ADOPTION:
            response = await self._handle_cart_choice(task, meaning, message)
        elif task.state == TaskState.NEEDS_STOCK_DECISION:
            response = await self._handle_stock_choice(task, meaning, message)
        elif (
            meaning.operation == TaskOperation.CONFIRM_CHECKOUT
            and task.state == TaskState.AWAITING_CHECKOUT_CONFIRMATION
            and self._checkout_mode == "review"
        ):
            response = await self._checkout_confirmation_response(
                task,
                message,
                review_complete=True,
            )
        elif meaning.operation == TaskOperation.SELECT_PAYMENT:
            response = await self._select_payment(task, meaning, message)
        else:
            try:
                apply_understanding(task, meaning)
            except InvalidTaskTransition:
                task.state = TaskState.NEEDS_DETAILS
                task.pending_question = (
                    "That action does not apply here. Tell me what you want to change."
                )
                task.version += 1

            if (
                meaning.operation == TaskOperation.CHANGE_ADDRESS
                and task.desired_basket
                and task.pending_plan is None
            ):
                task.pending_plan = BasketPlan(
                    version=task.version,
                    items=[item.model_copy(deep=True) for item in task.desired_basket],
                    cart_strategy="start_fresh",
                )

            if (
                meaning.operation == TaskOperation.SELECT_ADDRESS
                and task.pending_plan is not None
            ):
                task.state = (
                    TaskState.SYNCHRONIZING_CART
                    if task.pending_plan.approved_at is not None
                    else TaskState.AWAITING_BASKET_APPROVAL
                )

            if task.state == TaskState.SYNCHRONIZING_CART:
                response = await self._synchronize(task, message)
            elif task.state == TaskState.NEEDS_ADDRESS:
                response = await self._address_response(task, message)
            elif task.state == TaskState.AWAITING_CHECKOUT_CONFIRMATION:
                response = await self._checkout_confirmation_response(task, message)
            else:
                response = self._render(task, message)

        if task.version != expected_version:
            await self._repository.save(task, expected_version=expected_version)
        await self._repository.enqueue_outbound_message(
            task_id=task.task_id,
            message_id=message.message_id,
            payload=response.model_dump(mode="json"),
        )
        return TaskTurnResult(response=response, processed=True)

    async def _meaning_for(
        self, task: ShoppingTask, message: NormalizedIncomingMessage
    ) -> MessageUnderstanding:
        interactive = self._interactive_meaning(task, message.interactive_id)
        if interactive is not None:
            return interactive

        normalized = " ".join(message.text.casefold().split()).strip(" .!?")
        selected_choice = self._choice_from_text(task, normalized)
        if selected_choice is not None:
            return selected_choice
        if task.state == TaskState.NEEDS_CART_ADOPTION:
            if normalized in {"keep", "keep it", "keep them", "keep my cart", "use those"}:
                return self._proposal(TaskOperation.ADOPT_PROVIDER_CART)
            if normalized in {"start fresh", "fresh", "clear it", "new basket", "start over"}:
                return self._proposal(TaskOperation.START_FRESH_CART)
        if normalized in {"yes", "confirm", "looks good", "go ahead"}:
            operation = (
                TaskOperation.CONFIRM_BASKET
                if task.state == TaskState.AWAITING_BASKET_APPROVAL
                else TaskOperation.CONFIRM_CHECKOUT
            )
            return self._proposal(operation)
        proposal = await self._understanding.interpret(
            message.text,
            context=self._understanding_context(task),
        )
        return self._validate_model_selection(task, proposal)

    @staticmethod
    def _understanding_context(task: ShoppingTask) -> dict[str, object]:
        basket = task.pending_plan.items if task.pending_plan else task.desired_basket
        return {
            "task_state": task.state.value,
            "pending_question": task.pending_question,
            "basket_items": [item.name for item in basket],
            "selected_address_id": task.selected_address_id,
            "selected_payment_method": task.selected_payment_method,
            "visible_choices": [
                choice.model_dump(mode="json") for choice in task.offered_choices
            ],
        }

    def _interactive_meaning(
        self, task: ShoppingTask, action_id: str | None
    ) -> MessageUnderstanding | None:
        if not action_id:
            return None
        if task.offered_choices and action_id not in {
            choice.action_id for choice in task.offered_choices
        }:
            return None
        operation_by_id = {
            "confirm_basket": TaskOperation.CONFIRM_BASKET,
            "confirm_checkout": TaskOperation.CONFIRM_CHECKOUT,
            "keep_cart": TaskOperation.ADOPT_PROVIDER_CART,
            "start_fresh": TaskOperation.START_FRESH_CART,
            "cancel": TaskOperation.CANCEL_TASK,
            "change_address": TaskOperation.CHANGE_ADDRESS,
            "change_payment": TaskOperation.CHANGE_PAYMENT,
        }
        if action_id in operation_by_id:
            return self._proposal(operation_by_id[action_id], source="interactive")
        for prefix, operation in (
            ("select_address:", TaskOperation.SELECT_ADDRESS),
            ("select_payment:", TaskOperation.SELECT_PAYMENT),
        ):
            if action_id.startswith(prefix):
                return self._proposal(
                    operation,
                    selection_value=action_id.removeprefix(prefix),
                    source="interactive",
                )
        if action_id.startswith("select_product:"):
            _, target_item, spin_id = action_id.split(":", maxsplit=2)
            return MessageUnderstanding(
                operation=TaskOperation.SELECT_PRODUCT,
                target_item=target_item,
                selection_value=spin_id,
                confidence=1,
                source="interactive",
            )
        for prefix, operation in (
            ("stock_keep_available:", TaskOperation.ACCEPT_AVAILABLE_QUANTITY),
            ("stock_substitute:", TaskOperation.CHOOSE_SUBSTITUTE),
            ("stock_remove:", TaskOperation.REMOVE_ITEMS),
        ):
            if action_id.startswith(prefix):
                return self._proposal(
                    operation,
                    selection_value=action_id.removeprefix(prefix),
                    source="interactive",
                )
        return None

    def _choice_from_text(
        self, task: ShoppingTask, normalized: str
    ) -> MessageUnderstanding | None:
        """Resolve a bounded text reference against exactly what we displayed."""
        choices = task.offered_choices
        if not choices:
            return None

        selected: OfferedChoice | None = None
        ordinal = self._choice_ordinal(normalized)
        if ordinal is not None and 0 <= ordinal < len(choices):
            selected = choices[ordinal]
        elif normalized in {choice.title.casefold() for choice in choices}:
            selected = next(
                choice for choice in choices if choice.title.casefold() == normalized
            )
        elif "cheap" in normalized:
            products = [
                choice for choice in choices if choice.action_id.startswith("select_product:")
            ]
            if products:
                selected = min(products, key=self._choice_price)

        return (
            self._interactive_meaning(task, selected.action_id) if selected is not None else None
        )

    @staticmethod
    def _choice_ordinal(normalized: str) -> int | None:
        word_positions = {
            "first": 0,
            "second": 1,
            "third": 2,
            "fourth": 3,
            "fifth": 4,
        }
        if normalized in word_positions:
            return word_positions[normalized]
        match = re.fullmatch(r"(?:the )?(first|second|third|fourth|fifth)(?: one)?", normalized)
        if match:
            return word_positions[match.group(1)]
        match = re.fullmatch(r"(?:option )?([1-5])", normalized)
        return int(match.group(1)) - 1 if match else None

    @staticmethod
    def _choice_price(choice: OfferedChoice) -> float:
        match = re.search(r"₹\s*(\d+(?:\.\d+)?)", choice.description or "")
        return float(match.group(1)) if match else math.inf

    def _validate_model_selection(
        self, task: ShoppingTask, proposal: MessageUnderstanding
    ) -> MessageUnderstanding:
        """Only accept a model selection when it names a persisted visible action."""
        action_id: str | None = None
        if proposal.operation == TaskOperation.SELECT_OPTION:
            action_id = proposal.selection_value
        elif proposal.operation == TaskOperation.SELECT_PRODUCT and proposal.selection_value:
            action_id = (
                proposal.selection_value
                if proposal.selection_value.startswith("select_product:")
                else f"select_product:{proposal.target_item or ''}:{proposal.selection_value}"
            )
        elif proposal.operation == TaskOperation.SELECT_ADDRESS and proposal.selection_value:
            action_id = (
                proposal.selection_value
                if proposal.selection_value.startswith("select_address:")
                else f"select_address:{proposal.selection_value}"
            )
        elif proposal.operation == TaskOperation.SELECT_PAYMENT and proposal.selection_value:
            action_id = (
                proposal.selection_value
                if proposal.selection_value.startswith("select_payment:")
                else f"select_payment:{proposal.selection_value}"
            )
        if action_id:
            selected = self._interactive_meaning(task, action_id)
            if selected is not None:
                return selected
            return self._proposal(TaskOperation.CLARIFY)
        return proposal

    @staticmethod
    def _remember_choices(
        task: ShoppingTask, actions: list[InteractiveAction]
    ) -> None:
        offered = [
            OfferedChoice(
                action_id=action.id,
                title=action.title,
                description=action.description,
            )
            for action in actions
        ]
        if task.offered_choices == offered:
            return
        task.offered_choices = offered
        task.version += 1
        task.updated_at = datetime.now(timezone.utc)

    async def _handle_cart_choice(
        self,
        task: ShoppingTask,
        meaning: MessageUnderstanding,
        message: NormalizedIncomingMessage,
    ) -> NormalizedOutgoingResponse:
        if meaning.operation == TaskOperation.CANCEL_TASK:
            apply_understanding(task, meaning)
            return self._render(task, message)
        if meaning.operation not in {
            TaskOperation.ADOPT_PROVIDER_CART,
            TaskOperation.START_FRESH_CART,
        }:
            return self._cart_adoption_response(task, message)

        record_cart_adoption(task, meaning.operation)
        task.version += 1
        if task.pending_plan is None or task.pending_plan.approved_at is None:
            return self._render(task, message)
        task.pending_plan.cart_strategy = (
            "reuse"
            if meaning.operation == TaskOperation.ADOPT_PROVIDER_CART
            else "start_fresh"
        )
        task.state = TaskState.SYNCHRONIZING_CART
        return await self._synchronize(task, message)

    async def _synchronize(
        self, task: ShoppingTask, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        plan = task.pending_plan
        if plan is None:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "I no longer have a basket to approve. Please try again."
            return self._render(task, message)
        if not task.selected_address_id:
            task.state = TaskState.NEEDS_ADDRESS
            task.pending_question = "Which saved address would you like to use?"
            return await self._address_response(task, message)

        provider_cart = await self._commerce.get_cart(task.provider_cart.cart_id)
        if plan.cart_strategy != "start_fresh" and not require_cart_adoption(
            task, provider_cart
        ):
            return self._cart_adoption_response(task, message)

        resolutions = await self._resolver.resolve_basket(
            task.selected_address_id, plan.items
        )
        unresolved = next(
            (
                result
                for result in resolutions
                if result.kind != CatalogResolutionKind.EXACT
            ),
            None,
        )
        if unresolved is not None:
            return self._resolution_failure(task, message, unresolved)

        # Preserve the provider-grounded variant on the pending plan before a
        # cart call. If Swiggy rejects it as newly out of stock, recovery can
        # identify the exact customer item without guessing.
        for item, resolution in zip(plan.items, resolutions, strict=True):
            assert resolution.selected is not None
            item.selected_spin_id = resolution.selected.spin_id
            item.selected_sku_id = resolution.selected.sku_id

        updates = self._updates_for(resolutions)
        if plan.cart_strategy == "reuse":
            updates = self._merge_existing_updates(provider_cart, updates)
        updated = await self._commerce.update_cart(
            updates,
            cart_id=provider_cart.cart_id,
            address_id=task.selected_address_id,
        )
        verified = await self._commerce.get_cart(updated.cart_id)
        shortfall = self._first_stock_shortfall(plan, resolutions, verified)
        if shortfall is not None:
            return self._stock_recovery_response(task, message, shortfall)
        if not self._cart_matches(updates, verified):
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = (
                "Swiggy did not return the complete basket I expected. I have stopped "
                "before checkout so you can review it."
            )
            return self._render(task, message)

        task.desired_basket = [item.model_copy(deep=True) for item in plan.items]
        for item, resolution in zip(task.desired_basket, resolutions, strict=True):
            assert resolution.selected is not None
            item.selected_spin_id = resolution.selected.spin_id
            item.selected_sku_id = resolution.selected.sku_id
        task.pending_plan = None
        task.provider_cart.cart_id = verified.cart_id
        task.state = TaskState.NEEDS_PAYMENT
        task.pending_question = "How would you like to pay?"
        return await self._payment_response(
            task,
            message,
            lead=f"Your Swiggy basket is verified with {len(verified.items)} item(s).",
        )

    @staticmethod
    def _first_stock_shortfall(
        plan: BasketPlan,
        resolutions: list[CatalogResolution],
        verified: CommerceCart,
    ) -> StockRecovery | None:
        """Return one verified shortfall; never silently accept a provider cap."""
        quantities_by_spin = {item.spin_id: item.quantity for item in verified.items}
        for planned, resolution in zip(plan.items, resolutions, strict=True):
            if resolution.selected is None:
                continue
            available = quantities_by_spin.get(resolution.selected.spin_id, 0)
            if available < planned.quantity:
                return StockRecovery(
                    item_name=planned.name,
                    requested_quantity=planned.quantity,
                    available_quantity=available,
                    spin_id=resolution.selected.spin_id,
                    sku_id=resolution.selected.sku_id,
                )
        return None

    @staticmethod
    def _out_of_stock_recovery(
        task: ShoppingTask, exc: ItemOutOfStockError
    ) -> StockRecovery | None:
        if task.pending_plan is None:
            return None
        item = next(
            (
                planned
                for planned in task.pending_plan.items
                if planned.selected_spin_id == exc.spin_id
            ),
            None,
        )
        if item is None:
            return None
        return StockRecovery(
            item_name=item.name,
            requested_quantity=item.quantity,
            available_quantity=exc.available_quantity,
            spin_id=exc.spin_id,
            sku_id=item.selected_sku_id,
        )

    async def _handle_stock_choice(
        self,
        task: ShoppingTask,
        meaning: MessageUnderstanding,
        message: NormalizedIncomingMessage,
    ) -> NormalizedOutgoingResponse:
        recovery = task.pending_stock_recovery
        plan = task.pending_plan
        if recovery is None or plan is None:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = "Please tell me how you would like to update your basket."
            return self._render(task, message)
        if meaning.operation == TaskOperation.CANCEL_TASK:
            apply_understanding(task, meaning)
            return self._render(task, message)

        selected = next(
            (item for item in plan.items if item.name.casefold() == recovery.item_name.casefold()),
            None,
        )
        if selected is None:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_stock_recovery = None
            task.pending_question = "I could not find that item in your proposed basket."
            task.version += 1
            return self._render(task, message)

        if meaning.operation == TaskOperation.ACCEPT_AVAILABLE_QUANTITY:
            if recovery.available_quantity <= 0:
                return self._stock_recovery_response(task, message, recovery)
            selected.quantity = recovery.available_quantity
            return self._reapprove_after_stock_change(task, message)

        if meaning.operation == TaskOperation.REMOVE_ITEMS:
            plan.items = [
                item for item in plan.items if item.name.casefold() != recovery.item_name.casefold()
            ]
            return self._reapprove_after_stock_change(task, message)

        if meaning.operation == TaskOperation.CHOOSE_SUBSTITUTE:
            selected.selected_spin_id = None
            selected.selected_sku_id = None
            plan.approved_at = None
            plan.cart_strategy = "start_fresh"
            task.pending_stock_recovery = None
            task.pending_question = f"Which alternative to {recovery.item_name} would you like?"
            task.state = TaskState.NEEDS_PRODUCT_CHOICE
            task.version += 1
            alternatives = await self._resolver.candidates_for(
                task.selected_address_id or "",
                selected,
                exclude_spin_ids={recovery.spin_id},
            )
            if not alternatives:
                task.state = TaskState.NEEDS_DETAILS
                task.pending_question = (
                    f"I could not find another available option for {recovery.item_name}. "
                    "You can remove it or tell me what you would like instead."
                )
                return self._render(task, message)
            return self._product_choices_response(
                task,
                message,
                selected.name,
                alternatives,
                lead=task.pending_question,
            )
        return self._stock_recovery_response(task, message, recovery)

    def _reapprove_after_stock_change(
        self, task: ShoppingTask, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        plan = task.pending_plan
        assert plan is not None
        task.pending_stock_recovery = None
        plan.approved_at = None
        plan.cart_strategy = "start_fresh"
        task.state = TaskState.AWAITING_BASKET_APPROVAL
        task.pending_question = None
        task.confirmation_valid = False
        task.checkout_confirmation = None
        task.version += 1
        return self._render(task, message)

    def _stock_recovery_response(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        recovery: StockRecovery,
    ) -> NormalizedOutgoingResponse:
        task.pending_stock_recovery = recovery
        task.state = TaskState.NEEDS_STOCK_DECISION
        task.pending_question = (
            f"Swiggy has only {recovery.available_quantity:g} of {recovery.item_name} "
            f"instead of {recovery.requested_quantity:g}. What would you like to do?"
        )
        actions = [
            *(
                [
                    InteractiveAction(
                        id=f"stock_keep_available:{recovery.spin_id}",
                        title=f"Keep {recovery.available_quantity:g}",
                    )
                ]
                if recovery.available_quantity > 0
                else []
            ),
            InteractiveAction(
                id=f"stock_substitute:{recovery.spin_id}", title="Choose another"
            ),
            InteractiveAction(id=f"stock_remove:{recovery.spin_id}", title="Remove item"),
        ]
        self._remember_choices(task, actions)
        return self._response(message, task.state, task.pending_question, actions=actions)

    async def _select_payment(
        self,
        task: ShoppingTask,
        meaning: MessageUnderstanding,
        message: NormalizedIncomingMessage,
    ) -> NormalizedOutgoingResponse:
        options = await self._available_payment_options(task)
        requested = self._canonical_payment(meaning.selection_value or "")
        selected = next(
            (
                option
                for option in options
                if self._canonical_payment(option.method) == requested
            ),
            None,
        )
        if selected is None:
            return self._payment_options_response(
                task,
                message,
                options,
                lead="That payment method is not currently available for this cart.",
            )

        meaning.selection_value = self._canonical_payment(selected.method)
        try:
            apply_understanding(task, meaning)
        except InvalidTaskTransition:
            return self._payment_options_response(
                task,
                message,
                options,
                lead="Payment can only be selected after your basket is verified.",
            )
        return await self._checkout_confirmation_response(task, message)

    async def _payment_response(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        *,
        lead: str | None = None,
    ) -> NormalizedOutgoingResponse:
        options = await self._available_payment_options(task)
        return self._payment_options_response(task, message, options, lead=lead)

    async def _available_payment_options(
        self, task: ShoppingTask
    ) -> list[PaymentOption]:
        options = await self._commerce.get_payment_options(
            task.provider_cart.cart_id,
            task.selected_address_id,
        )
        return [option for option in options if option.is_available]

    def _payment_options_response(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        options: list[PaymentOption],
        *,
        lead: str | None = None,
    ) -> NormalizedOutgoingResponse:
        if not options:
            text = "No payment method is currently available. Your order was not placed."
            actions: list[InteractiveAction] = []
        else:
            text = " ".join(part for part in (lead, "How would you like to pay?") if part)
            actions = [
                InteractiveAction(
                    id=f"select_payment:{self._canonical_payment(option.method)}",
                    title=option.label[:20],
                    description=option.description,
                )
                for option in options
            ]
        self._remember_choices(task, actions)
        return self._response(message, TaskState.NEEDS_PAYMENT, text, actions=actions)

    async def _checkout_confirmation_response(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        *,
        review_complete: bool = False,
    ) -> NormalizedOutgoingResponse:
        cart = await self._commerce.get_cart(task.provider_cart.cart_id)
        addresses = await self._commerce.get_addresses(task.customer_id)
        address = next(
            (candidate for candidate in addresses if candidate.id == task.selected_address_id),
            None,
        )
        address_text = self._format_address(address)
        payment = self._payment_label(task.selected_payment_method)
        lines = ["Order confirmation", ""]
        lines.extend(
            f"• {item.quantity} × {item.name} ({item.pack_size}) — ₹{item.total_price:g}"
            for item in cart.items
        )
        lines.extend(
            [
                "",
                f"Items: ₹{cart.item_total:g}",
                f"Delivery: ₹{cart.delivery_fee:g}",
                f"Packaging: ₹{cart.packaging_fee:g}",
                f"Discount: ₹{cart.discount:g}",
                f"Total: ₹{cart.grand_total:g}",
                "",
                f"Delivering to: {address_text}",
                f"Payment: {payment}",
            ]
        )
        if review_complete:
            lines.extend(
                [
                    "",
                    "Review complete. No order was placed because Grocer is in review mode.",
                ]
            )
        else:
            lines.extend(["", "Confirm only when you want to place this order."])
        actions = (
            []
            if review_complete
            else [
                InteractiveAction(id="confirm_checkout", title="Confirm order"),
                InteractiveAction(id="change_address", title="Change address"),
                InteractiveAction(id="change_payment", title="Change payment"),
            ]
        )
        if not review_complete and task.selected_address_id and task.selected_payment_method:
            current = task.checkout_confirmation
            if (
                current is None
                or current.cart_id != cart.cart_id
                or current.address_id != task.selected_address_id
                or current.payment_method != task.selected_payment_method
                or current.grand_total != cart.grand_total
            ):
                task.checkout_confirmation = CheckoutConfirmationSnapshot(
                    cart_id=cart.cart_id,
                    address_id=task.selected_address_id,
                    payment_method=task.selected_payment_method,
                    grand_total=cart.grand_total,
                )
                task.version += 1
                task.updated_at = datetime.now(timezone.utc)
        self._remember_choices(task, actions)
        return self._response(
            message,
            TaskState.AWAITING_CHECKOUT_CONFIRMATION,
            "\n".join(lines),
            requires_confirmation=True,
            actions=actions,
        )

    async def _address_response(
        self, task: ShoppingTask, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        addresses = await self._commerce.get_addresses(task.customer_id)
        actions = [
            InteractiveAction(
                id=f"select_address:{address.id}",
                title=self._address_title(address),
                description=address.street or None,
            )
            for address in addresses
        ]
        self._remember_choices(task, actions)
        return self._response(
            message,
            task.state,
            task.pending_question or "Choose a saved delivery address.",
            actions=actions,
        )

    def _resolution_failure(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        resolution: CatalogResolution,
    ) -> NormalizedOutgoingResponse:
        name = resolution.requested_item.name
        if resolution.kind == CatalogResolutionKind.UNAVAILABLE:
            task.state = TaskState.NEEDS_DETAILS
            task.pending_question = (
                f"I could not find an available match for {name}. Nothing was changed "
                "in your Swiggy basket. What would you like instead?"
            )
            task.version += 1
            return self._render(task, message)

        task.state = TaskState.NEEDS_PRODUCT_CHOICE
        task.pending_question = f"Which {name} would you like?"
        return self._product_choices_response(
            task, message, name, list(resolution.candidates), lead=task.pending_question
        )

    def _product_choices_response(
        self,
        task: ShoppingTask,
        message: NormalizedIncomingMessage,
        name: str,
        candidates: list[CatalogCandidate],
        *,
        lead: str,
    ) -> NormalizedOutgoingResponse:
        actions = [
            InteractiveAction(
                id=f"select_product:{name}:{candidate.spin_id}",
                title=candidate.name[:20],
                description=f"{candidate.pack_size} — ₹{candidate.price:g}",
            )
            for candidate in candidates[:3]
        ]
        self._remember_choices(task, actions)
        return self._response(
            message,
            task.state,
            lead,
            actions=actions,
        )

    def _render(
        self, task: ShoppingTask, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        if task.state == TaskState.AWAITING_BASKET_APPROVAL and task.pending_plan:
            lines = ["Please review your basket:", ""]
            lines.extend(
                f"• {item.quantity:g} × {item.name}"
                for item in task.pending_plan.items
            )
            lines.append("\nConfirm this basket, or tell me what to change.")
            actions = [
                InteractiveAction(id="confirm_basket", title="Confirm basket"),
                InteractiveAction(id="cancel", title="Cancel"),
            ]
            self._remember_choices(task, actions)
            return self._response(
                message,
                task.state,
                "\n".join(lines),
                requires_confirmation=True,
                actions=actions,
            )
        if task.state == TaskState.AWAITING_CHECKOUT_CONFIRMATION:
            actions = [
                InteractiveAction(id="confirm_checkout", title="Confirm order"),
                InteractiveAction(id="change_address", title="Change address"),
                InteractiveAction(id="change_payment", title="Change payment"),
            ]
            self._remember_choices(task, actions)
            return self._response(
                message,
                task.state,
                "Your basket, address, and payment method are ready. Confirm only when "
                "you want to place the order.",
                requires_confirmation=True,
                actions=actions,
            )
        return self._response(
            message,
            task.state,
            task.pending_question or self._default_text(task.state),
        )

    def _cart_adoption_response(
        self, task: ShoppingTask, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        actions = [
            InteractiveAction(id="keep_cart", title="Keep"),
            InteractiveAction(id="start_fresh", title="Start fresh"),
            InteractiveAction(id="cancel", title="Cancel"),
        ]
        self._remember_choices(task, actions)
        return self._response(
            message,
            TaskState.NEEDS_CART_ADOPTION,
            task.pending_question
            or "I found items already in your Swiggy basket. What should I do?",
            actions=actions,
        )

    @staticmethod
    def _proposal(
        operation: TaskOperation,
        *,
        selection_value: str | None = None,
        source: Literal["rules", "interactive"] = "rules",
    ) -> MessageUnderstanding:
        return MessageUnderstanding(
            operation=operation,
            selection_value=selection_value,
            confidence=1,
            source=source,
        )

    @staticmethod
    def _updates_for(resolutions: list[CatalogResolution]) -> list[CartItemUpdate]:
        updates: list[CartItemUpdate] = []
        for resolution in resolutions:
            assert resolution.selected is not None
            quantity = resolution.requested_item.quantity
            updates.append(
                CartItemUpdate(
                    spin_id=resolution.selected.spin_id,
                    sku_id=resolution.selected.sku_id,
                    quantity=max(1, math.ceil(quantity)),
                )
            )
        return updates

    @staticmethod
    def _merge_existing_updates(
        cart: CommerceCart, planned: list[CartItemUpdate]
    ) -> list[CartItemUpdate]:
        merged = {
            item.spin_id: CartItemUpdate(
                spin_id=item.spin_id,
                sku_id=item.sku_id,
                quantity=item.quantity,
            )
            for item in cart.items
        }
        for update in planned:
            merged[update.spin_id] = update
        return list(merged.values())

    @staticmethod
    def _cart_matches(expected: list[CartItemUpdate], actual: CommerceCart) -> bool:
        actual_quantities = {item.spin_id: item.quantity for item in actual.items}
        return all(
            actual_quantities.get(item.spin_id) == item.quantity
            for item in expected
            if item.quantity > 0
        )

    @staticmethod
    def _address_title(address: DeliveryAddress) -> str:
        return (address.label or address.address_tag or "Saved address")[:20]

    @staticmethod
    def _default_text(state: TaskState) -> str:
        if state == TaskState.CANCELLED:
            return "This grocery task is cancelled. No order was placed."
        if state == TaskState.NEEDS_PAYMENT:
            return "How would you like to pay?"
        return "Tell me what groceries you need."

    @staticmethod
    def _canonical_payment(value: str) -> str:
        normalized = " ".join(value.casefold().replace("_", " ").split())
        if normalized in {"cod", "cash", "cash on delivery"}:
            return "cod"
        if "upi" in normalized:
            return "upi"
        return normalized

    @staticmethod
    def _payment_label(value: str | None) -> str:
        if value == "cod":
            return "Cash on delivery"
        if value == "upi":
            return "UPI"
        return value or "Not selected"

    @staticmethod
    def _format_address(address: DeliveryAddress | None) -> str:
        if address is None:
            return "Saved address unavailable"
        parts = [address.label, address.street, address.city, address.postal_code]
        return ", ".join(part for part in parts if part)

    @staticmethod
    def _response(
        message: NormalizedIncomingMessage,
        state: TaskState,
        text: str,
        *,
        requires_confirmation: bool = False,
        actions: list[InteractiveAction] | None = None,
    ) -> NormalizedOutgoingResponse:
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=text,
            conversation_state=state.value,
            requires_confirmation=requires_confirmation,
            interactive_actions=actions or [],
        )
