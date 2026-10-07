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
from backend.agent.budget import extract_total_budget, extract_ingredient_budget
from backend.agent.product_policy import is_symptom_suggestion_request
from backend.agent.tool_scheduler import execute_tool_calls
from backend.agent.tools import (
    SwiggyAgentTools,
    format_cart_receipt,
)
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart
from backend.integrations.commerce.exceptions import ProviderAuthError, ProviderRateLimitedError
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
    is_hesitation,
    missing_recipe_staples,
    reconcile_explicit_items,
)
from backend.agent.prompts import (  # noqa: E402, F401
    _SYSTEM_PROMPT,
    _SHOPPING_PLAN_PROMPT,
    build_system_instruction,
)

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_ORDINALS = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
    "sixth": 5, "6th": 5,
}


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
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        gemini_fallback_model: Optional[str] = None,
        timeout: float = 25.0,
        attempt_store: Any | None = None,
        state_store: Any | None = None,
        replenishment_store: Any | None = None,
    ) -> None:
        self.commerce = commerce
        self.tools = SwiggyAgentTools(commerce)
        self.attempt_store = attempt_store
        self.state_store = state_store
        self.replenishment_store = replenishment_store
        self._gemini_explicitly_passed = gemini_api_key is not None
        if gemini_api_key is not None:
            self.gemini_api_key = gemini_api_key
        elif groq_api_key is not None or openrouter_api_key is not None:
            self.gemini_api_key = None
        else:
            self.gemini_api_key = getattr(settings, "GEMINI_API_KEY", None)
        self.gemini_model = gemini_model or getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash")
        self.gemini_fallback_model = gemini_fallback_model or getattr(settings, "GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
        self.groq_api_key = groq_api_key or settings.GROQ_API_KEY
        self.groq_model = groq_model or settings.GROQ_MODEL
        self.openrouter_api_key = openrouter_api_key or settings.OPENROUTER_API_KEY
        self.openrouter_model = openrouter_model or settings.OPENROUTER_MODEL
        self.api_key = api_key or self.gemini_api_key or self.groq_api_key or self.openrouter_api_key
        self.model = model or self.gemini_model or self.groq_model or self.openrouter_model
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
            ingredient_budget_inr=state.get("ingredient_budget_inr"),
            ingredient_extras_text=state.get("ingredient_extras_text"),
            ingredient_spin_ids=state.get("ingredient_spin_ids") or [],
            pending_approval=PendingApproval(**approval) if approval else None,
            unresolved_items=state.get("unresolved_items") or [],
            budget_blocked_items=state.get("budget_blocked_items") or [],
            known_cart_fingerprint=state.get("known_cart_fingerprint"),
            external_cart_pending=bool(state.get("external_cart_pending", False)),
            pending_request_text=state.get("pending_request_text"),
            pending_variant_selection=state.get("pending_variant_selection"),
            selected_payment_id=state.get("selected_payment_id"),
            selected_payment_kind=state.get("selected_payment_kind"),
            selected_payment_method=state.get("selected_payment_method"),
            selected_payment_label=state.get("selected_payment_label"),
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
            "ingredient_budget_inr": session.ingredient_budget_inr,
            "ingredient_extras_text": session.ingredient_extras_text,
            "ingredient_spin_ids": session.ingredient_spin_ids,
            "pending_approval": (
                {"fingerprint": approval.fingerprint, "expires_at": approval.expires_at}
                if approval else None
            ),
            "unresolved_items": session.unresolved_items,
            "budget_blocked_items": session.budget_blocked_items,
            "known_cart_fingerprint": session.known_cart_fingerprint,
            "external_cart_pending": session.external_cart_pending,
            "pending_request_text": session.pending_request_text,
            "pending_variant_selection": session.pending_variant_selection,
            "selected_payment_id": session.selected_payment_id,
            "selected_payment_kind": session.selected_payment_kind,
            "selected_payment_method": session.selected_payment_method,
            "selected_payment_label": session.selected_payment_label,
        }

    def _address_choice_response(
        self, message: NormalizedIncomingMessage, addresses: list[dict[str, Any]]
    ) -> NormalizedOutgoingResponse:
        lines = []
        for index, address in enumerate(addresses, 1):
            lbl = address.get("label") or f"Address {index}"
            details = address.get("clean_address") or address.get("street") or lbl
            lines.append(f"*{index}. {lbl}* — {details}")
        prompt = "📍 *Which address should I use?*\n\n" + "\n".join(lines)
        prompt += "\n\nReply with the number (e.g. 1), label (e.g. Home), or tap a button."
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=prompt,
            interactive_actions=[
                InteractiveAction(
                    action_type="button", id=f"addr_choice_{address.get('_choice_code') or address.get('address_id')}",
                    title=f"{index}. {str(address.get('label') or f'Address {index}')}"[:20],
                )
                for index, address in enumerate(addresses[:3], 1)
            ],
            conversation_state="NEEDS_DECISION",
        )

    @staticmethod
    def _cart_proposal_state(cart: CommerceCart | None) -> dict[str, Any] | None:
        if cart is None:
            return None
        return {
            "cart_id": cart.cart_id, "address_id": cart.address_id,
            "grand_total": cart.grand_total,
            "items": sorted(
                ([item.spin_id, item.sku_id, item.quantity] for item in cart.items),
                key=lambda entry: entry[0],
            ),
        }

    def _variant_choice_response(
        self, message: NormalizedIncomingMessage, proposal: dict[str, Any],
        prefix: str = "",
    ) -> NormalizedOutgoingResponse:
        lines = [prefix, "Choose the exact products to add:"] if prefix else ["Choose the exact products to add:"]
        for index, group in enumerate(proposal["groups"], 1):
            lines.append(f"\n*{index}. {group['query']} × {group['quantity']}*")
            for option in group["options"]:
                lines.append(
                    f"{option['code']} — {option['name']} ({option['pack_size']}) — ₹{option['price']:g}"
                )
            if group.get("more_available"):
                lines.append("More versions are available. Tell me a brand or pack size if none of these fit.")
        if proposal.get("unavailable_items"):
            lines.append("\nUnavailable: " + ", ".join(proposal["unavailable_items"]))
        if proposal.get("restricted_items"):
            lines.append("\nCannot add medical products here: " + ", ".join(proposal["restricted_items"]))
        examples = " ".join(group["options"][0]["code"] for group in proposal["groups"])
        lines.append(f"\nReply with one code for each item, for example: {examples}. Nothing has been added yet.")
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id, channel=message.channel,
            text="\n".join(part for part in lines if part), conversation_state="NEEDS_DECISION",
        )

    async def _handle_variant_choice(
        self, message: NormalizedIncomingMessage, customer_id: str,
        current_cart: CommerceCart | None,
    ) -> NormalizedOutgoingResponse:
        session = self.get_session(customer_id)
        proposal = session.pending_variant_selection
        assert proposal is not None
        if message.text.casefold().strip() in {"cancel", "never mind", "start over"}:
            session.pending_variant_selection = None
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="Okay, I cancelled those product choices. Your basket was not changed.",
                conversation_state="READY",
            )
        if (current_cart is None or self._cart_proposal_state(current_cart) != proposal.get("cart_state")
                or self._customer_address.get(customer_id) != proposal.get("address_id")):
            session.pending_variant_selection = None
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="Your Swiggy basket or address changed. Please tell me what to add again so I can show fresh choices.",
                conversation_state="NEEDS_DECISION",
            )

        codes = re.findall(r"\b\d{1,2}[A-F]\b", message.text.upper())
        selected: list[dict[str, Any]] = []
        for group in proposal["groups"]:
            matches = [option for option in group["options"] if option["code"] in codes]
            if len(matches) != 1:
                return self._variant_choice_response(
                    message, proposal, "Please give one listed code for each item.",
                )
            selected.append({"query": group["query"], "quantity": group["quantity"],
                             "option": matches[0]})
        if len(codes) != len(selected):
            return self._variant_choice_response(message, proposal, "I couldn't match every code to a requested item.")

        fresh = await self.tools.prepare_variant_choices(
            [{"query": group["query"], "quantity": group["quantity"]} for group in proposal["groups"]],
            proposal["address_id"],
        )
        if fresh.get("error") == "AUTH_EXPIRED":
            return await self._auth_expired_response(message)
        if fresh.get("error") == "RATE_LIMITED":
            seconds = fresh.get("retry_after_seconds")
            wait = f"{seconds} seconds" if isinstance(seconds, int) else "a little while"
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text=f"Swiggy is limiting requests. Please wait {wait}, then send the same choice codes. I kept your choices.",
                conversation_state="RECOVERING",
            )
        if not fresh.get("success"):
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="I couldn't recheck those products. Your basket was not changed. Please send the same choice codes again later.",
                conversation_state="RECOVERING",
            )
        fresh_by_query: dict[str, list[dict[str, Any]]] = {}
        for group in fresh["groups"]:
            fresh_by_query.setdefault(group["query"], []).append(group)
        for item in selected:
            option = item["option"]
            matching_groups = fresh_by_query.get(item["query"], [])
            matching_group = matching_groups.pop(0) if matching_groups else {}
            live = next((candidate for candidate in matching_group.get("options", [])
                         if candidate["spin_id"] == option["spin_id"]
                         and candidate["sku_id"] == option["sku_id"]), None)
            if live is None or live["price"] != option["price"]:
                session.pending_variant_selection = {
                    **fresh, "address_id": proposal["address_id"],
                    "cart_state": proposal["cart_state"],
                } if fresh["groups"] else None
                if session.pending_variant_selection:
                    return self._variant_choice_response(
                        message, session.pending_variant_selection,
                        "A product's price or availability changed. Please choose again:",
                    )
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text="Those products are no longer available. Your basket was not changed.",
                    conversation_state="NEEDS_DECISION",
                )
            item["option"] = live

        result = await self.tools.add_selected_variants(
            selected, proposal["address_id"], current_cart, proposal["cart_state"],
            delivery_location=self._customer_address_label.get(customer_id, "Home"),
            budget_cap_inr=session.budget_inr,
            ingredient_budget_inr=session.ingredient_budget_inr,
            ingredient_extras_text=session.ingredient_extras_text or "",
            ingredient_spin_ids=session.ingredient_spin_ids,
        )
        if result.get("error") == "AUTH_EXPIRED":
            return await self._auth_expired_response(message)
        if result.get("error") == "RATE_LIMITED":
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="Swiggy is limiting requests. Please wait and then ask me to show your basket before retrying.",
                conversation_state="RECOVERING",
            )
        if not result.get("success"):
            if result.get("error") in {"CART_WRITE_UNVERIFIED", "BUDGET_ROLLBACK_UNVERIFIED"}:
                session.external_cart_pending = True
                session.pending_approval = None
            if result.get("error") not in {"CART_UNAVAILABLE", "SEARCH_UNAVAILABLE"}:
                session.pending_variant_selection = None
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text=result.get("message") or "I couldn't verify the basket change. Please show your basket before trying again.",
                conversation_state="NEEDS_DECISION",
            )

        session.pending_variant_selection = None
        session.pending_request_text = None
        session.ingredient_spin_ids = result.get("ingredient_spin_ids", session.ingredient_spin_ids)
        session.known_cart_fingerprint = result.get("verified_fingerprint")
        missing = list(dict.fromkeys(
            proposal.get("unavailable_items", []) + proposal.get("restricted_items", [])
            + result.get("budget_blocked_items", [])
        ))
        note = f"I couldn't add: {', '.join(missing)}. Please tell me what to change.\n\n" if missing else ""
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id, channel=message.channel,
            text=note + result["formatted_receipt"],
            conversation_state="NEEDS_DECISION" if missing else "AWAITING_CHECKOUT_CONFIRMATION",
            interactive_actions=[] if missing else [
                InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            ],
            order_total=result["grand_total"],
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
        planning_request_text = incoming_text
        if message.interactive_id:
            if message.interactive_id == "confirm_order":
                incoming_text = "Yes, please confirm and place the order now."
            elif message.interactive_id == "proceed_checkout":
                incoming_text = "Proceed to checkout and review my order."
            elif message.interactive_id == "modify_cart":
                incoming_text = "I would like to change something in my cart."
            elif message.interactive_id in ("start_fresh", "clear_cart"):
                incoming_text = "Please clear my cart and start fresh."

        # Extract explicit spending budget if mentioned by customer
        ingredient_budget = extract_ingredient_budget(incoming_text)
        budget = extract_total_budget(incoming_text) if ingredient_budget is None else None
        if ingredient_budget is not None:
            session.ingredient_budget_inr, session.ingredient_extras_text = ingredient_budget
            session.ingredient_spin_ids.clear()
            session.budget_inr = None
        elif budget is not None:
            session.budget_inr = budget
            session.ingredient_budget_inr = None
            session.ingredient_extras_text = None
            session.ingredient_spin_ids.clear()
            logger.info("Captured customer budget constraint: ₹%.2f for %s", budget, customer_id)

        norm_text = incoming_text.casefold().strip("!.? \t\n")
        if (session.pending_request_text and history
                and history[-1].get("clarification_pending")
                and not message.interactive_id
                and not re.match(r"(?i)^(?:add|buy|get|need|show|clear|cancel|start|remove)\b", norm_text)):
            planning_request_text = (
                f"{session.pending_request_text}\nCustomer clarification: {incoming_text}"
            )

        if self.replenishment_store is not None:
            try:
                reminder_reply = await self.replenishment_store.reply(
                    customer_id, incoming_text, self.commerce,
                )
            except ProviderAuthError:
                return await self._auth_expired_response(message)
            if reminder_reply is not None:
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text=reminder_reply, conversation_state="NEEDS_DECISION",
                )

        if norm_text == "cancel order":
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text=("I haven't cancelled an order. If you mean your current basket, "
                      "reply 'clear cart'. For an order already placed, check its status in Swiggy."),
                conversation_state="NEEDS_DECISION",
            )

        if (norm_text in {"hi", "hello", "hey", "namaste"}
                and not session.pending_variant_selection
                and customer_id not in self._awaiting_address_choice):
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="Hi! Tell me what grocery items you need, or ask to see your basket.",
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
        except ProviderAuthError:
            return await self._auth_expired_response(message)
        except ProviderRateLimitedError as exc:
            wait_text = (f"Please wait {exc.retry_after_seconds} seconds and try again."
                         if exc.retry_after_seconds is not None else "Please wait and try again later.")
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text=f"Swiggy is limiting requests right now. {wait_text}",
                conversation_state="RECOVERING",
            )
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
                session.selected_payment_id = None
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

        cart_read = norm_text in {"cart", "basket"} or bool(re.fullmatch(
            r"(?:(?:please|can you|could you)\s+)?(?:show|view|see|list)(?:\s+me)?\s+"
            r"(?:(?:my|the|your|current)\s+)?(?:cart|basket)(?:\s+(?:right\s+)?now)?"
            r"|what(?:'s| is)\s+in\s+(?:my|the|your)\s+(?:cart|basket)(?:\s+right\s+now)?",
            norm_text,
        ))
        if cart_read:
            if current_cart is None:
                text = "I couldn't read your current basket. Please try again shortly."
                state = "FAILED"
            elif not current_cart.items:
                text = "Your basket is empty. What groceries would you like to add?"
                state = "READY"
            else:
                text = format_cart_receipt(
                    current_cart, session.address_label or "Saved Address",
                    allow_checkout_prompt=False,
                )
                state = "NEEDS_DECISION"
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text=text, conversation_state=state,
            )

        if session.pending_variant_selection:
            ordinal = re.fullmatch(
                r"(?:the\s+)?(first|second|third|fourth|fifth|sixth|[1-6](?:st|nd|rd|th))"
                r"(?:\s+(?:one|option))?",
                norm_text,
            )
            if ordinal:
                groups = session.pending_variant_selection["groups"]
                if len(groups) != 1:
                    return self._variant_choice_response(
                        message, session.pending_variant_selection,
                        "Please name a listed code for each item.",
                    )
                choice_number = {
                    "first": 1, "second": 2, "third": 3, "fourth": 4,
                    "fifth": 5, "sixth": 6,
                }.get(ordinal.group(1), int(ordinal.group(1)[0]) if ordinal.group(1)[0].isdigit() else 0)
                options = groups[0]["options"]
                if choice_number <= len(options):
                    chosen = message.model_copy(update={"text": options[choice_number - 1]["code"]})
                    return await self._handle_variant_choice(chosen, customer_id, current_cart)
                return self._variant_choice_response(
                    message, session.pending_variant_selection,
                    "That option is not listed. Please choose one of these codes.",
                )
            if (re.search(r"\b\d{1,2}[A-F]\b", incoming_text.upper())
                    or norm_text in {"cancel", "never mind", "start over", "try again", "retry"}):
                return await self._handle_variant_choice(message, customer_id, current_cart)
            session.pending_variant_selection = None
            session.pending_request_text = incoming_text
            planning_request_text = incoming_text

        if message.interactive_id and message.interactive_id.startswith("payment_choice:"):
            selected_id = message.interactive_id.removeprefix("payment_choice:")
            approval = session.pending_approval
            approved_address = session.address_id or (current_cart.address_id if current_cart else "") or ""
            if (not approval or approval.expires_at <= time.time() or not current_cart
                    or cart_fingerprint(current_cart, approved_address) != approval.fingerprint):
                session.pending_approval = None
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text="Your basket changed or the review expired. Please review it again before choosing payment.",
                    conversation_state="NEEDS_DECISION",
                )
            try:
                options = await self.commerce.get_payment_options(current_cart.cart_id, approved_address)
            except Exception:
                options = []
            selected = next((option for option in options if option.id == selected_id
                             and option.is_available and (
                                 (option.method == "UPI" and option.kind == "intent")
                                 or option.method in ("Cash", "COD", "SwiggyPay")
                             )), None)
            if selected is None:
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text="That payment option is no longer available. Please ask me to show the current payment options.",
                    conversation_state="NEEDS_DECISION",
                )
            session.selected_payment_id = selected.id
            session.selected_payment_kind = selected.kind
            session.selected_payment_method = selected.method
            session.selected_payment_label = selected.label
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text=(format_cart_receipt(current_cart, session.address_label or approved_address)
                      + f"\n\nPayment: {selected.label}. Do you want to place this order to this address?"),
                interactive_actions=[
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )

        if message.interactive_id == "accept_partial_basket" or norm_text in {
            "keep the partial basket", "keep these items", "accept partial basket",
        }:
            if not session.budget_blocked_items or not current_cart:
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text="I couldn't verify a partial basket to keep. Please ask me to show your cart.",
                    conversation_state="NEEDS_DECISION",
                )
            approved_address = session.address_id or current_cart.address_id or ""
            if not self._record_pending_approval(customer_id, current_cart, approved_address):
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text="I couldn't verify the current basket and delivery address. Please review the basket again.",
                    conversation_state="NEEDS_DECISION",
                )
            session.budget_blocked_items.clear()
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text="Okay, I'll keep only these items. Please review the basket before placing an order.\n\n"
                     + format_cart_receipt(current_cart, session.address_label or "Home"),
                interactive_actions=[
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ],
                conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
                order_total=current_cart.grand_total,
            )

        # Fast-path 2: Hesitation guard when active basket exists
        if is_hesitation(norm_text) and current_cart and current_cart.items:
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
                chosen_addr = next(
                    (a for a in pending_addrs if str(a.get("_choice_code")) == choice_code or str(a.get("address_id")) == choice_code or str(a.get("_choice_index")) == choice_code),
                    None,
                )
            else:
                clean_num = norm_text.split(".")[0].strip() if norm_text and norm_text[0].isdigit() else norm_text
                matches = [a for a in pending_addrs if clean_num in {
                    str(a.get("_choice_index", "")),
                    str(a.get("_choice_code", "")).casefold(),
                    str(a.get("label", "")).casefold(),
                    str(a.get("clean_address", "")).casefold(),
                } or norm_text in {
                    str(a.get("_choice_index", "")),
                    str(a.get("_choice_code", "")).casefold(),
                    str(a.get("label", "")).casefold(),
                    str(a.get("clean_address", "")).casefold(),
                }]
                if len(matches) == 1:
                    chosen_addr = matches[0]

                if not chosen_addr:
                    tokens = [t for t in re.split(r"\W+", norm_text) if len(t) > 2]
                    for token in tokens:
                        token_matches = [
                            a for a in pending_addrs
                            if token in str(a.get("clean_address", "")).casefold()
                            or token in str(a.get("label", "")).casefold()
                        ]
                        if len(token_matches) == 1:
                            chosen_addr = token_matches[0]
                            break

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
                if session.pending_request_text:
                    planning_request_text = session.pending_request_text
                    incoming_text = (
                        f"{session.pending_request_text}\n"
                        f"Use delivery address: {self._customer_address_label[customer_id]} (ID: {address_id})."
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
                        rf"\b(?:deliver(?:y)?\s+to|send\s+to|ship\s+to|use|switch\s+to|change\s+to)"
                        rf"\s+(?:my\s+)?{re.escape(str(a['label']).casefold())}\b"
                        rf"|\b{re.escape(str(a['label']).casefold())}\s+address\b",
                        norm_text,
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
                        session.pending_request_text = incoming_text
                        history.append({"role": "user", "parts": [{"text": incoming_text}], "recorded_at": time.time()})
                        choices = [{**a, "_choice_code": secrets.token_hex(3), "_choice_index": str(idx)} for idx, a in enumerate(addresses, 1)]
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

        if session.pending_request_text and norm_text in {"try again", "retry"}:
            planning_request_text = session.pending_request_text
            incoming_text = (
                f"{session.pending_request_text}\n"
                f"Use delivery address: {self._customer_address_label.get(customer_id, 'selected address')} "
                f"(ID: {address_id})."
            )

        # Append user message
        history.append({
            "role": "user",
            "parts": [{"text": incoming_text}],
            "recorded_at": time.time(),
        })

        # Bounded ReAct loop (capped at 3 steps for sub-2s execution)
        max_iterations = 3
        final_text = ""
        actions: list[InteractiveAction] = []
        checkout_executed = False
        checkout_result: dict[str, Any] | None = None
        last_cart_receipt: str | None = None
        last_cart_total: float | None = None
        addr_lbl = self._customer_address_label.get(customer_id)
        address_changed = False
        step_limit_reached = False
        pending_request_needs_retry = False
        suggestion_only = is_symptom_suggestion_request(incoming_text)
        suggested_items: list[str] = []
        restricted_items: list[str] = []
        search_failed_items: list[str] = []
        budget_blocked_items: list[str] = []
        unavailable_items: list[str] = []
        reduced_items: list[str] = []
        guarded_change_message: str | None = None
        legacy_operation = bool(re.search(
            r"\b(?:remove|delete|increase|decrease|reduce|change|switch|replace|swap|update|edit|drop|take\s+out|"
            r"clear|cancel|checkout|confirm|pay|payment|track|usuals?|regulars?|address)\b"
            r"|\b(?:make|set)\s+(?:the\s+)?(?:first|second|third|1st|2nd|3rd|it|that|\w+)\s+(?:to\s+)?(?:\d+|zero|one|two|three|four|five)\b",
            planning_request_text, re.IGNORECASE,
        ))
        planning_turn = not user_confirmed and not legacy_operation

        for step_idx in range(1, max_iterations + 1):
            response_data = await self._call_llm(
                ([{"role": "user", "parts": [{"text": planning_request_text}]}]
                 if planning_turn else history),
                address_id=None if planning_turn else address_id,
                address_label=None if planning_turn else addr_lbl,
                cart=None if planning_turn else current_cart,
                planning_only=planning_turn,
                fast_fail_on_rate_limit=bool(last_cart_receipt or checkout_executed),
            )
            if not response_data:
                if last_cart_receipt or checkout_executed:
                    final_text = ""
                elif session.pending_request_text:
                    pending_request_needs_retry = True
                    final_text = (
                        f"I saved your request: {session.pending_request_text}. "
                        "I couldn't finish building the basket right now. "
                        "Reply *try again* and I'll check the basket before continuing."
                    )
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

            if planning_turn and any(call.get("name") == "quick_add_items" for call in function_calls):
                def invalid_item_plan(calls: list[dict[str, Any]]) -> bool:
                    for call in calls:
                        if call.get("name") != "quick_add_items":
                            continue
                        args = call.get("args")
                        items = args.get("items") if isinstance(args, dict) else None
                        if not isinstance(items, list) or not 1 <= len(items) <= 45:
                            return True
                        for item in items:
                            if not isinstance(item, dict):
                                return True
                            query = item.get("query")
                            quantity = item.get("quantity", 1)
                            if (not isinstance(query, str) or not query.strip()
                                    or type(quantity) is not int or not 1 <= quantity <= 99
                                    or re.search(r"\b(?:ingredients?|groceries|recipe|items|stuff)\b", query,
                                                 re.IGNORECASE)):
                                return True
                    return False

                if invalid_item_plan(function_calls):
                    repair_text = (
                        f"Customer request: {planning_request_text}\n\n"
                        "Your previous plan was not safe to search. Call quick_add_items with "
                        "concrete product queries, one object per item, and the customer's "
                        "quantity and pack-size details. Expand any named meal into ingredients."
                    )
                    repaired = await self._call_llm(
                        [{"role": "user", "parts": [{"text": repair_text}]}],
                        planning_only=True,
                    )
                    repaired_candidates = repaired.get("candidates", []) if repaired else []
                    parts = (repaired_candidates[0].get("content", {}).get("parts", [])
                             if repaired_candidates else [])
                    function_calls = [p["functionCall"] for p in parts if "functionCall" in p]
                    if (not any(call.get("name") == "quick_add_items" for call in function_calls)
                            or invalid_item_plan(function_calls)):
                        session.pending_request_text = planning_request_text
                        return NormalizedOutgoingResponse(
                            recipient_id=message.sender_id, channel=message.channel,
                            text="I couldn't read every item and quantity safely. I saved your request. "
                                 "Reply *try again* and I'll check it from the start.",
                            conversation_state="NEEDS_DECISION",
                        )

            # If no function call, we have the final assistant message
            if not function_calls:
                if planning_turn:
                    text_parts = [part.get("text", "").strip() for part in parts if "text" in part]
                    question = "\n".join(part for part in text_parts if part)
                    if (len(question) <= 180 and re.fullmatch(
                        r"(?is)(?:which|what|do|would|could|can|how|is|are|should|please)\b[^\n]*\?",
                        question,
                    ) and not re.search(
                        r"(?i)₹|\b(?:rs|cart|basket|added|ordered|found|available|stock|price)\b",
                        question,
                    )):
                        session.pending_request_text = planning_request_text
                        history.append({
                            "role": "model", "parts": [{"text": question}],
                            "clarification_pending": True, "recorded_at": time.time(),
                        })
                        pending_request_needs_retry = True
                        final_text = question
                        break
                    session.pending_request_text = planning_request_text
                    pending_request_needs_retry = True
                    final_text = (
                        "I haven't checked Swiggy products yet. Reply *try again* "
                        "and I'll look up your request."
                    )
                    break
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                final_text = "\n".join(t.strip() for t in text_parts if t.strip())
                # Append assistant response to history
                history.append({
                    "role": "model",
                    "parts": parts,
                    "recorded_at": time.time(),
                })
                break

            include_cart_in_choices = False
            if len(function_calls) > 1 and any(
                call.get("name") == "quick_add_items" for call in function_calls
            ):
                redundant_addresses = all(
                    isinstance(call.get("args"), dict) and call["args"].get("address_id") == address_id
                    for call in function_calls if call.get("name") == "select_delivery_address"
                )
                if redundant_addresses and all(
                    call.get("name") in {"quick_add_items", "get_cart", "select_delivery_address"}
                    for call in function_calls
                ):
                    include_cart_in_choices = any(call.get("name") == "get_cart" for call in function_calls)
                    batches = [call["args"].get("items") if isinstance(call.get("args"), dict) else None
                               for call in function_calls if call.get("name") == "quick_add_items"]
                    if all(isinstance(batch, list) for batch in batches):
                        merged = [item for batch in batches for item in batch]
                        if 1 <= len(merged) <= 30:
                            first_add = next(call for call in function_calls if call.get("name") == "quick_add_items")
                            function_calls = [{**first_add, "args": {"items": merged}}]
                            parts = [part for part in parts if "functionCall" not in part]
                            parts.append({"functionCall": function_calls[0]})
                if len(function_calls) > 1:
                    session.pending_request_text = session.pending_request_text or incoming_text
                    return NormalizedOutgoingResponse(
                        recipient_id=message.sender_id, channel=message.channel,
                        text="I couldn't safely check all those products together. I kept your request. Please tell me which items to check first; no items were added.",
                        conversation_state="NEEDS_DECISION",
                    )

            if planning_turn and any(call.get("name") not in {
                "quick_add_items", "get_cart", "search_products",
            } for call in function_calls):
                session.pending_request_text = planning_request_text
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text="Please choose an exact product variant before I add it. Nothing changed.",
                    conversation_state="NEEDS_DECISION",
                )

            cart_edits = [call for call in function_calls if call.get("name") == "update_cart"]
            if cart_edits:
                request_words = set(re.findall(r"[a-z0-9]+", planning_request_text.casefold())) - {
                    "a", "an", "and", "cart", "basket", "change", "decrease", "delete",
                    "from", "get", "in", "increase", "item", "make", "my", "of", "please",
                    "quantity", "reduce", "remove", "the", "to", "units", "update", "x",
                }
                cart_items_list = list(current_cart.items) if current_cart else []
                cart_by_spin = {item.spin_id: item for item in cart_items_list}
                remove_requested = bool(re.search(
                    r"\b(?:remove|delete|take\s+out|drop)\b", planning_request_text, re.IGNORECASE,
                ))
                ordinal_match = re.search(
                    r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th)\b",
                    planning_request_text, re.IGNORECASE,
                )
                target_ordinal_index = _ORDINALS.get(ordinal_match.group(1).casefold()) if ordinal_match else None
                target_ordinal_item = (
                    cart_items_list[target_ordinal_index]
                    if target_ordinal_index is not None and 0 <= target_ordinal_index < len(cart_items_list)
                    else None
                )

                qty_digit = re.search(r"\b(?:to|make\s+(?:it|that)?)\s+(\d+)\b", planning_request_text, re.IGNORECASE)
                qty_word = re.search(
                    r"\b(?:to|make\s+(?:it|that)?)\s+(zero|one|two|three|four|five|six|seven|eight|nine|ten)\b",
                    planning_request_text, re.IGNORECASE,
                )
                exact_qty = (
                    int(qty_digit.group(1)) if qty_digit
                    else (_WORD_NUMBERS.get(qty_word.group(1).casefold()) if qty_word else None)
                )

                for call in cart_edits:
                    items = call.get("args", {}).get("items") if isinstance(call.get("args"), dict) else None
                    if not isinstance(items, list) or not items:
                        continue
                    for item in items:
                        line = cart_by_spin.get(item.get("spin_id")) if isinstance(item, dict) else None
                        name_words = set(re.findall(r"[a-z0-9]+", line.name.casefold())) if line else set()
                        named_item = bool(
                            (request_words & name_words)
                            or (target_ordinal_item and line and target_ordinal_item.spin_id == line.spin_id)
                            or (len(cart_by_spin) == 1 and re.search(r"\b(?:that|it)\b", planning_request_text, re.IGNORECASE))
                        )
                        quantity = item.get("quantity") if isinstance(item, dict) else None
                        if (not named_item or (remove_requested and quantity != 0)
                                or (exact_qty is not None and quantity != exact_qty)):
                            session.pending_request_text = planning_request_text
                            return NormalizedOutgoingResponse(
                                recipient_id=message.sender_id, channel=message.channel,
                                text="I couldn't match that cart change to the item or quantity you named. "
                                     "Please name the item and the quantity again; nothing changed.",
                                conversation_state="NEEDS_DECISION",
                            )

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
                elif suggestion_only and fn_name == "quick_add_items":
                    tool_result = await self.tools.suggest_grocery_items(
                        fn_args.get("items", []), address_id or "",
                    )
                elif suggestion_only and fn_name in {"update_cart", "clear_cart", "checkout"}:
                    tool_result = {"success": False, "error": "SUGGESTION_ONLY"}
                else:
                    # Inject default address_id if omitted by the model
                    if "address_id" in fn_args and not fn_args["address_id"] and address_id:
                        fn_args["address_id"] = address_id

                    if fn_name == "quick_add_items" and isinstance(fn_args.get("items"), list):
                        proposed = reconcile_explicit_items(incoming_text, fn_args["items"])
                        queries = [str(item.get("query", "")) for item in proposed if isinstance(item, dict)]
                        staples = missing_recipe_staples(incoming_text, queries)
                        fn_args = {**fn_args, "items": [{"query": query} for query in staples] + proposed}

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
            history.append({
                "role": "user",
                "parts": tool_responses,
                "recorded_at": time.time(),
            })
            auth_failed = any(ec[1] for ec in executed_calls)
            limited_results = [
                ec[0].get("functionResponse", {}).get("response", {}).get("content", {})
                for ec in executed_calls
            ]
            limited_results = [result for result in limited_results
                               if isinstance(result, dict) and result.get("error") == "RATE_LIMITED"]
            if limited_results:
                session.pending_request_text = session.pending_request_text or incoming_text
                seconds = limited_results[0].get("retry_after_seconds")
                wait_text = (f"Please wait {seconds} seconds, then reply *try again*."
                             if isinstance(seconds, int) else "Please wait, then reply *try again*.")
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text=f"Swiggy is limiting requests right now. {wait_text} I'll keep your request.",
                    conversation_state="RECOVERING",
                )
            for ec in executed_calls:
                part = ec[0].get("functionResponse", {})
                result = part.get("response", {}).get("content", {})
                if (part.get("name") == "update_cart" and isinstance(result, dict)
                        and result.get("error") == "VARIANT_SELECTION_REQUIRED"):
                    session.pending_request_text = session.pending_request_text or incoming_text
                    return NormalizedOutgoingResponse(
                        recipient_id=message.sender_id, channel=message.channel,
                        text="Please choose an exact product and pack before I add it. I kept your request; nothing was added.",
                        conversation_state="NEEDS_DECISION",
                    )
                if part.get("name") != "quick_add_items" or not isinstance(result, dict):
                    continue
                if result.get("needs_variant_choice"):
                    proposal = {
                        **result, "address_id": address_id,
                        "cart_state": self._cart_proposal_state(current_cart),
                    }
                    session.pending_variant_selection = proposal
                    prefix = (format_cart_receipt(current_cart, addr_lbl or "Home", allow_checkout_prompt=False)
                              if include_cart_in_choices and current_cart else "")
                    return self._variant_choice_response(message, proposal, prefix)
                if not suggestion_only and result.get("success") and not result.get("groups"):
                    missing = result.get("unavailable_items", []) + result.get("restricted_items", [])
                    session.pending_request_text = None
                    return NormalizedOutgoingResponse(
                        recipient_id=message.sender_id, channel=message.channel,
                        text="I couldn't find eligible products for: " + ", ".join(missing)
                             + ". Nothing was added. Tell me what to try instead.",
                        conversation_state="NEEDS_DECISION",
                    )
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
                    if fn_content.get("error") in {"INGREDIENT_BUDGET_EXCEEDED", "SCOPED_BUDGET_USE_SEARCH"}:
                        guarded_change_message = str(fn_content.get("message") or "That change needs another review.")
                    if fn_content.get("error") == "BUDGET_ROLLBACK_UNVERIFIED":
                        session.external_cart_pending = True
                    if fn_call_name == "quick_add_items":
                        unavailable_items.extend(
                            str(item) for item in fn_content.get("unavailable_items", [])
                        )
                        reduced_items.extend(
                            str(item) for item in fn_content.get("reduced_items", [])
                        )
                        restricted_items.extend(
                            str(item) for item in fn_content.get("restricted_items", [])
                        )
                        search_failed_items.extend(
                            str(item) for item in fn_content.get("search_failed_items", [])
                        )
                        budget_blocked_items.extend(
                            str(item) for item in fn_content.get("budget_blocked_items", [])
                        )
                    if suggestion_only and fn_content.get("suggestions") is not None:
                        suggested_items.extend(str(item) for item in fn_content["suggestions"])
                    if fn_content.get("formatted_receipt"):
                        last_cart_receipt = fn_content["formatted_receipt"]
                    if fn_content.get("grand_total") is not None:
                        last_cart_total = float(fn_content["grand_total"])
                if ec[2]:
                    checkout_executed = True
                    checkout_result = ec[3]

            if any(ec[0].get("functionResponse", {}).get("name") in ("update_cart", "quick_add_items", "select_delivery_address", "clear_cart") for ec in executed_calls):
                try:
                    current_cart = await self.commerce.get_cart()
                except Exception:
                    pass

            if auth_failed:
                return await self._auth_expired_response(message)

            if step_idx == max_iterations:
                step_limit_reached = True

            if planning_turn:
                final_text = "I couldn't finish checking those items. Please try again."
                session.pending_request_text = planning_request_text
                break

        out_order_id: str | None = None
        out_order_total: float | None = None
        out_bridge_url: str | None = None
        conv_state = "READY"
        if pending_request_needs_retry:
            conv_state = "NEEDS_DECISION"

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
                elif checkout_result.get("error") == "PAYMENT_CHOICE_REQUIRED":
                    available = checkout_result.get("payment_options") or []
                    if available:
                        actions = [InteractiveAction(
                            action_type="list_row", id=f"payment_choice:{option['id']}",
                            title=str(option["label"])[:24],
                        ) for option in available[:10]]
                        final_text = "Please choose how you want to pay. I'll show the final basket again before placing an order."
                        conv_state = "NEEDS_PAYMENT"
                    else:
                        final_text = "I couldn't verify an available payment option. Please try again later."
                        conv_state = "NEEDS_DECISION"
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

        if suggestion_only:
            if not suggested_items:
                suggested_items = (
                    ["ginger", "lemon", "honey", "tea"]
                    if any(word in incoming_text.casefold() for word in ("cold", "cough", "throat"))
                    else ["water", "tea", "a light snack"]
                )
            options = ", ".join(suggested_items[:5])
            final_text = (
                "I can suggest groceries, but I can't add medical products here. "
                f"You could choose from: {options}. Which would you like me to add?"
            )
            actions = []
            conv_state = "NEEDS_DECISION"
            session.pending_request_text = None
        elif restricted_items:
            restricted = ", ".join(dict.fromkeys(restricted_items))
            receipt = (
                format_cart_receipt(current_cart, addr_lbl or "Home", allow_checkout_prompt=False)
                if current_cart and current_cart.items else ""
            )
            final_text = (
                f"I can't add medical products through this WhatsApp shopping flow: {restricted}. "
                "I can help you choose groceries instead."
            )
            if receipt:
                final_text += f"\n\n{receipt}"
            actions = []
            conv_state = "NEEDS_DECISION"
        elif search_failed_items:
            unchecked = ", ".join(dict.fromkeys(search_failed_items))
            receipt = (
                format_cart_receipt(current_cart, addr_lbl or "Home", allow_checkout_prompt=False)
                if current_cart and current_cart.items else ""
            )
            final_text = (
                f"I couldn't check {unchecked} with Swiggy right now, so I don't know whether "
                "those items are available. I saved your request. Reply *try again* to continue."
            )
            if receipt:
                final_text += f"\n\n{receipt}"
            session.pending_request_text = session.pending_request_text or message.text.strip()
            actions = []
            conv_state = "NEEDS_DECISION"

        if guarded_change_message:
            final_text = guarded_change_message
            actions = []
            conv_state = "NEEDS_DECISION"

        if budget_blocked_items or unavailable_items or reduced_items:
            blocked = list(dict.fromkeys(budget_blocked_items))
            unavailable = list(dict.fromkeys(unavailable_items))
            reduced = list(dict.fromkeys(reduced_items))
            session.budget_blocked_items = blocked + unavailable + reduced
            session.pending_approval = None
            receipt = (format_cart_receipt(current_cart, addr_lbl or "Home", allow_checkout_prompt=False)
                       if current_cart and current_cart.items else "Your basket is empty.")
            scoped_note = ""
            if session.ingredient_budget_inr is not None and current_cart:
                ingredient_total = sum(
                    item.total_price for item in current_cart.items
                    if item.spin_id in session.ingredient_spin_ids
                )
                scoped_note = (
                    f"Ingredient items: ₹{ingredient_total:,.2f} of "
                    f"₹{session.ingredient_budget_inr:,.2f}. "
                    "Extras and shared fees are outside that limit; the full payable total is below. "
                )
            final_text = (
                (("These recipe ingredients did not fit your ingredient-price limit: "
                  if session.ingredient_budget_inr is not None else
                  "These requested items did not fit your budget: ") + ", ".join(blocked) + ". "
                 if blocked else "")
                + ("These requested items were unavailable: " + ", ".join(unavailable) + ". "
                   if unavailable else "")
                + ("Swiggy reduced these quantities: " + ", ".join(reduced) + ". "
                   if reduced else "")
                + scoped_note + "I kept the items that fit in the order you listed them. "
                "Would you like to keep this partial basket or change something?\n\n" + receipt
            )
            actions = [
                InteractiveAction(action_type="button", id="accept_partial_basket", title="Keep These Items"),
                InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
            ]
            conv_state = "NEEDS_DECISION"

        if (not final_text.strip() or final_text.strip() == "How can I help with your groceries today?") and last_cart_receipt:
            final_text = last_cart_receipt
        if out_order_total is None and last_cart_total is not None:
            out_order_total = last_cart_total

        if any(action.id == "confirm_order" for action in actions):
            if session.budget_blocked_items:
                session.pending_approval = None
                actions = [action for action in actions if action.id != "confirm_order"]
                conv_state = "NEEDS_DECISION"
                final_text = (
                    "Some requested items were left out: "
                    + ", ".join(session.budget_blocked_items)
                    + ". Please review this partial basket and choose Keep These Items or tell me what to change."
                )
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id, channel=message.channel,
                    text=final_text,
                    interactive_actions=[InteractiveAction(action_type="button", id="accept_partial_basket", title="Keep These Items"),
                                         InteractiveAction(action_type="button", id="modify_cart", title="Change Items")],
                    conversation_state=conv_state,
                )
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
            if reviewed_cart and not reviewed_cart.address_id and approved_address:
                reviewed_cart.address_id = approved_address

            approval_ok = bool(
                reviewed_cart
                and approved_address
                and self._record_pending_approval(customer_id, reviewed_cart, approved_address)
            )

            if not approval_ok:
                self.get_session(customer_id).pending_approval = None
                actions = [action for action in actions if action.id != "confirm_order"]
                if user_confirmed:
                    conv_state = "NEEDS_DECISION"
                    final_text = "I couldn't verify the complete basket and delivery address. Please review them before ordering."
                else:
                    actions = [
                        InteractiveAction(action_type="button", id="proceed_checkout", title="Proceed to Checkout"),
                        InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                    ]
            else:
                receipt = format_cart_receipt(
                    reviewed_cart, self._customer_address_label.get(customer_id) or approved_address
                )
                basket_pattern = r"🛒\s*\*?Your Basket.*"
                if re.search(basket_pattern, final_text, flags=re.DOTALL | re.IGNORECASE):
                    intro = re.sub(basket_pattern, "", final_text, flags=re.DOTALL | re.IGNORECASE).strip()
                    final_text = f"{intro}\n\n{receipt}" if intro else receipt
                elif final_text and final_text.strip():
                    final_text = f"{final_text.strip()}\n\n{receipt}"
                else:
                    final_text = receipt
                out_order_total = reviewed_cart.grand_total
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"
        elif not checkout_executed:
            self.get_session(customer_id).pending_approval = None

        if (last_cart_receipt and not session.unresolved_items
                and not pending_request_needs_retry and not search_failed_items):
            session.pending_request_text = None

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
        elif name == "batch_search_products":
            addr = args.get("address_id") or address_id
            return await self.tools.batch_search_products(args.get("queries", []), address_id=addr)
        elif name == "get_cart":
            loc = self._customer_address_label.get(customer_id, "Home")
            return await self.tools.get_cart(delivery_location=loc)
        elif name == "quick_add_items":
            session = self.get_session(customer_id)
            session.pending_approval = None
            return await self.tools.prepare_variant_choices(args.get("items", []), address_id or "")
        elif name == "update_cart":
            session = self.get_session(customer_id)
            session.pending_approval = None
            proposed = args.get("items", [])
            try:
                existing = await self.commerce.get_cart()
            except ProviderAuthError:
                return {"success": False, "error": "AUTH_EXPIRED"}
            except ProviderRateLimitedError as exc:
                return {"success": False, "error": "RATE_LIMITED",
                        "retry_after_seconds": exc.retry_after_seconds}
            except Exception:
                return {"success": False, "error": "CART_UNAVAILABLE"}
            existing_by_spin = {item.spin_id: item for item in existing.items}
            if not isinstance(proposed, list) or any(
                not isinstance(item, dict) or type(item.get("quantity")) is not int
                for item in proposed
            ):
                return {"success": False, "error": "INVALID_CART_PROPOSAL"}
            if isinstance(proposed, list) and any(
                isinstance(item, dict) and item.get("quantity", 0) > 0
                and (item.get("spin_id") not in existing_by_spin
                     or (item.get("sku_id") and item.get("sku_id") != existing_by_spin[item["spin_id"]].sku_id))
                for item in proposed
            ):
                return {"success": False, "error": "VARIANT_SELECTION_REQUIRED"}
            addr = address_id
            loc = self._customer_address_label.get(customer_id, "Home")
            result = await self.tools.update_cart(
                proposed, address_id=addr or "", delivery_location=loc,
                ingredient_budget_inr=session.ingredient_budget_inr,
                ingredient_spin_ids=session.ingredient_spin_ids,
            )
            unresolved_by_spin = {
                item["spin_id"]: item for item in session.unresolved_items if item.get("spin_id")
            }
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
                self.get_session(customer_id).budget_inr = None
                self.get_session(customer_id).ingredient_budget_inr = None
                self.get_session(customer_id).ingredient_extras_text = None
                self.get_session(customer_id).ingredient_spin_ids.clear()
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
            if sess.ingredient_budget_inr is not None:
                ingredient_total = sum(
                    item.total_price for item in cart.items
                    if item.spin_id in sess.ingredient_spin_ids
                )
                if ingredient_total > sess.ingredient_budget_inr:
                    return {"success": False, "error": "INGREDIENT_BUDGET_EXCEEDED", "retryable": False,
                            "message": "Recipe ingredients exceed the agreed price limit. Please review the basket."}
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
                    payment_method=sess.selected_payment_method or "UPI",
                    payment_option_kind=sess.selected_payment_kind,
                    payment_option_id=sess.selected_payment_id,
                    is_user_confirmed=True,
                    budget_inr=sess.budget_inr,
                    expected_cart_fingerprint=approval.fingerprint,
                )
                if attempt_id is not None:
                    await self.attempt_store.finish(attempt_id, result)
                if result.get("error") in {
                    "PAYMENT_CHOICE_REQUIRED", "PAYMENT_OPTION_UNAVAILABLE",
                    "PAYMENT_OPTIONS_UNAVAILABLE", "QR_ELIGIBILITY_UNVERIFIED",
                }:
                    sess.pending_approval = approval
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
                    for i, fn_resp in enumerate(fn_responses):
                        call_id = fn_resp.get("id") or f"call_{i}"
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
                        tc_obj = {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": json.dumps(fn_args) if isinstance(fn_args, dict) else str(fn_args),
                            },
                        }
                        if fn_call.get("extra_content"):
                            tc_obj["extra_content"] = fn_call["extra_content"]
                        tool_calls.append(tc_obj)
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
        planning_only: bool = False,
        fast_fail_on_rate_limit: bool = False,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        """Perform request to Groq Cloud primary with OpenRouter automatic fallback."""
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_call_time
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)
        self._last_call_time = asyncio.get_running_loop().time()

        system_text = (_SHOPPING_PLAN_PROMPT if planning_only else build_system_instruction(
            address_id=address_id, address_label=address_label, cart=cart,
        ))

        providers: list[dict[str, Any]] = []
        if self.gemini_api_key and (self._gemini_explicitly_passed or self.groq_api_key or self.openrouter_api_key):
            providers.append({
                "name": "gemini",
                "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "model": self.gemini_model,
                "headers": {
                    "Authorization": f"Bearer {self.gemini_api_key}",
                    "Content-Type": "application/json",
                },
                "format": "openai",
            })
            providers.append({
                "name": "gemini-fallback",
                "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "model": self.gemini_fallback_model,
                "headers": {
                    "Authorization": f"Bearer {self.gemini_api_key}",
                    "Content-Type": "application/json",
                },
                "format": "openai",
            })
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
                "tools": ([tool for tool in OPENAI_TOOL_DECLARATIONS
                           if tool["function"]["name"] == "quick_add_items"]
                          if planning_only else OPENAI_TOOL_DECLARATIONS),
                "tool_choice": "auto",
                "temperature": 0.2,
            }

            try:
                resp = await client.post(p_url, json=payload, headers=p_headers)
                if resp.status_code in (429, 503, 404):
                    if fast_fail_on_rate_limit:
                        logger.info("Post-tool call encountered %d; fast-returning receipt result.", resp.status_code)
                        return None

                    # Parse reset duration if provided by provider (e.g. Groq '3.817s' or standard Retry-After)
                    reset_header = resp.headers.get("x-ratelimit-reset-tokens") or resp.headers.get("retry-after")
                    sleep_time = 2.0
                    if reset_header:
                        try:
                            sleep_time = float(str(reset_header).rstrip("s").strip())
                        except (ValueError, TypeError):
                            sleep_time = 2.0

                    # If provider explicitly gave a fast reset window (<= 4.0s, e.g. Groq token bucket), wait and retry once
                    if resp.status_code == 429 and reset_header is not None and sleep_time <= 4.0 and attempt == 0:
                        logger.warning("Provider %s rate-limited; resetting in %.1fs. Waiting to retry...", provider["name"], sleep_time)
                        await asyncio.sleep(sleep_time + 0.2)
                        continue

                    if attempt + 1 < len(providers):
                        next_provider = providers[attempt + 1]
                        logger.warning(
                            "Provider %s (%s) returned %d; pivoting immediately to %s (%s)...",
                            provider["name"], p_model, resp.status_code,
                            next_provider["name"], next_provider.get("model"),
                        )
                        await asyncio.sleep(0.2)
                        continue

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
            for i, tc in enumerate(tool_calls):
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except (ValueError, TypeError):
                    args = None
                tc_id = tc.get("id") or f"call_{i}"
                fc_dict: dict[str, Any] = {
                    "name": fn_name,
                    "args": args,
                    "id": tc_id,
                }
                if tc.get("extra_content"):
                    fc_dict["extra_content"] = tc["extra_content"]
                parts.append({
                    "functionCall": fc_dict
                })
        else:
            text = msg.get("content") or ""
            parts.append({"text": text})
        return {"candidates": [{"content": {"parts": parts}}]}
