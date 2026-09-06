"""BaseChannelAdapter — transport-agnostic channel boundary (Spec §17, Phase C)."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Optional

from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult
from backend.intent.session import ConversationState, default_session_store


class BaseChannelAdapter(ABC):
    """Abstract adapter decoupling transport protocols from GrocerOrchestrator."""

    def __init__(self, channel_type: ChannelType) -> None:
        self.channel_type = channel_type
        # Maps customer_id -> active session_id for session continuity across messages
        self._active_sessions: dict[str, str] = {}

    def map_sender_to_customer_id(self, sender_id: str) -> str:
        """Map raw transport sender ID to stable GROCER customer identity."""
        cleaned = re.sub(r"[^\w+]", "", sender_id)
        if self.channel_type == ChannelType.WHATSAPP:
            cleaned_num = cleaned.replace("+", "")
            return f"cust_wa_{cleaned_num}"
        return f"cust_{cleaned}"

    def get_or_create_session_id(self, customer_id: str) -> str:
        """Get or create stable conversational session ID for customer."""
        session_id = self._active_sessions.get(customer_id)
        if session_id:
            existing = default_session_store.get(session_id)
            # If session exists and was ordered/failed, create new session for fresh shopping task
            if existing and existing.conversation_state in (ConversationState.ORDERED, ConversationState.FAILED):
                session_id = None

        if not session_id:
            session_id = f"sess_{customer_id}_{int(default_session_store.get_or_create('', customer_id).turn_count + 1)}"
            self._active_sessions[customer_id] = session_id

        return session_id

    def reset_session(self, customer_id: str) -> None:
        """Reset active session for a customer."""
        self._active_sessions.pop(customer_id, None)

    async def dispatch(
        self,
        incoming: NormalizedIncomingMessage,
        orchestrator: GrocerOrchestrator,
    ) -> NormalizedOutgoingResponse:
        """Route incoming normalized message to GrocerOrchestrator and format response."""
        customer_id = self.map_sender_to_customer_id(incoming.sender_id)
        session_id = self.get_or_create_session_id(customer_id)
        session = default_session_store.get(session_id)

        clean_text = incoming.text.strip().lower()
        interactive_id = incoming.interactive_id

        turn_result: OrchestratorTurnResult

        # 1. Check for explicit checkout confirmation
        is_confirm_action = interactive_id == "confirm_checkout"
        is_confirm_text = clean_text in ("yes", "confirm", "proceed", "yes checkout", "confirm checkout", "place order", "ok checkout")

        if (is_confirm_action or is_confirm_text) and session and session.conversation_state == ConversationState.AWAITING_CONFIRMATION:
            turn_result = await orchestrator.handle_confirm(
                session_id=session_id,
                payment_method="UPI",
                address_id=session.address_id,
            )
            if turn_result.conversation_state == ConversationState.ORDERED:
                self.reset_session(customer_id)

        # 2. Check for clarification choice
        elif session and session.conversation_state == ConversationState.NEEDS_DECISION and session.pending_clarification:
            chosen_spin_id: Optional[str] = None
            pending = session.pending_clarification

            if interactive_id:
                if interactive_id.startswith("choice:"):
                    chosen_spin_id = interactive_id.replace("choice:", "")
                elif any(c.spin_id == interactive_id for c in pending.candidates):
                    chosen_spin_id = interactive_id

            if not chosen_spin_id:
                # Check if user texted an option number (e.g. "1", "2")
                if clean_text.isdigit():
                    idx = int(clean_text) - 1
                    if 0 <= idx < len(pending.candidates):
                        chosen_spin_id = pending.candidates[idx].spin_id

                # Check if user texted a candidate product name or spin ID
                if not chosen_spin_id:
                    for c in pending.candidates:
                        if clean_text in c.name.lower() or c.name.lower() in clean_text or clean_text == c.spin_id.lower():
                            chosen_spin_id = c.spin_id
                            break

            if chosen_spin_id:
                turn_result = await orchestrator.handle_choice(
                    session_id=session_id,
                    chosen_spin_id=chosen_spin_id,
                )
            else:
                turn_result = await orchestrator.handle_turn(
                    session_id=session_id,
                    customer_id=customer_id,
                    message=incoming.text,
                    address_id=session.address_id,
                )

        # 3. Standard conversational turn
        else:
            turn_result = await orchestrator.handle_turn(
                session_id=session_id,
                customer_id=customer_id,
                message=incoming.text,
                address_id=session.address_id if session else None,
            )

        # Build normalized outgoing response
        response = self._build_normalized_response(incoming.sender_id, turn_result)
        await self.send_response(response)
        return response

    def _build_normalized_response(
        self,
        recipient_id: str,
        result: OrchestratorTurnResult,
    ) -> NormalizedOutgoingResponse:
        """Map OrchestratorTurnResult to NormalizedOutgoingResponse with appropriate interactive actions."""
        actions: list[InteractiveAction] = []
        interactive_title = None
        interactive_button_text = None

        if result.conversation_state == ConversationState.NEEDS_DECISION and result.clarification_options:
            interactive_title = "Alternative Options"
            interactive_button_text = "Select Alternative"
            for opt in result.clarification_options:
                actions.append(
                    InteractiveAction(
                        action_type="list_item",
                        id=f"choice:{opt.spin_id}",
                        title=f"{opt.index}. {opt.name}"[:24],
                        description=f"₹{opt.price:,.0f} ({opt.pack_size})"[:72],
                    )
                )

        elif result.conversation_state == ConversationState.AWAITING_CONFIRMATION:
            interactive_title = "Confirm Order"
            actions.append(
                InteractiveAction(
                    action_type="button",
                    id="confirm_checkout",
                    title="Confirm Order",
                )
            )
            actions.append(
                InteractiveAction(
                    action_type="button",
                    id="cancel_order",
                    title="Change Items",
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
        """Deliver normalized response to transport layer."""
        raise NotImplementedError
