"""Context-aware message interpretation and safe conversation command routing.

The interpreter may use an LLM to understand free text. The controller is the
authority: it validates every command against the active session and delegates
only to ``GrocerOrchestrator`` entry points.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel, Field

from backend.config import settings
from backend.intent.session import ConversationState, OrchestratorSession

if TYPE_CHECKING:
    from backend.intent.orchestrator import GrocerOrchestrator, OrchestratorTurnResult


logger = logging.getLogger(__name__)


class ConversationAction(StrEnum):
    BASKET_REQUEST = "BASKET_REQUEST"
    SELECT_ADDRESS = "SELECT_ADDRESS"
    SELECT_PRODUCT_OPTION = "SELECT_PRODUCT_OPTION"
    SELECT_PAYMENT = "SELECT_PAYMENT"
    CONFIRM_CHECKOUT = "CONFIRM_CHECKOUT"
    CHANGE_OR_CANCEL = "CHANGE_OR_CANCEL"
    CHECK_PAYMENT_STATUS = "CHECK_PAYMENT_STATUS"
    TRACK_ORDER = "TRACK_ORDER"
    ORDER_DETAILS = "ORDER_DETAILS"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"


class ConversationCommand(BaseModel):
    """One bounded meaning extracted from an inbound customer message."""

    action: ConversationAction
    choice_index: int | None = Field(default=None, ge=1)
    selection_id: str | None = None
    nonce: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ConversationInterpreter:
    """Translate free text into a validated, non-authoritative command."""

    _MIN_CONFIDENCE = 0.7

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-3.5-flash-lite:generateContent?key={self._api_key}"
            if self._api_key
            else None
        )

    async def interpret(
        self,
        *,
        message: str,
        interactive_id: str | None,
        session: OrchestratorSession | None,
    ) -> ConversationCommand:
        """Return a command; ambiguous or unavailable-model inputs stay safe."""
        interactive_command = self._command_from_interactive_id(interactive_id)
        if interactive_command is not None:
            return interactive_command

        fallback = self._safe_fallback(message, session)
        if not self._url or "PYTEST_CURRENT_TEST" in os.environ:
            return fallback

        model_command = await asyncio.to_thread(
            self._interpret_with_model,
            message,
            self._context_for(session),
        )
        if model_command is None or model_command.confidence < self._MIN_CONFIDENCE:
            return fallback
        return model_command

    def _command_from_interactive_id(
        self, interactive_id: str | None
    ) -> ConversationCommand | None:
        if not interactive_id:
            return None
        if interactive_id.startswith("confirm_checkout:"):
            return ConversationCommand(
                action=ConversationAction.CONFIRM_CHECKOUT,
                selection_id=interactive_id.split(":", 1)[1],
                confidence=1,
            )
        if interactive_id == "cancel_order":
            return ConversationCommand(
                action=ConversationAction.CHANGE_OR_CANCEL,
                selection_id=interactive_id,
                confidence=1,
            )
        if interactive_id == "check_payment_status":
            return ConversationCommand(action=ConversationAction.CHECK_PAYMENT_STATUS, confidence=1)
        if interactive_id.startswith("address:"):
            return ConversationCommand(
                action=ConversationAction.SELECT_ADDRESS,
                selection_id=interactive_id.split(":", 1)[1],
                confidence=1,
            )
        if interactive_id.startswith("payment:"):
            parts = interactive_id.split(":", 2)
            return ConversationCommand(
                action=ConversationAction.SELECT_PAYMENT,
                selection_id=parts[2] if len(parts) == 3 else None,
                nonce=parts[1] if len(parts) == 3 else None,
                confidence=1,
            )
        if interactive_id.startswith("choice:"):
            parts = interactive_id.split(":", 2)
            return ConversationCommand(
                action=ConversationAction.SELECT_PRODUCT_OPTION,
                selection_id=parts[2] if len(parts) == 3 else None,
                nonce=parts[1] if len(parts) == 3 else None,
                confidence=1,
            )
        return None

    def _safe_fallback(
        self, message: str, session: OrchestratorSession | None
    ) -> ConversationCommand:
        """Never infer a consequential text command without model confidence."""
        choice_index = int(message.strip()) if message.strip().isdigit() else None
        if choice_index is not None and session is not None:
            if session.pending_address_choice:
                action = ConversationAction.SELECT_ADDRESS
            elif session.pending_payment_choice:
                action = ConversationAction.SELECT_PAYMENT
            elif session.pending_clarification:
                action = ConversationAction.SELECT_PRODUCT_OPTION
            else:
                action = ConversationAction.BASKET_REQUEST
            return ConversationCommand(action=action, choice_index=choice_index, confidence=1)
        return ConversationCommand(action=ConversationAction.BASKET_REQUEST, confidence=0)

    def _interpret_with_model(
        self, message: str, context: dict[str, Any]
    ) -> ConversationCommand | None:
        assert self._url is not None
        prompt = (
            "You classify one GROCER WhatsApp message in its current conversation state. "
            "Return JSON only: {action, choice_index, confidence}. "
            "Allowed actions: BASKET_REQUEST, SELECT_ADDRESS, SELECT_PRODUCT_OPTION, "
            "SELECT_PAYMENT, CONFIRM_CHECKOUT, CHANGE_OR_CANCEL, CHECK_PAYMENT_STATUS, "
            "TRACK_ORDER, ORDER_DETAILS, ASK_CLARIFICATION. "
            "Use SELECT_* only for an offered option and provide its 1-based choice_index. "
            "CONFIRM_CHECKOUT only means an unambiguous request to place the already shown order. "
            "A request to add, remove, change, wait, or ask a question is never confirmation. "
            "Do not invent IDs or provider facts. If uncertain, use ASK_CLARIFICATION.\n\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}\n"
            f"User message: {json.dumps(message, ensure_ascii=False)}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(self._url, json=payload)
            if response.status_code != 200:
                logger.warning("Conversation interpretation returned status %d", response.status_code)
                return None
            parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            if not parts or not parts[0].get("text"):
                return None
            return ConversationCommand.model_validate_json(parts[0]["text"])
        except (httpx.HTTPError, IndexError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Conversation interpretation failed: %s", type(exc).__name__)
            return None

    def _context_for(self, session: OrchestratorSession | None) -> dict[str, Any]:
        if session is None:
            return {"state": ConversationState.READY.value, "options": []}
        options: list[str] = []
        if session.pending_address_choice:
            options = [
                " | ".join(
                    part
                    for part in (address.label, address.street, address.city)
                    if part
                )
                or address.id
                for address in session.pending_address_choice.addresses
            ]
        elif session.pending_payment_choice:
            options = [option.label for option in session.pending_payment_choice.options]
        elif session.pending_clarification:
            options = [candidate.name for candidate in session.pending_clarification.candidates]
        return {"state": session.conversation_state.value, "options": options}


class ConversationController:
    """Validate commands against session state and call canonical orchestration."""

    async def handle(
        self,
        *,
        command: ConversationCommand,
        message: str,
        session_id: str,
        customer_id: str,
        session: OrchestratorSession | None,
        orchestrator: GrocerOrchestrator,
    ) -> OrchestratorTurnResult:
        if command.action == ConversationAction.CONFIRM_CHECKOUT:
            return await self._confirm(command, session_id, session, orchestrator, message, customer_id)
        if command.action == ConversationAction.SELECT_ADDRESS:
            return await self._select_address(command, session_id, session, orchestrator, message, customer_id)
        if command.action == ConversationAction.SELECT_PAYMENT:
            return await self._select_payment(command, session_id, session, orchestrator, message, customer_id)
        if command.action == ConversationAction.SELECT_PRODUCT_OPTION:
            return await self._select_product(command, session_id, session, orchestrator, message, customer_id)
        if command.action == ConversationAction.CHANGE_OR_CANCEL and command.selection_id == "cancel_order" and session is not None:
            return await orchestrator.handle_change_request(session_id)
        if command.action == ConversationAction.CHECK_PAYMENT_STATUS and session is not None:
            return await orchestrator.handle_payment_status(session_id)
        if command.action == ConversationAction.TRACK_ORDER and session is not None:
            return await orchestrator.handle_delivery_status(session_id)
        if command.action == ConversationAction.ORDER_DETAILS and session is not None:
            return await orchestrator.handle_order_details(session_id)
        if command.action == ConversationAction.ASK_CLARIFICATION:
            return self._clarification_result(session_id, session)
        return await orchestrator.handle_turn(
            session_id=session_id,
            customer_id=customer_id,
            message=message,
            address_id=session.address_id if session else None,
        )

    async def _confirm(
        self, command: ConversationCommand, session_id: str, session: OrchestratorSession | None,
        orchestrator: GrocerOrchestrator, message: str, customer_id: str,
    ) -> OrchestratorTurnResult:
        if session is None or session.conversation_state != ConversationState.AWAITING_CONFIRMATION:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        pending = session.pending_confirmation
        return await orchestrator.handle_confirm(
            session_id=session_id,
            payment_method=pending.payment_method if pending else "",
            address_id=session.address_id,
            explicit_confirmation=True,
            confirmation_nonce=command.selection_id or (pending.nonce if pending else None),
        )

    async def _select_address(
        self, command: ConversationCommand, session_id: str, session: OrchestratorSession | None,
        orchestrator: GrocerOrchestrator, message: str, customer_id: str,
    ) -> OrchestratorTurnResult:
        if session is None or session.pending_address_choice is None:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        addresses = session.pending_address_choice.addresses
        selected = next((address for address in addresses if address.id == command.selection_id), None)
        if selected is None and command.choice_index is not None and command.choice_index <= len(addresses):
            selected = addresses[command.choice_index - 1]
        if selected is None:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        return await orchestrator.handle_address_choice(session_id, selected.id)

    async def _select_payment(
        self, command: ConversationCommand, session_id: str, session: OrchestratorSession | None,
        orchestrator: GrocerOrchestrator, message: str, customer_id: str,
    ) -> OrchestratorTurnResult:
        if session is None or session.pending_payment_choice is None:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        if command.nonce is not None and command.nonce != session.pending_payment_choice.nonce:
            return self._clarification_result(session_id, session)
        options = session.pending_payment_choice.options
        option = next(
            (current for current in options if command.selection_id in {current.id, current.method}),
            None,
        )
        if option is None and command.choice_index is not None and command.choice_index <= len(options):
            option = options[command.choice_index - 1]
        if option is None:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        return await orchestrator.handle_payment_choice(
            session_id, option.id or option.method, session.pending_payment_choice.nonce
        )

    async def _select_product(
        self, command: ConversationCommand, session_id: str, session: OrchestratorSession | None,
        orchestrator: GrocerOrchestrator, message: str, customer_id: str,
    ) -> OrchestratorTurnResult:
        if session is None or session.pending_clarification is None:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        if command.nonce is not None and command.nonce != session.pending_clarification.nonce:
            return self._clarification_result(session_id, session)
        candidates = session.pending_clarification.candidates
        candidate = next(
            (current for current in candidates if current.spin_id == command.selection_id),
            None,
        )
        if candidate is None and command.choice_index is not None and command.choice_index <= len(candidates):
            candidate = candidates[command.choice_index - 1]
        if candidate is None:
            return await self._as_basket_request(session_id, session, orchestrator, message, customer_id)
        return await orchestrator.handle_choice(
            session_id=session_id,
            chosen_spin_id=candidate.spin_id,
            clarification_nonce=session.pending_clarification.nonce,
        )

    async def _as_basket_request(
        self, session_id: str, session: OrchestratorSession | None,
        orchestrator: GrocerOrchestrator, message: str, customer_id: str,
    ) -> OrchestratorTurnResult:
        return await orchestrator.handle_turn(
            session_id=session_id,
            customer_id=customer_id,
            message=message,
            address_id=session.address_id if session else None,
        )

    def _clarification_result(
        self, session_id: str, session: OrchestratorSession | None
    ) -> OrchestratorTurnResult:
        from backend.intent.orchestrator import OrchestratorTurnResult

        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=(session.conversation_state if session else ConversationState.READY),
            user_message="I want to get that right. Could you say which option or change you mean?",
            events=["CONVERSATION_CLARIFICATION_REQUESTED"],
        )
