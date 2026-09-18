"""Transport-neutral channel adapter for GROCER conversations."""
from __future__ import annotations

import re
import secrets
from abc import ABC, abstractmethod
from typing import Optional

from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.identity import whatsapp_customer_id
from backend.intent.conversation import (
    ConversationCommand,
    ConversationController,
    ConversationInterpreter,
)
from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult
from backend.intent.session import ConversationState, OrchestratorSession, default_session_store
from backend.intent.stages.address_stage import default_address_manager


class BaseChannelAdapter(ABC):
    """Map transport input into the one canonical GROCER workflow."""

    def __init__(self, channel_type: ChannelType) -> None:
        self.channel_type = channel_type
        self._active_sessions: dict[str, str] = {}
        self._conversation_interpreter = ConversationInterpreter()
        self._conversation_controller = ConversationController()

    def map_sender_to_customer_id(self, sender_id: str) -> str:
        """Map a transport sender to its stable, pseudonymous customer identity."""
        cleaned = re.sub(r"[^\w+]", "", sender_id)
        if self.channel_type == ChannelType.WHATSAPP:
            return whatsapp_customer_id(
                sender_id,
                getattr(self, "app_secret", None) or settings.WHATSAPP_APP_SECRET,
            )
        return f"cust_{cleaned}"

    def get_or_create_session_id(self, customer_id: str) -> str:
        """Return the active shopping session or create a new one."""
        session_id = self._active_sessions.get(customer_id)
        if session_id:
            existing = default_session_store.get(session_id)
            if existing and existing.conversation_state in {
                ConversationState.ORDERED,
                ConversationState.FAILED,
            }:
                session_id = None

        if session_id is None:
            session_id = f"sess_{secrets.token_urlsafe(24)}"
            self._active_sessions[customer_id] = session_id
            saved_address = default_address_manager.get_saved_address(customer_id)
            if saved_address:
                session = default_session_store.get_or_create(session_id, customer_id)
                session.address_id = saved_address
                default_session_store.save(session)
        return session_id

    def reset_session(self, customer_id: str) -> None:
        """Forget the active session mapping after a completed shopping task."""
        self._active_sessions.pop(customer_id, None)

    def pending_delivery(
        self, message_id: str
    ) -> Optional[NormalizedOutgoingResponse]:
        """Return a staged response for retry-aware transports, if any."""
        del message_id
        return None

    def stage_delivery(
        self, message_id: str, response: NormalizedOutgoingResponse
    ) -> None:
        """Stage an outcome before attempting outbound delivery."""
        del message_id, response

    async def dispatch(
        self,
        incoming: NormalizedIncomingMessage,
        orchestrator: GrocerOrchestrator,
    ) -> NormalizedOutgoingResponse:
        """Interpret one input and delegate it to the canonical orchestrator."""
        customer_id = self.map_sender_to_customer_id(incoming.sender_id)
        session_id, session, command = await self._resolve_conversation(
            incoming, customer_id
        )
        result = await self._conversation_controller.handle(
            command=command,
            message=incoming.text,
            session_id=session_id,
            customer_id=customer_id,
            session=session,
            orchestrator=orchestrator,
        )
        response = self._build_normalized_response(incoming.sender_id, result)
        self.stage_delivery(incoming.message_id, response)
        if not await self.send_response(response):
            raise RuntimeError("Channel response delivery failed.")
        return response

    async def _resolve_conversation(
        self,
        incoming: NormalizedIncomingMessage,
        customer_id: str,
    ) -> tuple[str, OrchestratorSession | None, ConversationCommand]:
        """Keep completed-order tracking on its session, otherwise begin a new task."""
        prior_session_id = self._active_sessions.get(customer_id)
        prior_session = (
            default_session_store.get(prior_session_id) if prior_session_id else None
        )
        if prior_session and prior_session.conversation_state == ConversationState.ORDERED:
            prior_command = await self._conversation_interpreter.interpret(
                message=incoming.text,
                interactive_id=incoming.interactive_id,
                session=prior_session,
            )
            if prior_command.action.value in {"TRACK_ORDER", "ORDER_DETAILS"}:
                return prior_session_id, prior_session, prior_command
            self.reset_session(customer_id)

        session_id = self.get_or_create_session_id(customer_id)
        session = default_session_store.get(session_id)
        command = await self._conversation_interpreter.interpret(
            message=incoming.text,
            interactive_id=incoming.interactive_id,
            session=session,
        )
        return session_id, session, command

    def _build_normalized_response(
        self,
        recipient_id: str,
        result: OrchestratorTurnResult,
    ) -> NormalizedOutgoingResponse:
        """Render canonical orchestration state as native WhatsApp actions."""
        actions: list[InteractiveAction] = []
        interactive_title = None
        interactive_button_text = None

        if result.conversation_state == ConversationState.NEEDS_DECISION and result.payment_options:
            interactive_title = "Payment Options"
            interactive_button_text = "Choose Payment"
            for index, option in enumerate(result.payment_options, 1):
                option_id = option.id or option.method
                actions.append(
                    InteractiveAction(
                        action_type="list_item",
                        id=f"payment:{result.payment_choice_nonce or 'invalid'}:{option_id}",
                        title=f"{index}. {option.label}"[:24],
                        description=option.method[:72],
                    )
                )
        elif result.conversation_state == ConversationState.NEEDS_DECISION and result.address_options:
            interactive_title = "Delivery Address"
            interactive_button_text = "Choose Address"
            for index, address in enumerate(result.address_options, 1):
                actions.append(
                    InteractiveAction(
                        action_type="list_item",
                        id=f"address:{address.id}",
                        title=f"{index}. {address.label}"[:24],
                        description=(address.street or address.city or "Saved Address")[:72],
                    )
                )
        elif result.conversation_state == ConversationState.NEEDS_DECISION and result.clarification_options:
            interactive_title = "Alternative Options"
            interactive_button_text = "Select Alternative"
            for option in result.clarification_options:
                actions.append(
                    InteractiveAction(
                        action_type="list_item",
                        id=f"choice:{result.clarification_nonce or 'invalid'}:{option.spin_id}",
                        title=f"{option.index}. {option.name}"[:24],
                        description=f"₹{option.price:,.0f} ({option.pack_size})"[:72],
                    )
                )
        elif result.conversation_state == ConversationState.AWAITING_CONFIRMATION:
            interactive_title = "Confirm Order"
            actions.extend(
                [
                    InteractiveAction(
                        action_type="button",
                        id=(
                            f"confirm_checkout:{result.basket_summary.confirmation_nonce}"
                            if result.basket_summary
                            else "confirm_checkout:invalid"
                        ),
                        title="Confirm Order",
                    ),
                    InteractiveAction(
                        action_type="button", id="cancel_order", title="Change Items"
                    ),
                ]
            )
        elif result.conversation_state == ConversationState.PAYMENT_PENDING:
            interactive_title = "Payment Pending"
            actions.append(
                InteractiveAction(
                    action_type="button", id="check_payment_status", title="Check Payment"
                )
            )

        return NormalizedOutgoingResponse(
            recipient_id=recipient_id,
            channel=self.channel_type,
            text=result.user_message,
            conversation_state=result.conversation_state.value,
            requires_confirmation=result.requires_confirmation,
            interactive_actions=actions,
            interactive_title=interactive_title,
            interactive_button_text=interactive_button_text,
            order_id=result.order_id,
            order_total=result.order_total,
            events=result.events,
        )

    @abstractmethod
    async def send_response(self, response: NormalizedOutgoingResponse) -> bool:
        """Deliver normalized response to the transport."""
        raise NotImplementedError
