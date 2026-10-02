"""Autonomous ReAct agent engine for Swiggy Instamart grocery ordering powered by Groq and OpenRouter."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from typing import Any, Optional

import httpx

from backend.agent.schemas import OPENAI_TOOL_DECLARATIONS
from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.budget import extract_total_budget
from backend.agent.tool_scheduler import execute_tool_calls
from backend.agent.tools import (
    SwiggyAgentTools,
    format_cart_receipt,
)
from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.engine")

from backend.agent.guards import (  # noqa: E402, F401
    _CONFIRMATION_PHRASES,
    _HESITATION_PHRASES,
    _ORDER_SUCCESS_PATTERNS,
    _RESET_COMMANDS,
    _claims_order_success,
    _explains_failure,
    is_explicit_confirmation,
)
from backend.agent.prompts import (  # noqa: E402, F401
    _SYSTEM_PROMPT,
    build_system_instruction,
)




class GroceryAgentEngine:
    """Conversational ReAct agent driving Swiggy Instamart through Groq LPU and OpenRouter function calling."""

    def __init__(
        self,
        commerce: CommercePort,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        groq_model: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        timeout: float = 25.0,
        attempt_store: Any | None = None,
        state_store: Any | None = None,
    ) -> None:
        self.commerce = commerce
        self.tools = SwiggyAgentTools(commerce)
        self.attempt_store = attempt_store
        self.state_store = state_store
        self.groq_api_key = groq_api_key or settings.GROQ_API_KEY
        self.groq_model = groq_model or settings.GROQ_MODEL
        self.openrouter_api_key = openrouter_api_key or settings.OPENROUTER_API_KEY
        self.openrouter_model = openrouter_model or settings.OPENROUTER_MODEL
        self.api_key = api_key or self.groq_api_key or self.openrouter_api_key
        self.model = model or self.groq_model or self.openrouter_model
        self.timeout = timeout
        # Unified atomic customer session map + compatibility views
        self._sessions: dict[str, Any] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._customer_address: dict[str, str] = {}
        self._customer_address_label: dict[str, str] = {}
        self._order_address_confirmed: dict[str, bool] = {}
        self._awaiting_address_choice: dict[str, list[dict[str, Any]]] = {}
        self._pending_checkout: dict[str, bool] = {}
        self._last_interaction_time: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_call_time: float = 0.0
        self.last_llm_error: Optional[str] = None
        self.last_turn_latency_ms: Optional[float] = None
        self._client: Optional[httpx.AsyncClient] = None

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
        from backend.agent.session import CustomerSession

        state = state or {}
        self._history[customer_id] = state.get("history") or []
        for mapping, field in (
            (self._customer_address, "address_id"),
            (self._customer_address_label, "address_label"),
            (self._order_address_confirmed, "order_address_confirmed"),
            (self._awaiting_address_choice, "awaiting_address_choice"),
            (self._last_interaction_time, "last_active_ts"),
        ):
            mapping.pop(customer_id, None)
            if state.get(field) is not None:
                mapping[customer_id] = state[field]
        approval = state.get("pending_approval")
        self._sessions[customer_id] = CustomerSession(
            customer_id=customer_id,
            history=self._history[customer_id],
            budget_inr=state.get("budget_inr"),
            pending_approval=PendingApproval(**approval) if approval else None,
            unresolved_items=state.get("unresolved_items") or [],
            known_cart_fingerprint=state.get("known_cart_fingerprint"),
            external_cart_pending=bool(state.get("external_cart_pending", False)),
        )

    def _task_state_snapshot(self, customer_id: str) -> dict[str, Any]:
        session = self.get_session(customer_id)
        approval = session.pending_approval
        return {
            "history": self.get_history(customer_id),
            "address_id": self._customer_address.get(customer_id),
            "address_label": self._customer_address_label.get(customer_id),
            "order_address_confirmed": self._order_address_confirmed.get(customer_id, False),
            "awaiting_address_choice": self._awaiting_address_choice.get(customer_id),
            "last_active_ts": self._last_interaction_time.get(customer_id),
            "budget_inr": session.budget_inr,
            "pending_approval": (
                {"fingerprint": approval.fingerprint, "expires_at": approval.expires_at}
                if approval else None
            ),
            "unresolved_items": session.unresolved_items,
            "known_cart_fingerprint": session.known_cart_fingerprint,
            "external_cart_pending": session.external_cart_pending,
        }

    def _address_choice_response(
        self, message: NormalizedIncomingMessage, addresses: list[dict[str, Any]]
    ) -> NormalizedOutgoingResponse:
        lines = [
            f"*{address.get('_choice_code')}* — {address.get('clean_address') or address.get('street') or address.get('label')}"
            for address in addresses
        ]
        prompt = "📍 *Which address should I use?*\n\n" + "\n".join(lines)
        prompt += "\n\nReply with the code beside your address, or tap a button."
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=prompt,
            interactive_actions=[
                InteractiveAction(
                    action_type="button", id=f"addr_choice_{address['_choice_code']}",
                    title=str(address.get("label") or f"Address {index}")[:20],
                )
                for index, address in enumerate(addresses[:3], 1)
            ],
            conversation_state="NEEDS_DECISION",
        )

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
        fingerprint = cart_fingerprint(cart, address_id)
        session = self.get_session(customer_id)
        session.pending_approval = (
            PendingApproval(fingerprint=fingerprint, expires_at=time.time() + 900)
            if fingerprint else None
        )
        if fingerprint:
            session.known_cart_fingerprint = fingerprint
        return fingerprint is not None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize persistent HTTP/2 client with keep-alive connection pool."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def close(self) -> None:
        """Close persistent HTTP connection pool on shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _connect_url(self, ticket: str) -> str:
        base_url = (settings.CONNECT_BASE_URL or "https://grocerr.vercel.app").rstrip("/")
        return f"{base_url}/?connect_ticket={ticket}"

    async def _auth_expired_response(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        from backend.integrations.commerce.connect_tickets import default_connect_tickets

        try:
            ticket = await default_connect_tickets.issue(message.customer_id or "")
            instructions = (
                "Your Swiggy login needs reconnecting. Open this one-time link from your WhatsApp chat:\n\n"
                f"👉 {self._connect_url(ticket)}\n\n"
                "The link expires in 10 minutes. After connecting, message me again."
            )
        except Exception:
            logger.exception("Could not issue a customer-scoped Swiggy connection link.")
            instructions = "Swiggy connection is temporarily unavailable. Please message me again shortly."
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=instructions,
            conversation_state="AUTH_REQUIRED",
        )

    def get_history(self, customer_id: str) -> list[dict[str, Any]]:
        if customer_id not in self._history:
            self._history[customer_id] = []
        return self._history[customer_id]

    def _prune_history(self, customer_id: str, max_user_turns: int = 20) -> None:
        """Keep conversation history bounded by whole user turn boundaries and compact past search returns."""
        hist = self._history.get(customer_id, [])
        if not hist:
            return

        if self.state_store is not None:
            cutoff_time = time.time() - 30 * 86400
            hist = [entry for entry in hist if isinstance(entry.get("recorded_at"), (int, float))
                    and entry["recorded_at"] > cutoff_time]
            self._history[customer_id] = hist

        # Identify turn start indices: user messages with user text (not function responses)
        user_turn_starts = [
            i
            for i, entry in enumerate(hist)
            if entry.get("role") == "user"
            and any("text" in p for p in entry.get("parts", []))
        ]

        if len(user_turn_starts) > max_user_turns:
            cutoff = user_turn_starts[-max_user_turns]
            hist = hist[cutoff:]
            self._history[customer_id] = hist
        elif not user_turn_starts and len(hist) > 12:
            hist = hist[-12:]
            self._history[customer_id] = hist

        # Compact bulky product search returns from older turns while preserving variants (spin_id & sku_id)
        for entry in hist[:-2]:
            if entry.get("role") == "user" and "parts" in entry:
                for part in entry["parts"]:
                    fn_resp = part.get("functionResponse", {})
                    content = fn_resp.get("response", {}).get("content", {})
                    if isinstance(content, dict) and "products" in content and len(content.get("products", [])) > 2:
                        compacted_products = []
                        for p in content["products"][:2]:
                            variants = p.get("variants") or []
                            first_var = variants[0] if variants and isinstance(variants[0], dict) else {}
                            compacted_products.append({
                                "product_id": p.get("product_id"),
                                "name": p.get("name") or first_var.get("name"),
                                "spin_id": p.get("spin_id") or first_var.get("spin_id"),
                                "sku_id": p.get("sku_id") or first_var.get("sku_id"),
                                "unit_price": p.get("unit_price") or first_var.get("price"),
                                "variants": variants[:1],
                            })
                        content["products"] = compacted_products

    async def _poll_payment_status(
        self,
        *,
        order_id: str,
        recipient_id: str,
        channel: ChannelType,
        customer_id: str,
        max_attempts: int = 6,
        interval_seconds: float = 10.0,
    ) -> None:
        """Poll Swiggy order tracking every 10s for up to 60s per rate-limit rules."""
        logger.info("Starting background payment poller for order_id=%s (cadence=%.1fs)", order_id, interval_seconds)
        for _ in range(max_attempts):
            await asyncio.sleep(interval_seconds)
            try:
                with self.commerce.customer_scope(customer_id):
                    tracking = await self.commerce.track_order(order_id)
                status_val = (
                    tracking.status.value
                    if hasattr(tracking.status, "value")
                    else str(tracking.status)
                ).upper()
                if status_val in {"ORDER_PLACED", "CONFIRMED", "PACKING", "OUT_FOR_DELIVERY"}:
                    logger.info("Payment confirmed by poller for order_id=%s status=%s", order_id, status_val)
                    eta = f" ETA: ~{tracking.eta_minutes} mins." if tracking.eta_minutes else ""
                    msg = NormalizedOutgoingResponse(
                        recipient_id=recipient_id,
                        channel=channel,
                        text=(
                            f"🎉 *Payment Confirmed!*\n\n"
                            f"Your Swiggy Instamart order *#{order_id}* is placed and being prepared at the dark store.{eta}\n\n"
                            f"You can message me *\"track order\"* anytime for live updates!"
                        ),
                        conversation_state="ORDER_PLACED",
                        order_id=order_id,
                    )
                    from backend.channels.whatsapp import default_whatsapp_adapter
                    await default_whatsapp_adapter.send_response(msg)
                    return
                if status_val in {"FAILED", "CANCELLED", "CANCELED"}:
                    logger.warning("Order failed according to poller: %s", order_id)
                    return
            except Exception as exc:
                logger.debug("Payment poller poll error for order_id=%s: %s", order_id, exc)

    async def handle_message(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        """Process one WhatsApp turn through the autonomous Groq LPU / OpenRouter agent loop with per-customer serialization."""
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
            if self.state_store is not None:
                self._restore_task_state(customer_id, await self.state_store.load(customer_id))
                self._prune_history(customer_id)
            with self.commerce.customer_scope(customer_id):
                result = await self._process_scoped_message(message, customer_id)
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
        history = self.get_history(customer_id)
        session = self.get_session(customer_id)

        # Handle interactive button callbacks
        incoming_text = message.text.strip()
        if message.interactive_id:
            if message.interactive_id == "confirm_order":
                incoming_text = "Yes, please confirm and place the order now."
            elif message.interactive_id == "modify_cart":
                incoming_text = "I would like to change something in my cart."
            elif message.interactive_id in ("start_fresh", "clear_cart"):
                incoming_text = "Please clear my cart and start fresh."

        # Extract explicit spending budget if mentioned by customer
        budget = extract_total_budget(incoming_text)
        if budget is not None:
            session.budget_inr = budget
            logger.info("Captured customer budget constraint: ₹%.2f for %s", budget, customer_id)

        norm_text = incoming_text.casefold().strip("!.? \t\n")

        if norm_text == "cancel order":
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=("I haven't cancelled an order. If you mean your current basket, "
                      "reply 'clear cart'. For an order already placed, check its status in Swiggy."),
                conversation_state="NEEDS_DECISION",
            )

        # Fast-path 1: Reset / Clear basket command
        if norm_text in _RESET_COMMANDS:
            try:
                clear_result = await self.tools.clear_cart()
                verified_cart = await self.commerce.get_cart() if clear_result.get("success") else None
            except Exception as exc:
                logger.warning("Fast-path clear_cart failed: %s", exc)
                clear_result = {"success": False}
                verified_cart = None
            if not clear_result.get("success") or verified_cart is None or verified_cart.items:
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I couldn't verify that your basket is empty. Please check it before trying again.",
                    conversation_state="FAILED",
                )
            self._history[customer_id] = []
            session.clear_all()
            self.reset_customer_order_address(customer_id)
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="🗑️ *Basket Cleared!*\n\nYour basket is now completely empty. What groceries can I get for you today?",
                conversation_state="READY",
            )

        # Explicit Human Confirmation Detection (Server-side safety gate with negation precedence)
        user_confirmed = (
            message.interactive_id == "confirm_order"
            or is_explicit_confirmation(incoming_text)
        )

        # Inspect current live cart
        current_cart: Optional[CommerceCart] = None
        try:
            current_cart = await self.commerce.get_cart()
        except Exception as exc:
            logger.debug("Failed to fetch initial cart for customer=%s: %s", customer_id, exc)

        if session.known_cart_fingerprint:
            observed_fingerprint = (
                cart_fingerprint(current_cart, current_cart.address_id or session.address_id or "")
                if current_cart else None
            )
            if observed_fingerprint != session.known_cart_fingerprint:
                session.external_cart_pending = True
                session.pending_approval = None
        if session.external_cart_pending:
            if norm_text == "use changes" and current_cart:
                observed_fingerprint = cart_fingerprint(
                    current_cart, current_cart.address_id or session.address_id or ""
                )
                if observed_fingerprint:
                    session.known_cart_fingerprint = observed_fingerprint
                    session.external_cart_pending = False
                    return NormalizedOutgoingResponse(
                        recipient_id=message.sender_id, channel=message.channel,
                        text="I’ve included the Swiggy cart changes. Please tell me what to change next.\n\n"
                             + format_cart_receipt(current_cart, session.address_label or "Saved Address",
                                                   allow_checkout_prompt=False),
                        conversation_state="NEEDS_DECISION",
                    )
            receipt = (
                format_cart_receipt(current_cart, session.address_label or "Saved Address",
                                    allow_checkout_prompt=False)
                if current_cart else "I couldn't read the current Swiggy basket."
            )
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="The Swiggy cart changed outside this chat. Reply *use changes* to include it, "
                     "or tell me how you want to restore the basket.\n\n" + receipt,
                conversation_state="NEEDS_DECISION",
            )

        # Fast-path 2: Hesitation guard when active basket exists
        if norm_text in _HESITATION_PHRASES and current_cart and current_cart.items:
            loc = self._customer_address_label.get(customer_id) or "Home"
            receipt = format_cart_receipt(current_cart, delivery_location=loc)
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=(
                    "No problem, I've kept your basket on hold! 🛒\n\n"
                    "Your groceries are still saved. Whenever you're ready, let me know if you want to add/remove items, switch delivery address, or clear your basket.\n\n"
                    f"{receipt}"
                ),
                interactive_actions=[
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                    InteractiveAction(action_type="button", id="start_fresh", title="Clear Cart"),
                ],
                requires_confirmation=True,
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )

        # Inactivity check (idle > 30 mins)
        current_time = time.time()
        last_seen = self._last_interaction_time.get(customer_id)
        self._last_interaction_time[customer_id] = current_time
        if last_seen is not None and (current_time - last_seen) > 1800:
            self._order_address_confirmed.pop(customer_id, None)
            self._awaiting_address_choice.pop(customer_id, None)
            self._customer_address.pop(customer_id, None)
            if not current_cart or not current_cart.items:
                history = []
                self._history[customer_id] = history

        # Resolve pending upfront address disambiguation if awaiting user's choice
        if customer_id in self._awaiting_address_choice:
            pending_addrs = self._awaiting_address_choice[customer_id]
            chosen_addr: Optional[dict[str, Any]] = None

            if message.interactive_id and message.interactive_id.startswith("addr_choice_"):
                choice_code = message.interactive_id.removeprefix("addr_choice_")
                chosen_addr = next((a for a in pending_addrs if a.get("_choice_code") == choice_code), None)
            else:
                matches = [a for a in pending_addrs if norm_text in {
                    str(a.get("_choice_code", "")).casefold(),
                    str(a.get("label", "")).casefold(),
                    str(a.get("clean_address", "")).casefold(),
                }]
                if len(matches) == 1:
                    chosen_addr = matches[0]

            if not chosen_addr:
                return self._address_choice_response(message, pending_addrs)

            if chosen_addr:
                self._awaiting_address_choice.pop(customer_id, None)
                address_id = chosen_addr["address_id"]
                self._customer_address[customer_id] = address_id
                self._customer_address_label[customer_id] = (
                    chosen_addr.get("clean_address") or chosen_addr.get("street") or chosen_addr.get("label") or "Home"
                )
                self._order_address_confirmed[customer_id] = True
                incoming_text = (
                    f"Use delivery address: {self._customer_address_label[customer_id]} (ID: {address_id}) "
                    f"and proceed immediately with my grocery order from the previous message."
                )

        # Detect address selection from text or context
        address_id = self._customer_address.get(customer_id)
        if not address_id:
            try:
                addr_res = await self.tools.get_saved_addresses(customer_id)
                if addr_res.get("error") == "AUTH_EXPIRED":
                    return await self._auth_expired_response(message)
                if addr_res.get("success") and addr_res.get("addresses"):
                    addresses = addr_res["addresses"]
                    # Check if user's initial message already names one of the addresses
                    explicit_matches = [a for a in addresses if a.get("label") and re.search(
                        rf"\b{re.escape(str(a['label']).casefold())}\b", norm_text
                    )]
                    explicit_match = explicit_matches[0] if len(explicit_matches) == 1 else None

                    if explicit_match:
                        address_id = explicit_match["address_id"]
                        self._customer_address[customer_id] = address_id
                        self._customer_address_label[customer_id] = (
                            explicit_match.get("clean_address") or explicit_match.get("label") or "Home"
                        )
                        self._order_address_confirmed[customer_id] = True
                    elif (
                        len(addresses) > 1
                        and not (current_cart and current_cart.items)
                        and not any(k in norm_text for k in ("address", "saved address", "track", "status"))
                    ):
                        # Upfront multi-address disambiguation (Option B): save Turn 1 grocery intent & ask address
                        history.append({"role": "user", "parts": [{"text": incoming_text}], "recorded_at": time.time()})
                        choices = [{**a, "_choice_code": secrets.token_hex(3)} for a in addresses]
                        self._awaiting_address_choice[customer_id] = choices
                        response = self._address_choice_response(message, choices)
                        history.append({"role": "model", "parts": [{"text": response.text}], "recorded_at": time.time()})
                        return response
                    else:
                        default_addr = next((a for a in addresses if a.get("is_default")), addresses[0])
                        address_id = default_addr["address_id"]
                        self._customer_address[customer_id] = address_id
                        self._customer_address_label[customer_id] = (
                            default_addr.get("clean_address") or default_addr.get("label") or "Home"
                        )
                        self._order_address_confirmed[customer_id] = True
            except Exception:
                pass

        # Append user message
        history.append({
            "role": "user",
            "parts": [{"text": incoming_text}],
            "recorded_at": time.time(),
        })

        # Bounded ReAct loop (up to 8 function call steps)
        max_iterations = 8
        final_text = ""
        actions: list[InteractiveAction] = []
        checkout_executed = False
        checkout_result: dict[str, Any] | None = None
        last_cart_receipt: str | None = None
        last_cart_total: float | None = None
        addr_lbl = self._customer_address_label.get(customer_id)
        address_changed = False
        step_limit_reached = False

        for step_idx in range(1, max_iterations + 1):
            response_data = await self._call_llm(
                history,
                address_id=address_id,
                address_label=addr_lbl,
                cart=current_cart,
                fast_fail_on_rate_limit=bool(last_cart_receipt or checkout_executed),
            )
            if not response_data:
                if last_cart_receipt or checkout_executed:
                    final_text = ""
                else:
                    final_text = "I'm having a brief connection hiccup. Please try again in a moment."
                break

            candidates = response_data.get("candidates", [])
            if not candidates:
                if last_cart_receipt or checkout_executed:
                    final_text = ""
                else:
                    final_text = "I couldn't process that request right now. Please tell me what you'd like to do."
                break

            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Check if model invoked function calls
            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            # If no function call, we have the final assistant message
            if not function_calls:
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                final_text = "\n".join(t.strip() for t in text_parts if t.strip())
                # Append assistant response to history
                history.append({
                    "role": "model",
                    "parts": parts,
                    "recorded_at": time.time(),
                })
                break

            # Append model's thought / function calls to history
            history.append({
                "role": "model",
                "parts": parts,
                "recorded_at": time.time(),
            })

            # Execute function calls concurrently and collect responses
            async def _execute_single_call(call: dict[str, Any]) -> tuple[dict[str, Any], bool, bool, dict[str, Any] | None]:
                fn_name = call.get("name")
                fn_args = call.get("args", {})
                call_id = call.get("id")

                if not isinstance(fn_args, dict):
                    tool_result = {"success": False, "error": "INVALID_TOOL_ARGUMENTS"}
                else:
                    # Inject default address_id if omitted by the model
                    if "address_id" in fn_args and not fn_args["address_id"] and address_id:
                        fn_args["address_id"] = address_id

                    tool_result = await self._execute_tool(
                        fn_name,
                        fn_args,
                        customer_id=customer_id,
                        address_id=address_id,
                        user_confirmed=user_confirmed,
                    )

                is_checkout = (fn_name == "checkout")
                is_auth_failed = isinstance(tool_result, dict) and tool_result.get("error") == "AUTH_EXPIRED"

                tool_response_part = {
                    "functionResponse": {
                        "name": fn_name,
                        "response": {
                            "name": fn_name,
                            "content": tool_result,
                        },
                    }
                }
                if call_id:
                    tool_response_part["functionResponse"]["id"] = call_id

                return tool_response_part, is_auth_failed, is_checkout, (tool_result if is_checkout else None)

            executed_calls = await execute_tool_calls(function_calls, _execute_single_call)
            tool_responses = [ec[0] for ec in executed_calls]
            auth_failed = any(ec[1] for ec in executed_calls)
            for ec in executed_calls:
                resp_part = ec[0].get("functionResponse", {})
                fn_call_name = resp_part.get("name")
                fn_content = resp_part.get("response", {}).get("content", {})
                if fn_call_name == "select_delivery_address":
                    address_changed = True
                    if isinstance(fn_content, dict) and fn_content.get("success"):
                        address_id = fn_content.get("address_id") or address_id
                        addr_lbl = self._customer_address_label.get(customer_id) or addr_lbl
                if isinstance(fn_content, dict):
                    if fn_content.get("formatted_receipt"):
                        last_cart_receipt = fn_content["formatted_receipt"]
                    if fn_content.get("grand_total") is not None:
                        last_cart_total = float(fn_content["grand_total"])
                if ec[2]:
                    checkout_executed = True
                    checkout_result = ec[3]

            if any(ec[0].get("functionResponse", {}).get("name") in ("update_cart", "select_delivery_address", "clear_cart") for ec in executed_calls):
                try:
                    current_cart = await self.commerce.get_cart()
                except Exception:
                    pass

            if auth_failed:
                return await self._auth_expired_response(message)

            # Send tool responses back to model in the next turn
            history.append({
                "role": "user",
                "parts": tool_responses,
                "recorded_at": time.time(),
            })
            if step_idx == max_iterations:
                step_limit_reached = True

        out_order_id: str | None = None
        out_order_total: float | None = None
        out_bridge_url: str | None = None
        conv_state = "READY"

        if checkout_executed and checkout_result:
            if not checkout_result.get("success"):
                if checkout_result.get("error") == "CONFIRMATION_REQUIRED":
                    conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
                    actions = [
                        InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                        InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                    ]
                    receipt_str = last_cart_receipt or (format_cart_receipt(current_cart, addr_lbl or "Home") if current_cart else "")
                    final_text = (
                        f"{receipt_str}\n\n"
                        f"👉 Reply *Confirm* to place order, or let me know if you'd like to change anything!"
                    ).strip()
                elif (checkout_result.get("error") in ("ORDER_STATE_UNKNOWN", "ATTEMPT_UNRESOLVED")
                      or checkout_result.get("status") == "ORDER_STATE_UNKNOWN"):
                    conv_state = "RECOVERING"
                    final_text = (
                        "I couldn't verify whether checkout completed. "
                        "Please check the order status in Swiggy or contact support before trying again. "
                        "Further checkout is on hold until this is resolved."
                    )
                else:
                    error_msg = checkout_result.get("error") or checkout_result.get("message") or "Provider checkout error"
                    if settings.CHECKOUT_MODE == "live":
                        final_text = (
                            f"Checkout could not be completed or verified: {error_msg}. "
                            "Please check the Swiggy order status before trying again."
                        )
                    else:
                        disclaimer = "Your order has NOT been placed and your account has not been charged."
                        if _claims_order_success(final_text):
                            logger.warning(
                                "Fail-closed guard triggered: LLM falsely claimed order success on failed checkout (%s). Overriding response.",
                                error_msg,
                            )
                            final_text = (
                                f"I could not complete your order: {error_msg}. "
                                f"{disclaimer} "
                                "Please check your basket and try again."
                            )
                        elif not _explains_failure(
                            final_text, checkout_result.get("error"), checkout_result.get("message")
                        ):
                            logger.warning(
                                "Fail-closed guard triggered: LLM failed to explain failure (%s). Overriding response.",
                                error_msg,
                            )
                            final_text = (
                                f"I could not complete your order: {error_msg}. "
                                f"{disclaimer} "
                                "Please check your basket and try again."
                            )
                        elif disclaimer not in final_text:
                            final_text = f"{final_text.rstrip()}\n\n{disclaimer}"
                    conv_state = "FAILED"
            else:
                out_order_id = checkout_result.get("order_id")
                out_order_total = checkout_result.get("grand_total")
                out_bridge_url = checkout_result.get("bridge_url")
                upi_url = checkout_result.get("upi_intent_url")
                status = checkout_result.get("status")

                if status in ("REVIEW_COMPLETE", "REVIEW_SIMULATED") or checkout_result.get("is_simulated"):
                    conv_state = "REVIEW_COMPLETE"
                    out_order_id = None
                    out_bridge_url = None
                    final_text = "Review complete. No real order was placed and no payment was taken."
                elif status == "PARTIAL_ORDER":
                    conv_state = "NEEDS_DECISION"
                    final_text = (
                        f"Swiggy reported a partial order: {checkout_result.get('success_count', 0)} "
                        f"placed and {checkout_result.get('failure_count', 0)} failed. "
                        "Please check the order details before taking another action."
                    )
                elif status == "PAYMENT_CONFIRMED":
                    conv_state = "RECOVERING"
                    final_text = (
                        "Swiggy confirmed payment, but I couldn't verify that every order was placed. "
                        "Please check the order details in Swiggy. Further checkout is on hold."
                    )
                elif status == "PAYMENT_PENDING":
                    conv_state = "AWAITING_PAYMENT"
                    self._order_address_confirmed.pop(customer_id, None)
                    self._customer_address.pop(customer_id, None)
                    self._customer_address_label.pop(customer_id, None)
                    pay_link = out_bridge_url or upi_url
                    link_present = False
                    if out_bridge_url and out_bridge_url in final_text:
                        link_present = True
                    if upi_url and upi_url in final_text:
                        link_present = True

                    if _claims_order_success(final_text) or not final_text.strip():
                        logger.warning(
                            "PAYMENT_PENDING guard triggered: LLM claimed premature order placement or empty response. Overriding response."
                        )
                        if pay_link:
                            final_text = f"Your order is ready! Please complete payment to place your order: {pay_link}"
                        else:
                            final_text = "Your order is ready! Please complete payment in your Swiggy app to place your order."
                    else:
                        if pay_link and not link_present:
                            final_text += f"\n\n👉 Complete payment to place your order: {pay_link}"
                        elif not pay_link and not link_present:
                            final_text += "\n\nPlease complete payment in your Swiggy app to finalize your order."

                    if out_order_id:
                        asyncio.create_task(
                            self._poll_payment_status(
                                order_id=out_order_id,
                                recipient_id=message.sender_id,
                                channel=message.channel,
                                customer_id=customer_id,
                            )
                        )
                elif status == "ORDER_PLACED":
                    conv_state = "ORDER_PLACED"
                    self._order_address_confirmed.pop(customer_id, None)
                    self._customer_address.pop(customer_id, None)
                    self._customer_address_label.pop(customer_id, None)
                else:
                    conv_state = "READY"
        else:
            # Post-process: Deterministically enforce exact formatted_receipt and interactive buttons
            if step_limit_reached and not final_text.strip():
                receipt_str = last_cart_receipt or (format_cart_receipt(current_cart, addr_lbl or "Home") if current_cart and current_cart.items else "")
                logger.warning("ReAct step limit reached (%d steps) for customer=%s", max_iterations, customer_id)
                if receipt_str:
                    final_text = (
                        "I've added the available items to your basket, but reached the maximum processing steps for this turn before completing all remaining searches.\n\n"
                        f"{receipt_str}\n\n"
                        "👉 Reply to continue resolving the remaining items before basket approval."
                    )
                else:
                    final_text = (
                        "I reached the maximum processing steps for this request. "
                        "Please tell me which specific item you'd like me to add or search next!"
                    )
                actions = [
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                    InteractiveAction(action_type="button", id="start_fresh", title="Clear Cart"),
                ]
                conv_state = "NEEDS_DECISION"
            elif last_cart_receipt:
                amnesiac_phrases = (
                    "what would you like to order",
                    "what can i get for you",
                    "what do you want to order",
                    "how can i help with your groceries",
                    "what groceries",
                    "what would you like",
                )
                is_amnesiac = any(p in final_text.casefold() for p in amnesiac_phrases)
                if address_changed and is_amnesiac:
                    logger.info(
                        "Deterministic address-change guard triggered: overriding amnesiac text for %s",
                        addr_lbl,
                    )
                    final_text = (
                        f"I've updated your delivery address to *{addr_lbl}*! 📍\n\n"
                        f"{last_cart_receipt}"
                    )
                elif last_cart_receipt not in final_text:
                    # Replace any LLM-retyped receipt block or append authoritative receipt
                    basket_match = re.search(r"🛒\s*\*?Your Basket.*", final_text, flags=re.DOTALL | re.IGNORECASE)
                    if basket_match:
                        intro = final_text[: basket_match.start()].strip()
                        final_text = f"{intro}\n\n{last_cart_receipt}" if intro else last_cart_receipt
                    elif not final_text.strip() or final_text.strip() == "How can I help with your groceries today?":
                        if address_changed:
                            final_text = (
                                f"I've updated your delivery address to *{addr_lbl}*! 📍\n\n"
                                f"{last_cart_receipt}"
                            )
                        else:
                            final_text = last_cart_receipt
                    else:
                        final_text = f"{final_text.strip()}\n\n{last_cart_receipt}"

                actions = [
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ]
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
            elif any(
                phrase in final_text.casefold()
                for phrase in (
                    "place this order",
                    "confirm order",
                    "shall i place",
                    "would you like me to place",
                    "reply *confirm*",
                    "reply confirm",
                    "place order",
                    "confirm to place order",
                )
            ):
                actions = [
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ]
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

        if (not final_text.strip() or final_text.strip() == "How can I help with your groceries today?") and last_cart_receipt:
            final_text = last_cart_receipt
        if out_order_total is None and last_cart_total is not None:
            out_order_total = last_cart_total

        if any(action.id == "confirm_order" for action in actions):
            unresolved = self.get_session(customer_id).unresolved_items
            if unresolved:
                self.get_session(customer_id).pending_approval = None
                actions = [action for action in actions if action.id != "confirm_order"]
                conv_state = "NEEDS_DECISION"
                final_text = (
                    "Swiggy changed or omitted a requested item. Please resolve these before approval: "
                    + ", ".join(str(item.get("spin_id")) for item in unresolved)
                )
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text=final_text, interactive_actions=actions, conversation_state=conv_state,
                )
            try:
                reviewed_cart = await self.commerce.get_cart()
            except Exception:
                reviewed_cart = None
            approved_address = self._customer_address.get(customer_id) or (
                reviewed_cart.address_id if reviewed_cart else None
            )
            if not reviewed_cart or not approved_address or not self._record_pending_approval(
                customer_id, reviewed_cart, approved_address
            ):
                self.get_session(customer_id).pending_approval = None
                actions = [action for action in actions if action.id != "confirm_order"]
                conv_state = "NEEDS_DECISION"
                final_text = "I couldn't verify the complete basket and delivery address. Please review them before ordering."
            else:
                final_text = format_cart_receipt(
                    reviewed_cart, self._customer_address_label.get(customer_id) or approved_address
                )
                out_order_total = reviewed_cart.grand_total
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
        elif not checkout_executed:
            self.get_session(customer_id).pending_approval = None

        self._prune_history(customer_id)

        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=final_text or "How can I help with your groceries today?",
            interactive_actions=actions,
            requires_confirmation=bool(actions),
            conversation_state=conv_state,
            order_id=out_order_id,
            order_total=out_order_total,
            payment_bridge_url=out_bridge_url,
        )

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        *,
        customer_id: str,
        address_id: Optional[str],
        user_confirmed: Optional[bool] = None,
    ) -> Any:
        """Dispatch a single function call to SwiggyAgentTools."""
        logger.info("Executing agent tool call: %s", name)
        if name == "get_saved_addresses":
            return await self.tools.get_saved_addresses(customer_id)
        elif name == "select_delivery_address":
            self.get_session(customer_id).pending_approval = None
            res = await self.tools.select_delivery_address(customer_id, args.get("address_id", ""))
            if res.get("success") and res.get("address_id"):
                self._customer_address[customer_id] = res["address_id"]
                self._customer_address_label[customer_id] = (
                    res.get("clean_address") or res.get("label") or "Selected Address"
                )
                self._order_address_confirmed[customer_id] = True
            return res
        elif name == "get_go_to_items":
            addr = args.get("address_id") or address_id
            return await self.tools.get_go_to_items(address_id=addr)
        elif name == "search_products":
            addr = args.get("address_id") or address_id
            return await self.tools.search_products(args.get("query", ""), address_id=addr)
        elif name == "get_cart":
            loc = self._customer_address_label.get(customer_id, "Home")
            return await self.tools.get_cart(delivery_location=loc)
        elif name == "update_cart":
            session = self.get_session(customer_id)
            session.pending_approval = None
            addr = args.get("address_id") or address_id
            loc = self._customer_address_label.get(customer_id, "Home")
            result = await self.tools.update_cart(
                args.get("items", []), address_id=addr or "", delivery_location=loc
            )
            unresolved_by_spin = {
                item["spin_id"]: item for item in session.unresolved_items if item.get("spin_id")
            }
            proposed = args.get("items", [])
            if isinstance(proposed, list):
                for item in proposed:
                    if isinstance(item, dict) and item.get("spin_id") and result.get("success"):
                        unresolved_by_spin.pop(str(item["spin_id"]), None)
            for item in result.get("unresolved_items", []):
                unresolved_by_spin[item["spin_id"]] = item
            session.unresolved_items = list(unresolved_by_spin.values())
            if result.get("verified_fingerprint"):
                session.known_cart_fingerprint = result["verified_fingerprint"]
            return result
        elif name == "clear_cart":
            result = await self.tools.clear_cart()
            if result.get("success"):
                try:
                    cart = await self.commerce.get_cart()
                except Exception:
                    cart = None
                if cart is None or cart.items:
                    return {"success": False, "error": "CLEAR_UNVERIFIED"}
                self.get_session(customer_id).unresolved_items.clear()
                self.get_session(customer_id).known_cart_fingerprint = None
                self.get_session(customer_id).external_cart_pending = False
                self.reset_customer_order_address(customer_id)
            return result
        elif name == "checkout":
            sess = self.get_session(customer_id)
            if sess.unresolved_items:
                return {"success": False, "error": "ITEMS_UNRESOLVED", "retryable": False,
                        "message": "Please resolve each missing or reduced requested item before checkout."}
            if sess.external_cart_pending:
                return {"success": False, "error": "EXTERNAL_CART_UNREVIEWED", "retryable": False}
            approval = sess.pending_approval
            if not user_confirmed or not approval or approval.expires_at <= time.time():
                return {"success": False, "error": "CONFIRMATION_REQUIRED", "retryable": False,
                        "message": "Please review the current basket and confirm it before checkout."}
            checkout_address = args.get("address_id", "") or address_id or ""
            try:
                cart = await self.commerce.get_cart(args.get("cart_id", ""))
            except Exception:
                return {"success": False, "error": "CART_UNAVAILABLE", "retryable": False,
                        "message": "I couldn't verify your basket. Please review it again."}
            if cart_fingerprint(cart, checkout_address) != approval.fingerprint:
                sess.pending_approval = None
                return {"success": False, "error": "CART_CHANGED", "retryable": False,
                        "message": "Your basket or total changed. Please review it again."}
            attempt_id = None
            if settings.CHECKOUT_MODE == "live":
                if self.attempt_store is None:
                    return {"success": False, "error": "DURABLE_ATTEMPT_REQUIRED", "retryable": False,
                            "message": "Live checkout is unavailable until durable attempt tracking is ready."}
                try:
                    attempt_id = await self.attempt_store.start(
                        customer_id, cart.cart_id or "", checkout_address,
                        approval.fingerprint, cart.grand_total,
                    )
                except Exception:
                    logger.exception("Could not reserve durable checkout attempt.")
                    return {"success": False, "error": "DURABLE_ATTEMPT_REQUIRED", "retryable": False}
                if attempt_id is None:
                    return {"success": False, "error": "ATTEMPT_UNRESOLVED", "retryable": False,
                            "message": "An earlier checkout or payment is unresolved. Further checkout is on hold."}
            sess.pending_approval = None
            try:
                result = await self.tools.checkout(
                    cart_id=args.get("cart_id", ""),
                    address_id=checkout_address,
                    payment_method=args.get("payment_method", "UPI"),
                    payment_option_kind=args.get("payment_option_kind", "qr"),
                    is_user_confirmed=True,
                    budget_inr=sess.budget_inr,
                    expected_cart_fingerprint=approval.fingerprint,
                )
                if attempt_id is not None:
                    await self.attempt_store.finish(attempt_id, result)
                return result
            except Exception:
                logger.exception("Checkout outcome could not be verified.")
                return {"success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False}
        elif name == "track_order":
            return await self.tools.track_order(args.get("order_id", ""))
        return {"error": f"Unknown tool: {name}"}

    def _convert_to_openai_messages(
        self, contents: list[dict[str, Any]], system_text: str
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_text}]
        for entry in contents:
            role = entry.get("role")
            parts = entry.get("parts", [])
            if role == "user":
                fn_responses = [p["functionResponse"] for p in parts if "functionResponse" in p]
                if fn_responses:
                    for fn_resp in fn_responses:
                        call_id = fn_resp.get("id") or f"call_{fn_resp.get('name')}"
                        resp_data = fn_resp.get("response", {})
                        content_str = json.dumps(resp_data) if isinstance(resp_data, (dict, list)) else str(resp_data)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": content_str,
                        })
                else:
                    user_text = "\n".join(p.get("text", "") for p in parts if "text" in p)
                    if user_text:
                        messages.append({"role": "user", "content": user_text})
            elif role in ("model", "assistant"):
                fn_calls = [p["functionCall"] for p in parts if "functionCall" in p]
                if fn_calls:
                    tool_calls = []
                    for i, fn_call in enumerate(fn_calls):
                        call_id = fn_call.get("id") or f"call_{i}"
                        fn_name = fn_call.get("name")
                        fn_args = fn_call.get("args", {})
                        tool_calls.append({
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": json.dumps(fn_args) if isinstance(fn_args, dict) else str(fn_args),
                            },
                        })
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    })
                else:
                    asst_text = "\n".join(p.get("text", "") for p in parts if "text" in p)
                    if asst_text:
                        messages.append({"role": "assistant", "content": asst_text})
        return messages

    async def _call_llm(
        self,
        contents: list[dict[str, Any]],
        *,
        address_id: Optional[str] = None,
        address_label: Optional[str] = None,
        cart: Optional[CommerceCart] = None,
        fast_fail_on_rate_limit: bool = False,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        """Perform request to Groq Cloud primary with OpenRouter automatic fallback."""
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_call_time
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)
        self._last_call_time = asyncio.get_running_loop().time()

        system_text = build_system_instruction(
            address_id=address_id,
            address_label=address_label,
            cart=cart,
        )

        providers: list[dict[str, Any]] = []
        if self.groq_api_key:
            providers.append({
                "name": "groq",
                "url": "https://api.groq.com/openai/v1/chat/completions",
                "model": self.groq_model,
                "headers": {
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "GrocerApp/1.0 (Windows NT 10.0; Win64; x64)",
                },
                "format": "openai",
            })
        if self.openrouter_api_key:
            providers.append({
                "name": "openrouter",
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "model": self.openrouter_model,
                "headers": {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://grocerr.vercel.app",
                    "X-Title": "Grocer",
                },
                "format": "openai",
            })
        if not providers:
            self.last_llm_error = "NO_PROVIDER_CONFIGURED"
            return None
        providers.sort(key=lambda provider: provider["name"] != settings.AI_PROVIDER)
        client = await self._get_client()

        openai_messages = self._convert_to_openai_messages(contents, system_text)

        max_retries = 1 if fast_fail_on_rate_limit else len(providers) * 2
        for attempt in range(max_retries):
            provider = providers[min(attempt, len(providers) - 1)]
            p_url = provider["url"]
            p_headers = provider.get("headers", {})
            p_model = provider.get("model")

            payload = {
                "model": p_model,
                "messages": openai_messages,
                "tools": OPENAI_TOOL_DECLARATIONS,
                "tool_choice": "auto",
                "temperature": 0.2,
            }

            try:
                resp = await client.post(p_url, json=payload, headers=p_headers)
                if resp.status_code in (429, 503, 404):
                    if fast_fail_on_rate_limit:
                        logger.info("Post-tool call encountered %d; fast-returning receipt result.", resp.status_code)
                        return None
                    if attempt + 1 < len(providers):
                        next_provider = providers[attempt + 1]
                        logger.warning(
                            "Provider %s (%s) returned %d; pivoting immediately to %s (%s)...",
                            provider["name"], p_model, resp.status_code,
                            next_provider["name"], next_provider.get("model"),
                        )
                        await asyncio.sleep(0.2)
                        continue
                    retry_after = resp.headers.get("retry-after")
                    sleep_time = float(retry_after) if retry_after else 2.0
                    logger.warning(
                        "HTTP %d on %s (%s). Retrying in %.1fs...",
                        resp.status_code, provider["name"], p_model, sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                if resp.status_code == 400 and len(contents) > 1:
                    logger.warning("HTTP 400 on multi-turn history. Retrying with a text-only copy.")
                    salvaged = [
                        {"role": entry.get("role"), "parts": [
                            part for part in entry.get("parts", []) if "text" in part
                        ]}
                        for entry in contents
                    ]
                    salvaged = [entry for entry in salvaged if entry["parts"]]
                    openai_messages = self._convert_to_openai_messages(salvaged, system_text)
                    payload["messages"] = openai_messages
                    resp = await client.post(p_url, json=payload, headers=p_headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        self.last_llm_error = None
                        if "candidates" in data:
                            return data
                        return self._normalize_openai_response(data)

                if resp.status_code != 200:
                    err_text = f"HTTP {resp.status_code}: {resp.text[:300]}"
                    logger.error("LLM Provider returned %s", err_text)
                    self.last_llm_error = err_text
                    if attempt + 1 < len(providers):
                        await asyncio.sleep(0.2)
                        continue
                    return None

                data = resp.json()
                self.last_llm_error = None
                if "candidates" in data:
                    return data
                return self._normalize_openai_response(data)

            except Exception as exc:
                err_text = f"Exception: {type(exc).__name__} - {exc}"
                logger.error("LLM request failed on attempt %d: %s", attempt + 1, exc)
                self.last_llm_error = err_text
                if attempt + 1 < len(providers):
                    await asyncio.sleep(0.2)
                    continue
                return None
        return None

    def _normalize_openai_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI/Groq response format into normalized parts candidate."""
        choices = data.get("choices", [])
        if not choices:
            return {"candidates": []}
        msg = choices[0].get("message", {})
        tool_calls = msg.get("tool_calls", [])
        parts: list[dict[str, Any]] = []
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except (ValueError, TypeError):
                    args = None
                parts.append({
                    "functionCall": {
                        "name": fn_name,
                        "args": args,
                        "id": tc.get("id"),
                    }
                })
        else:
            text = msg.get("content") or ""
            parts.append({"text": text})
        return {"candidates": [{"content": {"parts": parts}}]}
