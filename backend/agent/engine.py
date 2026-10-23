"""Autonomous ReAct agent engine for Swiggy Instamart grocery ordering powered by Google Gemini."""
from __future__ import annotations
import math
from backend.agent.approval import cart_fingerprint
from backend.agent.session_manager import record_pending_cart_clear
from backend.agent.formatters import _format_inr, format_cart_receipt
from backend.channels.models import InteractiveAction

import asyncio
import logging
import time
from typing import Any, Optional

from backend.agent.config import BRAIN_MODEL, BRAIN_FALLBACK_MODEL
from backend.agent.schemas import RAW_TOOL_DECLARATIONS
from backend.agent.tools import SwiggyAgentTools
from backend.agent.gemini import GeminiClient
from backend.agent.budget import read_budget_cap
from backend.agent.formatters import (
    build_address_choice_response,
    build_auth_expired_response,
)
from backend.agent.session_manager import (
    dump_task_state_dict,
    prune_history_entries,
    record_pending_approval,
    restore_task_state_dict,
)
from backend.agent.preflight_handler import execute_preflight

# --- Merged Tool Execution & Checkout Outcome ---


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

    return ""





def process_checkout_outcome(

    engine: Any,

    customer_id: str,

    *,

    checkout_executed: bool,

    checkout_result: Optional[dict[str, Any]],

    last_cart_receipt: Optional[str],

    current_cart: Optional[CommerceCart],

    addr_lbl: Optional[str],

    final_text: str,

    actions: list[InteractiveAction],

    pending_request_needs_retry: bool,

) -> tuple[str, str, list[InteractiveAction], Optional[str], Optional[float], Optional[str]]:

    """Evaluate checkout results and return (conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url)."""

    out_order_id: str | None = None

    out_order_total: float | None = None

    out_bridge_url: str | None = None

    conv_state = "READY"

    session = engine.get_session(customer_id) if hasattr(engine, "get_session") else None

    if pending_request_needs_retry:

        conv_state = "NEEDS_DECISION"



    if checkout_executed and checkout_result:

        if not checkout_result.get("success"):

            if checkout_result.get("error") == "CONFIRMATION_REQUIRED":

                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

                token = ""

                if session and getattr(session, "pending_approval", None) and session.pending_approval.token:

                    token = session.pending_approval.token

                elif engine and current_cart and hasattr(engine, "_record_pending_approval"):

                    target_addr = (

                        (session.address_id if session else None)

                        or (current_cart.address_id if current_cart else None)

                        or addr_lbl

                        or ""

                    )

                    if engine._record_pending_approval(customer_id, current_cart, target_addr):

                        sess = engine.get_session(customer_id) if hasattr(engine, "get_session") else None

                        if sess and getattr(sess, "pending_approval", None):

                            token = sess.pending_approval.token or ""



                actions = []

                if token:

                    actions.append(InteractiveAction(action_type="button", id=f"confirm_order:{token}", title="Confirm Order"))

                actions.append(InteractiveAction(action_type="button", id="modify_cart", title="Change Items"))



                receipt_str = last_cart_receipt or (format_cart_receipt(current_cart, addr_lbl or "Home") if current_cart else "")

                final_text = (f"{receipt_str}\n\n👉 Reply *Confirm* to place order, or let me know if you'd like to change anything!").strip()

            elif (

                checkout_result.get("error") in ("ORDER_STATE_UNKNOWN", "ATTEMPT_UNRESOLVED")

                or checkout_result.get("status") == "ORDER_STATE_UNKNOWN"

            ):

                conv_state = "RECOVERING"

                final_text = (

                    "I couldn't verify whether checkout completed. "

                    "Please check the order status in Swiggy or contact support before trying again. "

                    "Further checkout is on hold until this is resolved."

                )

            elif checkout_result.get("error") == "PAYMENT_CHOICE_REQUIRED":

                available = checkout_result.get("payment_options") or []

                if available:

                    actions = [

                        InteractiveAction(

                            action_type="list_row",

                            id=f"payment_choice:{option['id']}",

                            title=str(option["label"])[:24],

                        )

                        for option in available[:10]

                    ]

                    final_text = "Please choose how you want to pay. I'll show the final basket again before placing an order."

                    conv_state = "NEEDS_PAYMENT"

                else:

                    final_text = "I couldn't verify an available payment option. Please try again later."

                    conv_state = "NEEDS_DECISION"

            else:

                error_msg = checkout_result.get("error") or checkout_result.get("message") or "Provider checkout error"

                base_text = (

                    f"Checkout could not be completed or verified: {error_msg}. "

                    "Please check the Swiggy order status before trying again."

                )

                extra = final_text.strip()

                final_text = f"{base_text}\n\n{extra}" if extra else base_text

                conv_state = "FAILED"

        else:

            out_order_id = checkout_result.get("order_id")

            out_order_total = checkout_result.get("grand_total")

            out_bridge_url = checkout_result.get("bridge_url")

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
                if session is not None:
                    session.reset_order_address()
                pay_url = checkout_result.get("upi_intent_url") or checkout_result.get("bridge_url")
                if pay_url:
                    actions = [
                        InteractiveAction(
                            action_type="url",
                            id=f"pay_order:{out_order_id or 'order'}",
                            title="Pay with UPI (1-Tap)",
                            url=pay_url,
                        )
                    ]
                else:
                    actions = [
                        InteractiveAction(
                            action_type="button",
                            id=f"check_payment:{out_order_id or 'order'}",
                            title="Check Payment",
                        ),
                        InteractiveAction(
                            action_type="button",
                            id="modify_cart",
                            title="Change Items",
                        ),
                    ]
                code_text = order_message(checkout_result)
                extra = final_text.strip()
                final_text = f"{code_text}\n\n{extra}" if extra else code_text

            elif status == "ORDER_PLACED":

                conv_state = "ORDER_PLACED"

                if session is not None:

                    session.reset_order_address()

                final_text = order_message(checkout_result)

            else:

                conv_state = "READY"



    return conv_state, final_text, actions, out_order_id, out_order_total, out_bridge_url



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
    """Dispatch a single function call to SwiggyAgentTools."""
    logger.info("Executing agent tool call: %s", name)
    session = engine.get_session(customer_id)
    if name == "get_saved_addresses":
        return await engine.tools.get_saved_addresses(customer_id)
    elif name == "select_delivery_address":
        session.pending_approval = None
        res = await engine.tools.select_delivery_address(customer_id, args.get("address_id", ""))
        if res.get("success") and res.get("address_id"):
            session.address_id = res["address_id"]
            session.address_label = (
                res.get("clean_address") or res.get("label") or "Selected Address"
            )
            session.order_address_confirmed = True
            if hasattr(engine, "commerce") and hasattr(engine.commerce, "get_cart"):
                try:
                    new_cart = await engine.commerce.get_cart(delivery_location=session.address_label)
                    session.known_cart_fingerprint = cart_fingerprint(new_cart, session.address_id)
                except Exception:
                    pass
        return res
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
        loc = session.address_label or "Home"
        return await engine.tools.get_cart(delivery_location=loc)
    elif name == "manage_basket":
        session = engine.get_session(customer_id)
        session.pending_approval = None
        loc = session.address_label or "Home"
        result = await engine.tools.manage_basket(
            address_id=args.get("address_id") or address_id or "",
            add=args.get("add"),
            remove=args.get("remove"),
            set_quantity=args.get("set_quantity"),
            current_cart=current_cart,
            delivery_location=loc,
            budget_cap_inr=session.budget_inr,
        )
        if result.get("verified_fingerprint"):
            session.known_cart_fingerprint = result["verified_fingerprint"]
        return result
    elif name == "clear_cart":
        session = engine.get_session(customer_id)
        try:
            cart = await engine.commerce.get_cart()
        except Exception:
            cart = None
        address_id = (
            session.address_id
            or (cart.address_id if cart else None)
            or ""
        )
        if cart and not cart.address_id and address_id:
            cart.address_id = address_id
        if not cart or not cart.items:
            return {"success": True, "message": "Cart is already empty."}
        if session:
            record_pending_cart_clear(session, cart, address_id)
        return {"success": False, "error": "CLEAR_CONFIRMATION_REQUIRED"}
    elif name == "checkout":
        sess = engine.get_session(customer_id)
        confirmed_by_user = bool(user_confirmed)
        approval = sess.pending_approval
        if sess.unresolved_items:
            if confirmed_by_user and approval and approval.expires_at > time.time():
                sess.unresolved_items.clear()
            else:
                return {
                    "success": False,
                    "error": "ITEMS_UNRESOLVED",
                    "retryable": False,
                    "message": "Please resolve each missing or reduced requested item before checkout.",
                }
        if sess.external_cart_pending:
            return {"success": False, "error": "EXTERNAL_CART_UNREVIEWED", "retryable": False}
        if not confirmed_by_user or not approval or approval.expires_at <= time.time():
            return {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "retryable": False,
                "message": "Please review the current basket and confirm it before checkout.",
            }
        checkout_address = args.get("address_id", "") or address_id or ""
        try:
            cart = await engine.commerce.get_cart(args.get("cart_id", ""))
        except Exception:
            return {
                "success": False,
                "error": "CART_UNAVAILABLE",
                "retryable": False,
                "message": "I couldn't verify your basket. Please review it again.",
            }
        if cart.address_id is None and checkout_address:
            cart.address_id = checkout_address
        if cart_fingerprint(cart, checkout_address) != approval.fingerprint:
            sess.pending_approval = None
            return {
                "success": False,
                "error": "CART_CHANGED",
                "retryable": False,
                "message": "Your basket or total changed. Please review it again.",
            }
        attempt_id = None
        if settings.CHECKOUT_MODE == "live":
            if engine.attempt_store is None:
                return {
                    "success": False,
                    "error": "DURABLE_ATTEMPT_REQUIRED",
                    "retryable": False,
                    "message": "Live checkout is unavailable until durable attempt tracking is ready.",
                }
            try:
                attempt_id = await engine.attempt_store.start(
                    customer_id,
                    cart.cart_id or "",
                    checkout_address,
                    approval.fingerprint,
                    cart.grand_total,
                )
            except Exception:
                logger.exception("Could not reserve durable checkout attempt.")
                return {"success": False, "error": "DURABLE_ATTEMPT_REQUIRED", "retryable": False}
            if attempt_id is None:
                return {
                    "success": False,
                    "error": "ATTEMPT_UNRESOLVED",
                    "retryable": False,
                    "message": "An earlier checkout or payment is unresolved. Further checkout is on hold.",
                }
        try:
            result = await engine.tools.checkout(
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
                await engine.attempt_store.finish(attempt_id, result)
            if not result.get("success"):
                sess.pending_approval = None
            else:
                sess.pending_approval = None
            return result
        except Exception as exc:
            logger.exception("Checkout outcome could not be verified: %s", exc)
            fallback = {"success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False}
            sess.pending_approval = None
            if attempt_id is not None:
                try:
                    await engine.attempt_store.finish(attempt_id, fallback)
                except Exception as finish_exc:
                    logger.warning("Could not record attempt failure: %s", finish_exc)
            return fallback
    elif name == "track_order":
        return await engine.tools.track_order(args.get("order_id", ""))
    elif name == "set_budget":
        raw_amount = args.get("amount_inr")
        try:
            amount = float(raw_amount)
            if not math.isfinite(amount) or amount <= 0:
                return {"success": False, "error": "Invalid budget amount"}
        except (TypeError, ValueError):
            return {"success": False, "error": "Invalid budget amount"}
        session.budget_inr = amount
        return {"success": True, "budget_inr": amount, "message": f"Budget set to ₹{amount}"}
    return {"error": f"Unknown tool: {name}"}


from backend.agent.react_coordinator import execute_react_turn_loop
from backend.agent.response_synthesizer import synthesize_turn_response
from backend.channels.models import (
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart
from backend.integrations.commerce.port import CommercePort
from backend.agent.prompts import (
    build_system_instruction,
)

logger = logging.getLogger("grocer.agent.engine")


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
        self.attempt_store = attempt_store
        self.state_store = state_store
        self.gemini_api_key = gemini_api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.gemini_model = gemini_model or BRAIN_MODEL
        self.gemini_fallback_model = gemini_fallback_model or BRAIN_FALLBACK_MODEL
        self.timeout = timeout
        # Single authoritative CustomerSession map
        self._sessions: dict[str, Any] = {}
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

    def get_session(self, customer_id: str) -> Any:
        """Return the atomic CustomerSession for customer_id."""
        from backend.agent.session import CustomerSession
        sess = self._sessions.get(customer_id)
        if sess is None:
            sess = CustomerSession(customer_id=customer_id)
            self._sessions[customer_id] = sess
        return sess

    async def forget_customer(self, customer_id: str) -> None:
        """Drop local mirrors after a verified deletion request."""
        self._locks.pop(customer_id, None)
        sess = self._sessions.pop(customer_id, None)
        if sess is not None:
            sess.clear_all()

    def evict_inactive_sessions(self, ttl_seconds: float = 1800.0) -> int:
        """Evict customer sessions and locks that have exceeded inactivity TTL."""
        now = time.time()
        to_evict = []
        for cid, sess in list(self._sessions.items()):
            last_active = getattr(sess, "last_active_time", None) or getattr(sess, "last_active_ts", None) or 0.0
            if last_active > 0 and (now - last_active) > ttl_seconds:
                to_evict.append(cid)
        for cid in to_evict:
            self._locks.pop(cid, None)
            s = self._sessions.pop(cid, None)
            if s is not None:
                s.clear_all()
        return len(to_evict)

    def _restore_task_state(self, customer_id: str, state: dict[str, Any] | None) -> None:
        session, _ = restore_task_state_dict(
            customer_id=customer_id,
            state=state,
        )
        self._sessions[customer_id] = session

    def _task_state_snapshot(self, customer_id: str) -> dict[str, Any]:
        return dump_task_state_dict(self.get_session(customer_id))

    def _address_choice_response(
        self, message: NormalizedIncomingMessage, addresses: list[dict[str, Any]]
    ) -> NormalizedOutgoingResponse:
        return build_address_choice_response(message, addresses)

    def reset_customer_order_address(self, customer_id: str) -> None:
        """Atomically clear order address lock across session."""
        session = self.get_session(customer_id)
        session.reset_order_address()
        session.pending_approval = None

    def _record_pending_approval(
        self, customer_id: str, cart: CommerceCart, address_id: str
    ) -> bool:
        return record_pending_approval(self.get_session(customer_id), cart, address_id)

    async def close(self) -> None:
        """Close Gemini client session on shutdown."""
        if hasattr(self, "gemini") and self.gemini:
            await self.gemini.close()

    async def _auth_expired_response(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        return await build_auth_expired_response(message)

    def get_history(self, customer_id: str) -> list[dict[str, Any]]:
        return self.get_session(customer_id).history

    def _prune_history(self, customer_id: str, max_user_turns: int = 20) -> None:
        """Keep conversation history bounded by whole user turn boundaries and compact past search returns."""
        session = self.get_session(customer_id)
        session.history = prune_history_entries(
            session.history or [],
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
                    "I can only read text messages, voice notes, and grocery list photos right now! "
                    "Please send your grocery items so I can check dark store stock and add them to your cart. 🛒"
                ),
                conversation_state="READY",
            )

        # Handle media input (voice notes or grocery list photos)
        if getattr(message, "media_id", None) or getattr(message, "media_type", None) in ("audio", "image"):
            from backend.channels.whatsapp_media import download_whatsapp_media, extract_groceries_from_media

            # Check if media bytes were supplied directly (e.g. in test or memory buffer)
            media_bytes = getattr(message, "raw_media_bytes", None)
            mime_type = message.media_mime_type or ("audio/ogg" if message.media_type == "audio" else "image/jpeg")

            if media_bytes is None and message.media_id:
                media_bytes, fetched_mime = await download_whatsapp_media(message.media_id)
                if fetched_mime:
                    mime_type = fetched_mime

            if media_bytes and getattr(self, "gemini", None):
                extracted_request = await extract_groceries_from_media(
                    self.gemini,
                    media_bytes,
                    mime_type,
                    message.media_type or "image",
                    caption=message.media_caption or "",
                )
                if extracted_request == "NO_GROCERIES_FOUND":
                    note_type = "voice note" if message.media_type == "audio" else "photo"
                    return NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text=(
                            f"I couldn't clearly read your grocery list from that {note_type}. "
                            "Could you please send a clearer photo or voice note, or type the items? "
                            "Your current basket is saved. 🛒"
                        ),
                        conversation_state="READY",
                    )
                message = message.model_copy(update={"text": extracted_request})
                incoming_text = extracted_request
            elif not media_bytes and not incoming_text.replace("[VOICE_NOTE]", "").replace("[GROCERY_PHOTO]", "").strip():
                return NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text=(
                        "I couldn't download that media file. Please try sending your grocery items again as text or a clear photo! 🛒"
                    ),
                    conversation_state="READY",
                )

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
                    logger.exception("Turn aborted with error for customer=%s; skipping state save.", customer_id)
                    raise

            self.last_turn_latency_ms = round(
                (asyncio.get_running_loop().time() - start_time) * 1000, 1
            )
            logger.info(
                "Turn completed for customer=%s in %.1fms (state=%s)",
                customer_id,
                self.last_turn_latency_ms,
                result.conversation_state,
            )
            if result.conversation_state == "AWAITING_PAYMENT" and result.order_id:
                if hasattr(self, "payment_poller") and self.payment_poller:
                    self.payment_poller.start_polling(
                        customer_id=customer_id,
                        order_id=result.order_id,
                        paas_id=result.order_id,
                        recipient_id=message.sender_id,
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



