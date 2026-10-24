"""Production Grocery Concierge Single-Turn Agent Engine.

Coordinates Gemini 3.5 Flash NLU, deterministic 50ms button routing,
parallel Swiggy dark-store commerce tools, 3-lock latch safety, and WhatsApp receipts.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from backend.agent.address_tools import (
    execute_get_saved_addresses,
    execute_select_delivery_address,
)
from backend.agent.approval import (
    cart_fingerprint,
    check_cart_drift,
    is_confirmed,
)
from backend.agent.button_router import handle_button_action
from backend.agent.checkout_executor import execute_gated_checkout
from backend.agent.config import BRAIN_FALLBACK_MODEL, BRAIN_MODEL
from backend.agent.customer_advocate import CustomerAdvocate
from backend.agent.formatters import _format_inr, build_address_choice_response, format_cart_receipt
from backend.agent.gemini import GeminiClient
from backend.agent.budget import read_budget_cap
from backend.agent.prompts import build_system_instruction
from backend.agent.schemas import RAW_TOOL_DECLARATIONS
from backend.agent.session import CustomerSession
from backend.agent.session_manager import (
    dump_task_state_dict,
    record_pending_approval,
    record_pending_cart_clear,
    restore_task_state_dict,
)
from backend.agent.tools import SwiggyAgentTools
from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.integrations.commerce.exceptions import (
    ProviderAuthError,
    ProviderRateLimitedError,
)
from backend.integrations.commerce.models import CommerceCart, CommerceProductItem
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.engine")


# ---------------------------------------------------------------------------
# Public Helpers (Backward-compatible with tests)
# ---------------------------------------------------------------------------

def order_message(result: dict[str, Any]) -> str:
    """Write customer message deterministically from checkout result."""
    order_id = result.get("order_id") or ""
    total = result.get("formatted_grand_total")
    if not total and result.get("grand_total") is not None:
        total = _format_inr(result["grand_total"])
    total_str = f" for {total}" if total else ""
    order_str = f" {order_id}" if order_id else ""
    status = result.get("status")

    if status == "ORDER_PLACED":
        tracking_url = result.get("tracking_url")
        track_str = f" Track your order here: {tracking_url}" if tracking_url else ""
        return f"Your order{order_str}{total_str} has been placed!{track_str}".strip()
    elif status == "PAYMENT_PENDING":
        pay_link = result.get("upi_intent_url") or result.get("bridge_url") or result.get("qr_code_url")
        tracking_url = result.get("tracking_url")
        parts = [f"🛒 *Your order{order_str}{total_str} is ready for payment!*"]
        if pay_link:
            parts.extend(["", f"👉 *1-Tap UPI Link (Google Pay / PhonePe):*\n{pay_link}"])
        else:
            parts.extend(["", "Please complete payment in your Swiggy app."])
        if tracking_url:
            parts.extend(["", f"📍 *Live Tracking:* {tracking_url}"])
        parts.extend(["", "Tap *Check Payment* once paid, or *Change Items*."])
        return "\n".join(parts).strip()
    elif status == "PARTIAL_ORDER":
        s_cnt = result.get("success_count", 0)
        f_cnt = result.get("failure_count", 0)
        return f"partial order: {s_cnt} placed and {f_cnt} failed"
    return ""


def process_checkout_outcome(
    engine: Any,
    customer_id: str,
    checkout_executed: bool = False,
    checkout_result: Optional[dict[str, Any]] = None,
    last_cart_receipt: Optional[str] = None,
    current_cart: Optional[CommerceCart] = None,
    addr_lbl: Optional[str] = None,
    final_text: str = "",
    actions: Optional[list[InteractiveAction]] = None,
    pending_request_needs_retry: bool = False,
    **kwargs: Any,
) -> tuple[str, str, list[InteractiveAction], Optional[str], Optional[float], Optional[str]]:
    """Evaluate checkout results and return (conv_state, final_text, actions, order_id, order_total, bridge_url)."""
    out_order_id: str | None = None
    out_order_total: float | None = None
    out_bridge_url: str | None = None
    conv_state = "READY"
    actions = list(actions or [])
    session = engine.get_session(customer_id) if hasattr(engine, "get_session") else None

    if pending_request_needs_retry:
        conv_state = "NEEDS_DECISION"

    if checkout_executed and checkout_result:
        if not checkout_result.get("success"):
            err = checkout_result.get("error")
            if err == "CONFIRMATION_REQUIRED":
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
                token = ""
                if session and getattr(session, "pending_approval", None) and session.pending_approval.token:
                    token = session.pending_approval.token
                actions = []
                if token:
                    actions.append(InteractiveAction(id=f"confirm_order:{token}", title="Confirm Order"))
                actions.append(InteractiveAction(id="modify_cart", title="Change Items"))
                receipt_str = last_cart_receipt or (format_cart_receipt(current_cart, addr_lbl or "Home") if current_cart else "")
                final_text = f"{receipt_str}\n\n👉 Reply *Confirm* to place order, or let me know if you'd like to change anything!".strip()
                return conv_state, final_text, actions, None, None, None
            elif err in ("ORDER_STATE_UNKNOWN", "ATTEMPT_UNRESOLVED") or checkout_result.get("status") == "ORDER_STATE_UNKNOWN":
                conv_state = "RECOVERING"
                final_text = (
                    "I couldn't verify whether checkout completed. "
                    "Please check the order status in Swiggy or contact support before trying again. "
                    "Further checkout is on hold until this is resolved."
                )
                return conv_state, final_text, actions, None, None, None
            else:
                conv_state = "FAILED"
                msg = checkout_result.get("message") or "Checkout could not be completed. Please try again."
                final_text = f"{msg}\n{final_text}".strip() if final_text else msg
                return conv_state, final_text, actions, None, None, None
        else:
            status = checkout_result.get("status")
            out_order_id = checkout_result.get("order_id")
            out_order_total = checkout_result.get("grand_total")
            out_bridge_url = checkout_result.get("bridge_url") or checkout_result.get("upi_intent_url")
            out_paas_id = checkout_result.get("paas_id")
            if session and out_paas_id:
                session.paas_id = out_paas_id
            msg = order_message(checkout_result)

            if status == "ORDER_PLACED":
                conv_state = "ORDER_PLACED"
                final_text = msg or f"Your order #{out_order_id} has been placed!"
                actions = []
            elif status == "PAYMENT_PENDING":
                conv_state = "AWAITING_PAYMENT"
                final_text = f"{msg}\n{final_text}".strip() if final_text else msg
                actions = []
                if out_bridge_url:
                    actions.append(
                        InteractiveAction(action_type="url", id=f"pay:{out_order_id}", title="Pay with UPI", url=out_bridge_url)
                    )
            elif status == "PARTIAL_ORDER":
                conv_state = "NEEDS_DECISION"
                final_text = f"{msg}\n{final_text}".strip() if final_text else msg
            else:
                conv_state = "ORDER_PLACED"
                final_text = msg or f"Order updated: {status}"
            return conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url

    return conv_state, final_text, actions, None, None, None


async def synthesize_turn_response(
    engine: Any,
    message: NormalizedIncomingMessage,
    customer_id: str,
    *,
    final_text: str = "",
    actions: Optional[list[InteractiveAction]] = None,
    conv_state: str = "READY",
    last_cart_receipt: Optional[str] = None,
    checkout_executed: bool = False,
    unavailable_items: Optional[list[str]] = None,
    **kwargs: Any,
) -> NormalizedOutgoingResponse:
    """Outbound response synthesizer creating clean receipt cards and 1-tap actions."""
    session = engine.get_session(customer_id) if hasattr(engine, "get_session") else None
    actions = list(actions or [])

    # 0. Two-step clear cart confirmation
    if session and getattr(session, "pending_cart_clear", None):
        token = session.pending_cart_clear.token
        actions = [
            InteractiveAction(id=f"clear_cart_confirm:{token}", title="Clear Cart"),
            InteractiveAction(id="modify_cart", title="Keep Cart"),
        ]
        conv_state = "AWAITING_CLEAR_CONFIRMATION"
        if not final_text or "clear cart?" not in final_text.lower():
            final_text = "Clear cart? This will remove all items from your basket."
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=final_text,
            conversation_state=conv_state,
            interactive_actions=actions,
        )

    # 1. Unavailable items notice
    if unavailable_items:
        unavail_str = ", ".join(unavailable_items)
        notice = f"I checked with Swiggy Instamart, but {unavail_str} is currently out of stock at your store."
        final_text = f"{notice}\n\n{final_text}".strip() if final_text else notice

    # 2. Append deterministic receipt card if cart exists
    if last_cart_receipt and not checkout_executed:
        if last_cart_receipt not in final_text:
            final_text = f"{final_text.strip()}\n\n{last_cart_receipt}".strip() if final_text.strip() else last_cart_receipt
        if not actions:
            token = session.pending_approval.token if (session and session.pending_approval) else ""
            actions = [
                InteractiveAction(id=f"confirm_order:{token}" if token else "confirm_order", title="Confirm Order"),
                InteractiveAction(id="modify_cart", title="Change Items"),
            ]
        if conv_state == "READY":
            conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

    return NormalizedOutgoingResponse(
        recipient_id=message.sender_id,
        channel=message.channel,
        text=final_text or "How can I help with your grocery order today?",
        conversation_state=conv_state,
        interactive_actions=actions,
    )


class PreflightResult:
    def __init__(
        self,
        early_response: Optional[NormalizedOutgoingResponse] = None,
        incoming_text: str = "",
        user_confirmed: bool = False,
        current_cart: Optional[CommerceCart] = None,
        address_id: Optional[str] = None,
    ):
        self.early_response = early_response
        self.incoming_text = incoming_text
        self.user_confirmed = user_confirmed
        self.current_cart = current_cart
        self.address_id = address_id


async def execute_preflight(
    engine: Any, message: NormalizedIncomingMessage, customer_id: str
) -> PreflightResult:
    """Preflight check: inactivity timeout, budget caps, auth expiry, and confirmation check."""
    session = engine.get_session(customer_id)
    incoming_text = (message.text or "").strip()

    # Session inactivity check (30 minutes)
    current_time = time.time()
    last_seen = session.last_active_ts if session.last_active_ts > 0 else None
    session.last_active_ts = current_time
    if last_seen and (current_time - last_seen) > 1800:
        session.order_address_confirmed = False
        session.address_id = None
        session.address_label = None
        session.pending_approval = None

    # Rupee budget cap extraction
    budget_cap = await engine._read_budget_cap(incoming_text)
    if budget_cap is not None:
        session.budget_inr = float(budget_cap)

    current_cart: Optional[CommerceCart] = None
    try:
        current_cart = await engine.commerce.get_cart()
    except ProviderAuthError:
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="Your Swiggy login has expired. Please reconnect your account to continue.",
                conversation_state="RECOVERING",
            )
        )
    except ProviderRateLimitedError as exc:
        return PreflightResult(
            early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="Swiggy is temporarily busy. Please wait a moment and try again.",
                conversation_state="RECOVERING",
            )
        )
    except Exception as exc:
        logger.debug("Initial cart probe: %s", exc)

    user_confirmed = await is_confirmed(incoming_text)
    return PreflightResult(
        incoming_text=incoming_text,
        user_confirmed=user_confirmed,
        current_cart=current_cart,
        address_id=session.address_id,
    )


async def execute_engine_tool(
    engine: Any,
    name: str,
    args: dict[str, Any],
    *,
    customer_id: str,
    address_id: Optional[str],
    user_confirmed: Optional[bool] = None,
    current_cart: Optional[CommerceCart] = None,
) -> Any:
    """Dispatch LLM function call to SwiggyAgentTools."""
    logger.info("Executing agent tool: %s", name)
    session = engine.get_session(customer_id)

    if name == "get_saved_addresses":
        return await engine.tools.get_saved_addresses(customer_id)
    elif name == "select_delivery_address":
        session.pending_approval = None
        res = await engine.tools.select_delivery_address(customer_id, args.get("address_id", ""))
        if res.get("success") and res.get("address_id"):
            session.address_id = res["address_id"]
            session.address_label = res.get("clean_address") or res.get("label") or "Selected Address"
            session.order_address_confirmed = True
        return res
    elif name == "create_address":
        return await engine.commerce.create_address(
            customer_id=customer_id,
            street=args.get("street", ""),
            city=args.get("city", ""),
            label=args.get("label"),
            latitude=args.get("latitude"),
            longitude=args.get("longitude"),
        )
    elif name == "delete_address":
        return await engine.commerce.delete_address(customer_id=customer_id, address_id=args.get("address_id", ""))
    elif name == "get_go_to_items":
        addr = args.get("address_id") or address_id
        return await engine.tools.get_go_to_items(address_id=addr)
    elif name == "search_products":
        addr = args.get("address_id") or address_id
        return await engine.tools.search_products(args.get("query", ""), address_id=addr)
    elif name == "batch_search_products":
        addr = args.get("address_id") or address_id
        return await engine.tools.batch_search_products(args.get("queries", []), address_id=addr)
    elif name == "get_cart":
        return await engine.tools.get_cart(delivery_location=session.address_label or "Home")
    elif name == "manage_basket":
        session.pending_approval = None
        res = await engine.tools.manage_basket(
            address_id=args.get("address_id") or address_id or "",
            add=args.get("add"),
            remove=args.get("remove"),
            set_quantity=args.get("set_quantity"),
            current_cart=current_cart,
            delivery_location=session.address_label or "Home",
            budget_cap_inr=session.budget_inr,
            session=session,
        )
        if res.get("verified_fingerprint"):
            session.known_cart_fingerprint = res["verified_fingerprint"]
        return res
    elif name == "clear_cart":
        try:
            cart = await engine.commerce.get_cart()
        except Exception:
            cart = None
        if not cart or not cart.items:
            return {"success": True, "message": "Cart is already empty."}
        record_pending_cart_clear(session, cart, session.address_id or cart.address_id or "")
        return {"success": False, "error": "CLEAR_CONFIRMATION_REQUIRED"}
    elif name == "get_orders":
        return await engine.tools.get_orders(count=args.get("count", 5))
    elif name == "get_order_details":
        return await engine.tools.get_order_details(order_id=args.get("order_id", ""))
    elif name == "track_order":
        return await engine.tools.track_order(order_id=args.get("order_id", ""), lat=args.get("lat"), lng=args.get("lng"))
    elif name == "list_coupons":
        return await engine.tools.list_available_coupons(cart_id=args.get("cart_id"))
    elif name == "apply_coupon":
        return await engine.tools.apply_cart_coupon(code=args.get("code", ""), cart_id=args.get("cart_id"))
    elif name == "report_error":
        return await engine.tools.report_error(report_id=args.get("report_id", ""), details=args.get("details"))
    elif name == "set_budget":
        cap = args.get("budget_cap_inr")
        if cap is not None:
            session.budget_inr = float(cap)
        return {"success": True, "budget_cap_inr": session.budget_inr}
    elif name == "checkout":
        try:
            return await engine.tools.checkout(
                cart_id=args.get("cart_id", ""),
                address_id=session.address_id or "",
                payment_method="UPI",
                is_user_confirmed=bool(user_confirmed),
                budget_inr=session.budget_inr,
                expected_cart_fingerprint=session.known_cart_fingerprint,
                customer_id=customer_id,
            )
        except Exception as exc:
            session.pending_approval = None
            return {
                "success": False,
                "error": "ORDER_STATE_UNKNOWN",
                "retryable": False,
                "message": f"Checkout state unresolved: {exc}",
            }

    logger.warning("Unknown tool name: %s", name)
    return {"success": False, "error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# GroceryAgentEngine
# ---------------------------------------------------------------------------

class GroceryAgentEngine:
    """Production WhatsApp Concierge Engine powered by Gemini 3.5 Flash."""

    def __init__(
        self,
        commerce: CommercePort,
        gemini_api_key: Optional[str] = None,
        state_store: Optional[Any] = None,
        attempt_store: Optional[Any] = None,
        gemini_model: Optional[str] = None,
        gemini_fallback_model: Optional[str] = None,
        timeout: float = 20.0,
        **kwargs: Any,
    ) -> None:
        self.commerce = commerce
        self.state_store = state_store
        self.attempt_store = attempt_store
        self.attempt_store = None
        self.gemini_api_key = gemini_api_key or settings.GEMINI_API_KEY
        self.gemini_model = gemini_model or BRAIN_MODEL
        self.gemini_fallback_model = gemini_fallback_model or BRAIN_FALLBACK_MODEL
        self.timeout = timeout
        self._sessions: dict[str, CustomerSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.last_turn_latency_ms: Optional[float] = None

        self.gemini = GeminiClient(
            api_key=self.gemini_api_key or "",
            primary_model=self.gemini_model,
            fallback_model=self.gemini_fallback_model,
            timeout=self.timeout,
        )
        self.tools = SwiggyAgentTools(commerce, gemini_client=self.gemini)
        from backend.channels.payment_poller import PaymentPoller
        self.payment_poller = PaymentPoller(
            commerce=self.commerce,
            store=getattr(self, "state_store", None),
            engine=self,
        )

    def get_session(self, customer_id: str) -> CustomerSession:
        """Return or create active CustomerSession for customer_id."""
        sess = self._sessions.get(customer_id)
        if sess is None:
            sess = CustomerSession(customer_id=customer_id)
            self._sessions[customer_id] = sess
        return sess

    async def forget_customer(self, customer_id: str) -> None:
        """Purge all in-memory state for a customer."""
        self._locks.pop(customer_id, None)
        sess = self._sessions.pop(customer_id, None)
        if sess is not None:
            sess.clear_all()

    def evict_inactive_sessions(self, ttl_seconds: float = 1800.0) -> int:
        """Evict sessions that exceeded inactivity TTL."""
        now = time.time()
        to_evict = [
            cid for cid, s in self._sessions.items()
            if (now - (getattr(s, "last_active_time", None) or getattr(s, "last_active_ts", 0.0) or 0.0)) > ttl_seconds
        ]
        for cid in to_evict:
            self._locks.pop(cid, None)
            s = self._sessions.pop(cid, None)
            if s is not None:
                s.clear_all()
        return len(to_evict)

    def _restore_task_state(self, customer_id: str, state: dict[str, Any] | None) -> None:
        session, _ = restore_task_state_dict(customer_id=customer_id, state=state)
        self._sessions[customer_id] = session

    def _task_state_snapshot(self, customer_id: str) -> dict[str, Any]:
        return dump_task_state_dict(self.get_session(customer_id))

    def reset_customer_order_address(self, customer_id: str) -> None:
        session = self.get_session(customer_id)
        session.reset_order_address()
        session.pending_approval = None

    def get_history(self, customer_id: str) -> list[dict[str, Any]]:
        return list(self.get_session(customer_id).history or [])

    def _prune_history(self, customer_id: str, max_user_turns: int = 20) -> None:
        session = self.get_session(customer_id)
        history = session.history or []
        user_turn_count = sum(1 for m in history if m.get("role") == "user")
        if user_turn_count > max_user_turns:
            excess = user_turn_count - max_user_turns
            pruned: list[dict[str, Any]] = []
            dropped = 0
            for turn in history:
                if turn.get("role") == "user" and dropped < excess:
                    dropped += 1
                    continue
                pruned.append(turn)
            session.history = pruned

    async def process_message(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        """Single authoritative turn processor under per-customer lock and customer scope."""
        start_time = asyncio.get_running_loop().time()
        customer_id = message.customer_id or message.sender_id
        lock = self._locks.setdefault(customer_id, asyncio.Lock())

        async with lock:
            if self.state_store is not None:
                state_data = await self.state_store.load(customer_id)
                self._restore_task_state(customer_id, state_data)
                self._prune_history(customer_id)

            with self.commerce.customer_scope(customer_id):
                try:
                    result = await self._process_scoped_message(message, customer_id)
                    if self.state_store is not None:
                        self._prune_history(customer_id)
                        await self.state_store.save(customer_id, self._task_state_snapshot(customer_id))
                except Exception:
                    logger.exception("Turn error for customer=%s; skipping state save.", customer_id)
                    raise

            self.last_turn_latency_ms = round(
                (asyncio.get_running_loop().time() - start_time) * 1000, 1
            )
            logger.info("Turn completed for customer=%s in %.1fms (state=%s)", customer_id, self.last_turn_latency_ms, result.conversation_state)

            if result.conversation_state == "AWAITING_PAYMENT" and result.order_id:
                if hasattr(self, "payment_poller") and self.payment_poller:
                    target_paas_id = (
                        getattr(result, "paas_id", None)
                        or getattr(session, "paas_id", None)
                        or result.order_id
                    )
                    self.payment_poller.start_polling(
                        customer_id=customer_id,
                        order_id=result.order_id,
                        paas_id=target_paas_id,
                        recipient_id=message.sender_id,
                    )
            return result

    handle_message = process_message

    async def _process_scoped_message(
        self, message: NormalizedIncomingMessage, customer_id: str
    ) -> NormalizedOutgoingResponse:
        # 1. Fast 50ms Deterministic Button Router
        btn_payload = message.interactive_id or (message.text.strip() if message.text else "")
        session = self.get_session(customer_id)
        btn_resp = await handle_button_action(
            payload=btn_payload,
            session=session,
            commerce=self.commerce,
            customer_id=customer_id,
            recipient_id=message.sender_id,
            channel=message.channel,
        )
        if btn_resp is not None:
            return btn_resp

        # 2. Preflight verification
        preflight = await execute_preflight(self, message, customer_id)
        if preflight.early_response is not None:
            return preflight.early_response

        incoming_text = preflight.incoming_text
        current_cart = preflight.current_cart

        # 3. Natural Language Confirmation Check ("confirm", "proceed", "yes")
        if preflight.user_confirmed and session.pending_approval is not None:
            drift = check_cart_drift(current_cart, session.pending_approval)
            if drift:
                receipt = format_cart_receipt(current_cart, address_label=session.address_label)
                session.pending_approval = None
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text=f"Your basket changed ({drift}). Please review your updated bill before confirming:\n\n{receipt}",
                    conversation_state="AWAITING_APPROVAL",
                    interactive_actions=[
                        InteractiveAction(id="confirm_order", title="Confirm Order"),
                        InteractiveAction(id="modify_cart", title="Change Items"),
                    ],
                )
            return await execute_gated_checkout(
                self,
                customer_id,
                token=session.pending_approval.token,
                recipient_id=message.sender_id,
                channel=message.channel,
            )

        # 4. Single-Turn Gemini Brain (Tool Execution + Follow-up Speech)
        history = list(session.history or [])
        history.append({"role": "user", "parts": [{"text": incoming_text}]})

        response_data = await self._call_llm(
            history,
            address_id=session.address_id,
            address_label=session.address_label,
            cart=current_cart,
            saved_addresses=getattr(session, "saved_addresses", None),
        )

        final_text = ""
        unavailable_items: list[str] = []

        if response_data:
            candidates = response_data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

                if function_calls:
                    history.append({"role": "model", "parts": parts})
                    response_parts = []
                    for fc in function_calls:
                        name = fc.get("name", "")
                        args = fc.get("args", {})
                        tool_res = await self._execute_tool(
                            name,
                            args,
                            customer_id=customer_id,
                            address_id=session.address_id,
                            user_confirmed=preflight.user_confirmed,
                            current_cart=current_cart,
                        )
                        response_parts.append({
                            "functionResponse": {
                                "name": name,
                                "response": tool_res if isinstance(tool_res, dict) else {"result": tool_res},
                            }
                        })
                        if name == "manage_basket" and isinstance(tool_res, dict):
                            unavailable_items.extend(tool_res.get("unavailable_items", []))

                    history.append({"role": "user", "parts": response_parts})

                    # Follow-up turn: Let Gemini speak naturally about what it added or changed
                    try:
                        current_cart = await self.commerce.get_cart()
                        follow_up = await self._call_llm(
                            history,
                            address_id=session.address_id,
                            address_label=session.address_label,
                            cart=current_cart,
                            saved_addresses=getattr(session, "saved_addresses", None),
                        )
                        if follow_up:
                            fu_cands = follow_up.get("candidates", [])
                            if fu_cands:
                                fu_parts = fu_cands[0].get("content", {}).get("parts", [])
                                history.append({"role": "model", "parts": fu_parts})
                                fu_texts = [p.get("text", "") for p in fu_parts if "text" in p]
                                if fu_texts:
                                    final_text = "\n".join(t.strip() for t in fu_texts if t.strip())
                    except Exception as exc:
                        logger.debug("Follow-up conversational turn: %s", exc)

                text_parts = [p.get("text", "") for p in parts if "text" in p]
                if text_parts and not final_text:
                    final_text = "\n".join(t.strip() for t in text_parts if t.strip())

        session.history = history
        self._prune_history(customer_id)

        # 5. Build Receipt and Actions
        receipt_str: Optional[str] = None
        actions: list[InteractiveAction] = []
        conv_state = "READY"

        if current_cart and current_cart.items and not getattr(session, "pending_cart_clear", None):
            advocate = CustomerAdvocate(self.commerce)
            coupon_res = await advocate.optimize_cart(current_cart, address_id=session.address_id)
            receipt_str = format_cart_receipt(
                current_cart,
                delivery_location=session.address_label or "Home",
                advocate_info=coupon_res,
            )
            addr_id = session.address_id or current_cart.address_id or ""
            record_pending_approval(session, current_cart, addr_id)
            token = session.pending_approval.token if session.pending_approval else ""
            actions = [
                InteractiveAction(id=f"confirm_order:{token}" if token else "confirm_order", title="Confirm Order"),
                InteractiveAction(id="modify_cart", title="Change Items"),
            ]
            conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

        return await synthesize_turn_response(
            self,
            message,
            customer_id,
            final_text=final_text,
            actions=actions,
            conv_state=conv_state,
            last_cart_receipt=receipt_str,
            unavailable_items=unavailable_items,
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
        saved_addresses: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        system_text = build_system_instruction(
            address_id=address_id,
            address_label=address_label,
            cart=cart,
            saved_addresses=saved_addresses,
        )
        return await self.gemini.generate_content(
            contents=contents,
            system_text=system_text,
            tools=RAW_TOOL_DECLARATIONS,
        )

    async def _read_budget_cap(self, text: str) -> float | None:
        """Extract whole-basket rupee budget cap using the engine's Gemini client."""
        return await read_budget_cap(text, self.gemini)


__all__ = [
    "GroceryAgentEngine",
    "PreflightResult",
    "execute_engine_tool",
    "execute_preflight",
    "order_message",
    "process_checkout_outcome",
    "synthesize_turn_response",
]
