"""Autonomous ReAct agent engine for Swiggy Instamart grocery ordering powered by Google Gemini."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.agent.schemas import RAW_TOOL_DECLARATIONS
from backend.agent.tools import SwiggyAgentTools
from backend.agent.gemini import GeminiClient
from backend.agent.budget import read_budget_cap
from backend.agent.formatters import (
    build_address_choice_response,
    build_auth_expired_response,
    build_connect_url,
)
from backend.agent.session_manager import (
    dump_task_state_dict,
    prune_history_entries,
    record_pending_approval,
    restore_task_state_dict,
)
from backend.agent.preflight_handler import execute_preflight
from backend.agent.react_coordinator import execute_react_turn_loop
from backend.agent.response_synthesizer import synthesize_turn_response
from backend.agent.tool_executor import execute_engine_tool
from backend.channels.models import (
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart
from backend.integrations.commerce.port import CommercePort
from backend.agent.prompts import (
    build_system_instruction,
    _SHOPPING_PLAN_PROMPT,
)

logger = logging.getLogger("grocer.agent.engine")


class _SessionDictView(dict):
    """Transparent dictionary view backed purely by CustomerSession with zero duplicate state."""

    def __init__(self, engine: Any, attr_name: str, default: Any = None):
        super().__init__()
        self._engine = engine
        self._attr = attr_name
        self._default = default

    def get(self, key: str, default: Any = None):
        sess = self._engine._sessions.get(key)
        if sess is not None:
            val = getattr(sess, self._attr, None)
            if val is not None:
                return val
        return default if default is not None else self._default

    def __getitem__(self, key: str):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: Any):
        sess = self._engine.get_session(key)
        setattr(sess, self._attr, value)

    def pop(self, key: str, default: Any = None):
        sess = self._engine._sessions.get(key)
        if sess is not None:
            old = getattr(sess, self._attr, None)
            setattr(sess, self._attr, None if not isinstance(self._default, bool) else False)
            return old if old is not None else default
        return default

    def clear(self):
        for sess in self._engine._sessions.values():
            setattr(sess, self._attr, None if not isinstance(self._default, bool) else False)

    def __contains__(self, key: object):
        if not isinstance(key, str):
            return False
        sess = self._engine._sessions.get(key)
        if sess is not None:
            val = getattr(sess, self._attr, None)
            return val is not None and (val is not False if isinstance(self._default, bool) else True)
        return False

    def keys(self):
        return [k for k, s in self._engine._sessions.items() if getattr(s, self._attr, None) is not None]

    def values(self):
        return [getattr(s, self._attr) for s in self._engine._sessions.values() if getattr(s, self._attr, None) is not None]

    def items(self):
        return [(k, getattr(s, self._attr)) for k, s in self._engine._sessions.items() if getattr(s, self._attr, None) is not None]


class GroceryAgentEngine:
    """Conversational ReAct agent driving Swiggy Instamart through Google Gemini function calling."""

    def __init__(
        self,
        commerce: CommercePort,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        gemini_fallback_model: Optional[str] = None,
        timeout: float = 25.0,
        attempt_store: Any | None = None,
        state_store: Any | None = None,
        **_kwargs: Any,
    ) -> None:
        self.commerce = commerce
        self.tools = SwiggyAgentTools(commerce)
        self.attempt_store = attempt_store
        self.state_store = state_store
        self.gemini_api_key = gemini_api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.gemini_model = gemini_model or getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")
        self.gemini_fallback_model = gemini_fallback_model or getattr(settings, "GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")
        self.timeout = timeout
        # Single authoritative CustomerSession map with synchronized views
        self._sessions: dict[str, Any] = {}
        self._customer_address = _SessionDictView(self, "address_id")
        self._customer_address_label = _SessionDictView(self, "address_label")
        self._order_address_confirmed = _SessionDictView(self, "order_address_confirmed", default=False)
        self._awaiting_address_choice = _SessionDictView(self, "awaiting_address_choice")
        self._history = _SessionDictView(self, "history", default=[])
        self._pending_checkout: dict[str, bool] = {}
        self._last_interaction_time: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_call_time: float = 0.0
        self.last_llm_error: Optional[str] = None
        self.last_turn_latency_ms: Optional[float] = None
        self.gemini = GeminiClient(
            api_key=self.gemini_api_key or "",
            primary_model=self.gemini_model,
            fallback_model=self.gemini_fallback_model,
            timeout=self.timeout,
        )

    def get_session(self, customer_id: str) -> Any:
        """Return the atomic CustomerSession for customer_id, synchronized with engine state."""
        from backend.agent.session import CustomerSession
        sess = self._sessions.get(customer_id)
        if sess is None:
            sess = CustomerSession(customer_id=customer_id)
            self._sessions[customer_id] = sess
        sess.history = self.get_history(customer_id)
        sess.address_id = self._customer_address.get(customer_id)
        sess.address_label = self._customer_address_label.get(customer_id)
        sess.order_address_confirmed = bool(self._order_address_confirmed.get(customer_id, False))
        sess.awaiting_address_choice = self._awaiting_address_choice.get(customer_id)
        sess.last_active_ts = self._last_interaction_time.get(customer_id, 0.0)
        return sess

    async def forget_customer(self, customer_id: str) -> None:
        """Drop local mirrors after a verified deletion request."""
        for mapping in (
            self._sessions, self._history, self._customer_address,
            self._customer_address_label, self._order_address_confirmed,
            self._awaiting_address_choice, self._pending_checkout,
            self._last_interaction_time,
        ):
            mapping.pop(customer_id, None)

    def _restore_task_state(self, customer_id: str, state: dict[str, Any] | None) -> None:
        session, history = restore_task_state_dict(
            customer_id=customer_id,
            state=state,
            customer_address=self._customer_address,
            customer_address_label=self._customer_address_label,
            order_address_confirmed=self._order_address_confirmed,
            awaiting_address_choice=self._awaiting_address_choice,
            last_interaction_time=self._last_interaction_time,
        )
        self._sessions[customer_id] = session
        self._history[customer_id] = history

    def _task_state_snapshot(self, customer_id: str) -> dict[str, Any]:
        return dump_task_state_dict(
            session=self.get_session(customer_id),
            history=self.get_history(customer_id),
            address_id=self._customer_address.get(customer_id),
            address_label=self._customer_address_label.get(customer_id),
            order_address_confirmed=self._order_address_confirmed.get(customer_id, False),
            awaiting_address_choice=self._awaiting_address_choice.get(customer_id),
            last_active_ts=self._last_interaction_time.get(customer_id),
        )

    def _address_choice_response(
        self, message: NormalizedIncomingMessage, addresses: list[dict[str, Any]]
    ) -> NormalizedOutgoingResponse:
        return build_address_choice_response(message, addresses)

    def reset_customer_order_address(self, customer_id: str) -> None:
        """Atomically clear order address lock across session and state dictionaries."""
        self._order_address_confirmed.pop(customer_id, None)
        self._customer_address.pop(customer_id, None)
        self._customer_address_label.pop(customer_id, None)
        self._awaiting_address_choice.pop(customer_id, None)
        if customer_id in self._sessions:
            self._sessions[customer_id].reset_order_address()
            self._sessions[customer_id].pending_approval = None

    def _record_pending_approval(
        self, customer_id: str, cart: CommerceCart, address_id: str
    ) -> bool:
        return record_pending_approval(self.get_session(customer_id), cart, address_id)

    async def close(self) -> None:
        """Close Gemini client session on shutdown."""
        if hasattr(self, "gemini") and self.gemini:
            await self.gemini.close()

    def _connect_url(self, ticket: str) -> str:
        return build_connect_url(ticket)

    async def _auth_expired_response(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        return await build_auth_expired_response(message)

    def get_history(self, customer_id: str) -> list[dict[str, Any]]:
        if customer_id not in self._history:
            self._history[customer_id] = []
        return self._history[customer_id]

    def _prune_history(self, customer_id: str, max_user_turns: int = 20) -> None:
        """Keep conversation history bounded by whole user turn boundaries and compact past search returns."""
        self._history[customer_id] = prune_history_entries(
            self._history.get(customer_id, []),
            has_state_store=self.state_store is not None,
            max_user_turns=max_user_turns,
        )

    async def handle_message(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        """Process one WhatsApp turn through the autonomous Gemini 3.5 Flash-Lite ReAct agent engine with per-customer serialization."""
        incoming_text = (message.text or "").strip()
        if incoming_text == "UNSUPPORTED_MEDIA":
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=(
                    "I can only read text messages right now! Please type your grocery items as text "
                    "so I can check dark store stock and add them to your cart. 🛒"
                ),
                conversation_state="READY",
            )

        start_time = asyncio.get_running_loop().time()
        customer_id = message.customer_id or message.sender_id
        lock = self._locks.setdefault(customer_id, asyncio.Lock())
        async with lock:
            if self.state_store is not None and getattr(self.state_store, "pool", None) is not None:
                async with self.state_store.transaction_lock(customer_id) as conn:
                    state_data = await self.state_store.load(customer_id, conn=conn)
                    self._restore_task_state(customer_id, state_data)
                    self._prune_history(customer_id)
                    with self.commerce.customer_scope(customer_id):
                        try:
                            result = await self._process_scoped_message(message, customer_id)
                        finally:
                            self._prune_history(customer_id)
                            await self.state_store.save(customer_id, self._task_state_snapshot(customer_id), conn=conn)
            else:
                if self.state_store is not None:
                    self._restore_task_state(customer_id, await self.state_store.load(customer_id))
                    self._prune_history(customer_id)
                with self.commerce.customer_scope(customer_id):
                    try:
                        result = await self._process_scoped_message(message, customer_id)
                    finally:
                        if self.state_store is not None:
                            self._prune_history(customer_id)
                            await self.state_store.save(customer_id, self._task_state_snapshot(customer_id))

            self.last_turn_latency_ms = round(
                (asyncio.get_running_loop().time() - start_time) * 1000, 1
            )
            logger.info(
                "Turn completed for customer=%s in %.1fms (state=%s)",
                customer_id,
                self.last_turn_latency_ms,
                result.conversation_state,
            )
            return result

    async def _process_scoped_message(
        self, message: NormalizedIncomingMessage, customer_id: str
    ) -> NormalizedOutgoingResponse:
        preflight = await execute_preflight(self, message, customer_id)
        if preflight.early_response is not None:
            return preflight.early_response

        react_result = await execute_react_turn_loop(
            self,
            message,
            customer_id,
            incoming_text=preflight.incoming_text,
            planning_request_text=preflight.planning_request_text,
            user_confirmed=preflight.user_confirmed,
            current_cart=preflight.current_cart,
            address_id=preflight.address_id,
        )
        if react_result.early_response is not None:
            return react_result.early_response

        return await synthesize_turn_response(
            self,
            message,
            customer_id,
            final_text=react_result.final_text,
            actions=react_result.actions,
            conv_state=react_result.conv_state,
            last_cart_receipt=react_result.last_cart_receipt,
            last_cart_total=react_result.last_cart_total,
            out_order_id=react_result.out_order_id,
            out_order_total=react_result.out_order_total,
            out_bridge_url=react_result.out_bridge_url,
            address_changed=react_result.address_changed,
            suggestion_only=react_result.suggestion_only,
            suggested_items=react_result.suggested_items,
            restricted_items=react_result.restricted_items,
            search_failed_items=react_result.search_failed_items,
            budget_blocked_items=react_result.budget_blocked_items,
            unavailable_items=react_result.unavailable_items,
            reduced_items=react_result.reduced_items,
            guarded_change_message=react_result.guarded_change_message,
            pending_request_needs_retry=react_result.pending_request_needs_retry,
            step_limit_reached=react_result.step_limit_reached,
            checkout_executed=react_result.checkout_executed,
            user_confirmed=react_result.user_confirmed,
            incoming_text=react_result.incoming_text,
            addr_lbl=react_result.addr_lbl,
        )

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        *,
        customer_id: str,
        address_id: Optional[str],
        user_confirmed: Optional[bool] = None,
        current_cart: Optional[CommerceCart] = None,
    ) -> Any:
        return await execute_engine_tool(
            self,
            name,
            args,
            customer_id=customer_id,
            address_id=address_id,
            user_confirmed=user_confirmed,
            current_cart=current_cart,
        )

    async def _call_llm(
        self,
        contents: list[dict[str, Any]],
        *,
        address_id: Optional[str] = None,
        address_label: Optional[str] = None,
        cart: Optional[CommerceCart] = None,
        planning_only: bool = False,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        if planning_only:
            system_text = _SHOPPING_PLAN_PROMPT
            gemini_tools = [tool for tool in RAW_TOOL_DECLARATIONS if tool["name"] == "quick_add_items"]
        else:
            system_text = build_system_instruction(
                address_id=address_id, address_label=address_label, cart=cart,
            )
            gemini_tools = RAW_TOOL_DECLARATIONS
        return await self.gemini.generate_content(
            contents=contents,
            system_text=system_text,
            tools=gemini_tools,
        )

    async def _read_budget_cap(self, text: str) -> float | None:
        """Extract whole-basket rupee budget cap using the engine's Gemini client."""
        return await read_budget_cap(text, self.gemini)

