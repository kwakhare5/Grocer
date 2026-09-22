"""Autonomous Gemini ReAct agent engine for Swiggy Instamart grocery ordering."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional
from urllib.parse import quote

import httpx

from backend.agent.tools import (
    GEMINI_TOOL_DECLARATIONS,
    SwiggyAgentTools,
    _format_inr,
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

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

_SYSTEM_PROMPT = """You are GROCER, an exceptionally smart, delightful WhatsApp grocery concierge powered by Swiggy Instamart.
Your mission is to get the customer's groceries delivered to their doorstep with zero friction and total accuracy.

### COMMUNICATION STYLE:
- Speak warmly, naturally, and concisely in English formatted for WhatsApp readability.
- Use clean WhatsApp formatting (*bold* for emphasis). Never use raw JSON, code blocks, or markdown tables.
- Avoid robotic corporate disclaimers or repetitive pleasantries.

### UNIVERSAL INTENT & SHOPPING ARCHETYPES:
1. Specific Item / Staple Intent:
   When the customer asks for a specific item, brand, or everyday staple (e.g. "milk", "eggs", "Amul butter 500g", "Surf Excel 1kg", "Dettol soap"):
   - Search Swiggy, select the top in-stock variant matching the requested unit/pack size, update the cart, and show the updated basket receipt.
2. Broad / Variant Choice Intent:
   When the customer asks for an open-ended category with wide variety (e.g. "chocolates", "chips", "ice cream", "shampoo", "biscuits"):
   - Search Swiggy and present the top 2-3 in-stock options with number, name, pack size, and price:
     "I found a few options:
     1. Cadbury Dairy Milk Silk (60g) — ₹90
     2. Cadbury Dairy Milk Crackle (36g) — ₹50
     3. Cadbury Bournville Dark (80g) — ₹110
     Which one would you like?"
3. Composite / Meal / Recipe / Occasion Intent:
   When the customer asks for a dish, meal, event, or budget bundle (e.g. "pasta groceries under 500", "chai and snacks for 4", "breakfast for two under 200", "weekly essentials under 2000"):
   - A dish is a complete kit. Proactively infer essential ingredients (Core carbs + Sauce/Body + Dairy/Protein + Aromatics) within the budget.
   - When a specific dish/recipe is requested (e.g. pasta, biryani, sandwich, tea), the search MUST prioritize the core dish ingredients (e.g. for pasta: search 'pasta', 'sauce', 'cheese'). NEVER substitute generic kitchen staples (like flour or dal) when a specific dish or recipe is named.
   - When a strict budget is given, choose key essential items so the total including delivery/packaging fees stays strictly within the budget.
   - Search products in parallel, add the complete kit to the basket in one `update_cart` call, and ask if they'd like to add any extras.
4. Problem / Symptom / Situational Care Intent:
   When the customer describes a symptom, ritual, or situation without naming products (e.g. "terrible cold and sore throat", "upset stomach / light food", "midnight study snacks", "pooja samagri"):
   - Proactively infer what is needed and search concurrently in parallel:
     * Cold/Headache: search Crocin/Paracetamol, Strepsils, Vicks, and Green/Herbal tea.
     * Upset stomach: search Dahi/curd, bananas, oats/khichdi.
     * Study/Midnight snacks: search chips, chocolate, almonds, instant noodles.
     * Pooja ritual: search agarbatti, camphor/kapoor, ghee.
   - Add the essential care kit to the basket with `update_cart` and show the receipt.
5. Conversational Disambiguation & Deltas:
   - If you presented a list of numbered choices and the customer replies with an ambiguous affirmation ("ok", "yes", "sure", "add it"), NEVER guess an arbitrary item. Ask:
     "Which one would you like me to add? Reply 1, 2, or 3 (or name the item)."
   - If the customer uses a relative reference ("the second one", "cheapest", "the 1kg one", "the dark chocolate"), resolve the referenced item and add it.
   - When modifying the cart ("remove the sauce", "make it 2 packs"), pass the cumulative cart items with the change to `update_cart`.

### TOOL CALL EFFICIENCY & PARALLEL EXECUTION:
- When searching for multiple items or building a meal/bundle, ALWAYS execute all search queries concurrently in a SINGLE turn using parallel tool calls. NEVER search for items one at a time across multiple turns.
- After receiving search results, immediately call `update_cart` with all matched items.

### BASKET & RECEIPT RULE:
- When presenting the customer's basket, output the verified `formatted_receipt` provided by `update_cart` or `get_cart`.
- Never manually recalculate numbers or invent fee lines; rely on the verified receipt so every rupee is mathematically exact.

### HINGLISH & INDIAN GROCERY AWARENESS:
- Recognize common Indian kitchen terms and map them to catalogue searches:
  `doodh` -> milk, `dahi` -> curd/yogurt, `cheeni`/`shakkar` -> sugar, `anda` -> eggs, `aata` -> wheat flour, `chawal` -> rice, `tel` -> cooking oil, `adrak` -> ginger, `chai patti` -> tea, `pyaz` -> onions, `aloo` -> potatoes.

### DIETARY & INVENTORY CONSTRAINTS:
- Strictly respect dietary preferences (pure veg, eggless, sugar-free, whole wheat).
- If a requested item/brand is out of stock, substitute with the closest in-stock variant and clearly disclose the substitute on the receipt.
- If the cart is below the store's `min_order_threshold`, proactively inform the customer and suggest quick add-ons (milk, bread, snacks).

### CHECKOUT & PAYMENT:
- NEVER call `checkout` until the customer has explicitly approved the basket (e.g. said "Confirm", "Yes", "Place order", or tapped Confirm Order).
- When confirmed, call `checkout` with `payment_method='UPI'`, `payment_option_kind='qr'`, and `is_user_confirmed=true`.
- Present the UPI payment link clearly.
- If the customer asks to track an order, call `track_order` and report status, ETA, and delivery partner details.
"""

# ============================================================================
# DETERMINISTIC SAFETY GUARDS & REGEX PATTERNS
# ============================================================================

_ORDER_SUCCESS_PATTERNS = (
    # 1. Passive / State assertions: [Subject: order/items/groceries/etc] + [copula/auxiliary] + [participle/status]
    # Matches: "order was placed", "order has been placed", "order placed", "order confirmed",
    #          "items have been ordered", "order completed", "order is complete", "order accepted",
    #          "order has been received", "order has been dispatched", "groceries have been ordered",
    #          "Your purchase has been confirmed.", "Your basket was checked out successfully."
    # Rejects: "order was not placed", "order could not be placed", "no order has been placed"
    re.compile(
        r"(?i)(?:(?:\b(?:your|the|this)\s+)?(?<!no )(?<!not )(?<!n\'t )\b(?:order|groceries|items|basket|delivery|everything|checkout|purchase)\s+)"
        r"(?:(?:has|have|is|are|was|were|got)\s+(?:now\s+|just\s+|already\s+)?(?:been\s+)?(?:successfully\s+)?)?"
        r"(?:placed|confirmed|booked|completed|complete|accepted|received|submitted|processed|dispatched|delivered|fulfilled|shipped|sent|ordered|checked\s+out)\b"
    ),

    # 2. Active voice assertions: [Agent/Subject] + [Verb] + [Object: order/groceries/items]
    # Matches: "placed your order", "placed an order for you", "confirmed your order", "ordered your items",
    #          "completed your order", "booked your groceries", "submitted your order to Swiggy", "accepted your order",
    #          "dispatched your order", "delivered your groceries", "fulfilled your order", "shipped your items"
    # Rejects: "could not place your order", "have not placed your order", "to place your order", "would you like to place"
    re.compile(
        r"(?i)\b(?<!not )(?<!n\'t )(?<!never )"
        r"(?:placed|confirmed|booked|completed|submitted|processed|dispatched|delivered|fulfilled|shipped|sent|ordered|accepted)"
        r"\s+(?:an?\s+(?:grocery\s+)?order(?:\s+(?:for\s+you|with\s+\w+))?|"
        r"(?:your|the|this)\s+(?:grocery\s+)?(?:order|groceries|items|basket|purchase)|"
        r"everything)\b"
    ),

    # 3. Order success adjectives / predicates: [order/purchase] + [was/is/has] + [successful/succeeded]
    # Matches: "order was successful", "order successful", "order has succeeded", "Your order was successful!"
    # Rejects: "order was not successful", "order wasn't successful"
    re.compile(
        r"(?i)\b(?<!no )(?<!not )(?<!n\'t )"
        r"(?:your|the|this)?\s*(?:order|purchase)\s+"
        r"(?:(?:has|have|is|was)\s+)?(?:successful|succeeded)\b"
    ),

    # 4. Idiomatic completion: [order/payment/purchase] + [went/gone through]
    # Matches: "order went through", "order has gone through", "your order went through"
    # Rejects: "order failed to go through", "order did not go through", "order didn't go through"
    re.compile(
        r"(?i)\b(?<!no )(?<!not )(?<!n\'t )"
        r"(?:your|the|this)?\s*(?:order|payment|purchase)\s+"
        r"(?:(?:has|have)\s+)?(?:went|gone)\s+through\b"
    ),

    # 5. En route / In-transit / In-preparation assertions
    # Matches: "groceries are on their way", "delivery is on its way", "order is on the way",
    #          "groceries are en route", "order is being prepared", "Swiggy is preparing your order",
    #          "Your delivery partner is on the way."
    # Rejects: "Swiggy is experiencing high demand and cannot take this order"
    re.compile(
        r"(?i)\b(?<!no )(?<!not )(?<!n\'t )"
        r"(?:(?:your|the|this)?\s*(?:order|groceries|items|delivery|basket|delivery partner)\s+"
        r"(?:are|is|will\s+be|now)\s+"
        r"(?:(?:on\s+(?:the|its|their)\s+way)|(?:en\s+route)|(?:heading\s+your\s+way)|(?:headed\s+your\s+way)|"
        r"(?:out\s+for\s+delivery)|(?:being\s+(?:delivered|prepared|packed))|(?:arriving\s+(?:soon|shortly|\w+)))|"
        r"Swiggy\s+is\s+preparing\s+your\s+order)\b"
    ),

    # 6. Standalone adverbial confirmations: [successfully] + [participle] or [participle] + [successfully]
    # Matches: "successfully placed", "order completed successfully", "items have been ordered successfully"
    # Rejects: "not successfully placed"
    re.compile(
        r"(?i)\b(?<!not )(?<!n\'t )(?<!never )"
        r"(?:successfully\s+(?:placed|ordered|confirmed|booked|completed|processed|submitted|dispatched|delivered|fulfilled|shipped|sent)|"
        r"(?:placed|ordered|confirmed|booked|completed|processed|submitted|dispatched|delivered|fulfilled|shipped|sent)\s+successfully)\b"
    ),
)


def _claims_order_success(text: str) -> bool:
    """Return True if text asserts or implies that an order has been successfully placed, confirmed, or is en route."""
    if not text or not text.strip():
        return False
    return any(pattern.search(text) is not None for pattern in _ORDER_SUCCESS_PATTERNS)


def _explains_failure(
    text: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> bool:
    """Return True if text provides an honest explanation of a failure or contains error context."""
    if not text or not text.strip():
        return False
    lowered = text.casefold()
    if error_code and error_code.casefold() in lowered:
        return True
    if error_message and error_message.casefold() in lowered:
        return True
    failure_indicators = (
        "could not",
        "couldn't",
        "cannot",
        "can't",
        "unable",
        "failed",
        "failure",
        "error",
        "sorry",
        "unfortunately",
        "out of stock",
        "unavailable",
        "high demand",
        "issue",
        "problem",
        "unserviceable",
        "not available",
        "expired",
    )
    return any(ind in lowered for ind in failure_indicators)




class GroceryAgentEngine:
    """Conversational ReAct agent driving Swiggy Instamart through Gemini function calling."""

    def __init__(
        self,
        commerce: CommercePort,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 25.0,
    ) -> None:
        self.commerce = commerce
        self.tools = SwiggyAgentTools(commerce)
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout = timeout
        # In-memory session history keyed by customer_id
        self._history: dict[str, list[dict[str, Any]]] = {}
        # Track selected address per customer
        self._customer_address: dict[str, str] = {}
        self._customer_address_label: dict[str, str] = {}
        # Track pending checkout confirmation per customer
        self._pending_checkout: dict[str, bool] = {}
        # Track last interaction timestamp per customer for session inactivity detection
        self._last_interaction_time: dict[str, float] = {}
        # Per-customer concurrency locks to serialize rapid-fire incoming messages
        self._locks: dict[str, asyncio.Lock] = {}
        # Pacing timestamp for rate-limit protection
        self._last_call_time: float = 0.0
        # Telemetry for health and debugging
        self.last_gemini_error: Optional[str] = None
        self.last_turn_latency_ms: Optional[float] = None
        # Persistent HTTP client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None

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

    def _connect_url(self) -> str:
        base_url = (settings.CONNECT_BASE_URL or "https://grocerr.vercel.app").rstrip("/")
        return f"{base_url}/"

    def _auth_expired_response(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        return NormalizedOutgoingResponse(
            recipient_id=message.sender_id,
            channel=message.channel,
            text=(
                "Your Swiggy login has expired. Please tap the link below to reconnect your Swiggy Instamart account so I can manage your groceries:\n\n"
                f"👉 {self._connect_url()}\n\n"
                "Once connected, message me again and we'll pick right back up!"
            ),
            conversation_state="AUTH_REQUIRED",
        )

    def get_history(self, customer_id: str) -> list[dict[str, Any]]:
        if customer_id not in self._history:
            self._history[customer_id] = []
        return self._history[customer_id]

    def _prune_history(self, customer_id: str, max_user_turns: int = 4) -> None:
        """Keep conversation history bounded by whole user turn boundaries and compact past search returns."""
        hist = self._history.get(customer_id, [])
        if not hist:
            return

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

        # Compact bulky product search returns from older turns
        for entry in hist[:-2]:
            if entry.get("role") == "user" and "parts" in entry:
                for part in entry["parts"]:
                    fn_resp = part.get("functionResponse", {})
                    content = fn_resp.get("response", {}).get("content", {})
                    if isinstance(content, dict) and "products" in content and len(content.get("products", [])) > 2:
                        content["products"] = [
                            {"name": p.get("name"), "spin_id": p.get("spin_id"), "unit_price": p.get("unit_price")}
                            for p in content["products"][:2]
                        ]

    async def _poll_payment_status(
        self,
        *,
        order_id: str,
        recipient_id: str,
        channel: ChannelType,
        customer_id: str,
        max_attempts: int = 12,
        interval_seconds: float = 5.0,
    ) -> None:
        """Poll Swiggy order tracking every 5s for up to 60s to notify customer when payment completes."""
        logger.info("Starting background payment poller for order_id=%s", order_id)
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
        """Process one WhatsApp turn through the autonomous Gemini agent loop with per-customer serialization."""
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
            with self.commerce.customer_scope(customer_id):
                result = await self._process_scoped_message(message, customer_id)
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

        # Handle interactive button callbacks
        incoming_text = message.text.strip()
        if message.interactive_id:
            if message.interactive_id == "confirm_order":
                incoming_text = "Yes, please confirm and place the order now."
            elif message.interactive_id == "modify_cart":
                incoming_text = "I would like to change something in my cart."
            elif message.interactive_id in ("start_fresh", "clear_cart"):
                incoming_text = "Please clear my cart and start fresh."

        norm_text = incoming_text.casefold().strip("!.? \t\n")

        # Fast-path 1: Reset / Clear basket command
        _RESET_COMMANDS = {
            "start over",
            "start fresh",
            "clear cart",
            "clear my cart",
            "empty cart",
            "empty my cart",
            "clear basket",
            "clear the cart",
            "reset",
            "reset cart",
            "please clear my cart and start fresh.",
            "please clear my cart and start fresh",
        }
        if norm_text in _RESET_COMMANDS:
            try:
                await self.tools.clear_cart()
            except Exception as exc:
                logger.warning("Fast-path clear_cart failed: %s", exc)
            self._history[customer_id] = []
            return NormalizedOutgoingResponse(
                recipient_id=message.sender_id,
                channel=message.channel,
                text="🗑️ *Basket Cleared!*\n\nYour basket is now completely empty. What groceries can I get for you today?",
                conversation_state="READY",
            )

        # Explicit Human Confirmation Detection (Server-side safety gate)
        _EXPLICIT_CONFIRM_PATTERNS = re.compile(
            r"(?i)\b("
            r"confirm|confirm order|place order|place this order|order place karo|"
            r"theek hai order confirm karo|theek hai order confirm|yes please confirm|"
            r"yes confirm|yes place|proceed to pay|reply confirm|i explicitly confirm|"
            r"proceed with order|complete order|konfirm order|yes, please confirm and place the order now|"
            r"order confirm"
            r")\b"
        )
        user_confirmed = (
            message.interactive_id == "confirm_order"
            or bool(_EXPLICIT_CONFIRM_PATTERNS.search(incoming_text))
        )

        # Inspect current live cart
        current_cart: Optional[CommerceCart] = None
        try:
            current_cart = await self.commerce.get_cart()
        except Exception as exc:
            logger.debug("Failed to fetch initial cart for customer=%s: %s", customer_id, exc)

        # Fast-path 2: Hesitation guard when active basket exists
        _HESITATION_PHRASES = {
            "no",
            "wait",
            "hold on",
            "not yet",
            "stop",
            "don't place it",
            "not now",
            "pause",
            "wait a minute",
            "hold",
            "no thanks",
            "no not yet",
            "wait wait",
            "no wait",
            "nope",
        }
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
        current_time = asyncio.get_running_loop().time()
        last_seen = self._last_interaction_time.get(customer_id)
        self._last_interaction_time[customer_id] = current_time
        if last_seen is not None and (current_time - last_seen) > 1800:
            if not current_cart or not current_cart.items:
                history = []
                self._history[customer_id] = history

        # Detect address selection from text or context
        address_id = self._customer_address.get(customer_id)
        if not address_id:
            try:
                addr_res = await self.tools.get_saved_addresses(customer_id)
                if addr_res.get("error") == "AUTH_EXPIRED":
                    return self._auth_expired_response(message)
                if addr_res.get("success") and addr_res.get("addresses"):
                    addresses = addr_res["addresses"]
                    # Prioritize customer's Swiggy default address, fallback to first saved address
                    default_addr = next((a for a in addresses if a.get("is_default")), addresses[0])
                    address_id = default_addr["address_id"]
                    self._customer_address[customer_id] = address_id
                    self._customer_address_label[customer_id] = (
                        default_addr.get("clean_address") or default_addr.get("label") or "Home"
                    )
            except Exception:
                pass

        # Append user message
        history.append({
            "role": "user",
            "parts": [{"text": incoming_text}],
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

        for _ in range(max_iterations):
            response_data = await self._call_gemini(
                history,
                address_id=address_id,
                address_label=addr_lbl,
                cart=current_cart,
            )
            if not response_data:
                final_text = "I'm having a brief connection hiccup. Please try again in a moment."
                break

            candidates = response_data.get("candidates", [])
            if not candidates:
                final_text = "I couldn't process that request right now. Please tell me what you'd like to do."
                break

            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Check if Gemini invoked function calls
            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            # If no function call, we have the final assistant message
            if not function_calls:
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                final_text = "\n".join(t.strip() for t in text_parts if t.strip())
                # Append assistant response to history
                history.append({
                    "role": "model",
                    "parts": parts,
                })
                break

            # Append model's thought / function calls to history
            history.append({
                "role": "model",
                "parts": parts,
            })

            # Execute function calls concurrently and collect responses
            async def _execute_single_call(call: dict[str, Any]) -> tuple[dict[str, Any], bool, bool, dict[str, Any] | None]:
                fn_name = call.get("name")
                fn_args = call.get("args", {})
                call_id = call.get("id")

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

            executed_calls = await asyncio.gather(*[_execute_single_call(c) for c in function_calls])
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
                return self._auth_expired_response(message)

            # Send tool responses back to model in the next turn
            history.append({
                "role": "user",
                "parts": tool_responses,
            })

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
                else:
                    error_msg = checkout_result.get("error") or checkout_result.get("message") or "Provider checkout error"
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
                    else:
                        if disclaimer not in final_text:
                            final_text = f"{final_text.rstrip()}\n\n{disclaimer}"
                    conv_state = "FAILED"
            else:
                out_order_id = checkout_result.get("order_id")
                out_order_total = checkout_result.get("grand_total")
                out_bridge_url = checkout_result.get("bridge_url")
                upi_url = checkout_result.get("upi_intent_url")
                status = checkout_result.get("status")

                if status == "PAYMENT_PENDING":
                    conv_state = "AWAITING_PAYMENT"
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
                else:
                    conv_state = "READY"
        else:
            # Post-process: Add interactive buttons if cart summary is ready for confirmation
            if address_changed and last_cart_receipt:
                amnesiac_phrases = (
                    "what would you like to order",
                    "what can i get for you",
                    "what do you want to order",
                    "how can i help with your groceries",
                    "what groceries",
                    "what would you like",
                )
                is_amnesiac = any(p in final_text.casefold() for p in amnesiac_phrases)
                receipt_missing = "🛒 *your basket" not in final_text.casefold()
                if is_amnesiac or receipt_missing:
                    logger.info(
                        "Deterministic address-change guard triggered: ensuring receipt is presented for %s",
                        addr_lbl,
                    )
                    final_text = (
                        f"I've updated your delivery address to *{addr_lbl}*! 📍\n\n"
                        f"{last_cart_receipt}"
                    )
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
        logger.info("Executing agent tool call: %s with args: %s", name, args)
        if name == "get_saved_addresses":
            return await self.tools.get_saved_addresses(customer_id)
        elif name == "select_delivery_address":
            res = await self.tools.select_delivery_address(customer_id, args.get("address_id", ""))
            if res.get("success") and res.get("address_id"):
                self._customer_address[customer_id] = res["address_id"]
                self._customer_address_label[customer_id] = (
                    res.get("clean_address") or res.get("label") or "Selected Address"
                )
            return res
        elif name == "search_products":
            addr = args.get("address_id") or address_id
            return await self.tools.search_products(args.get("query", ""), address_id=addr)
        elif name == "get_cart":
            loc = self._customer_address_label.get(customer_id, "Home")
            return await self.tools.get_cart(delivery_location=loc)
        elif name == "update_cart":
            addr = args.get("address_id") or address_id
            loc = self._customer_address_label.get(customer_id, "Home")
            return await self.tools.update_cart(
                args.get("items", []), address_id=addr or "", delivery_location=loc
            )
        elif name == "clear_cart":
            return await self.tools.clear_cart()
        elif name == "checkout":
            # Deterministic Server-Side Invariant Gate:
            # If user_confirmed is provided by message processor, enforce human confirmation.
            # If None (direct unit test invocation of _execute_tool), respect args is_user_confirmed.
            if user_confirmed is None:
                effective_confirmed = bool(args.get("is_user_confirmed", False))
            else:
                effective_confirmed = bool(user_confirmed and args.get("is_user_confirmed", False))
            return await self.tools.checkout(
                cart_id=args.get("cart_id", ""),
                address_id=args.get("address_id", "") or address_id or "",
                payment_method=args.get("payment_method", "UPI"),
                payment_option_kind=args.get("payment_option_kind", "qr"),
                is_user_confirmed=effective_confirmed,
            )
        elif name == "track_order":
            return await self.tools.track_order(args.get("order_id", ""))
        return {"error": f"Unknown tool: {name}"}

    async def _call_gemini(
        self,
        contents: list[dict[str, Any]],
        *,
        address_id: Optional[str] = None,
        address_label: Optional[str] = None,
        cart: Optional[CommerceCart] = None,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        """Perform one HTTP POST request to Gemini v1beta generateContent using pooled connection."""
        # Pacing protection against rapid burst rate limits
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_call_time
        if elapsed < 0.6:
            await asyncio.sleep(0.6 - elapsed)
        self._last_call_time = asyncio.get_running_loop().time()

        system_text = _SYSTEM_PROMPT
        loc = address_label or "Saved Delivery Address"
        if address_id:
            system_text += (
                f"\n\n### ACTIVE DELIVERY CONTEXT (PRE-SELECTED):\n"
                f"- Active delivery address is already selected: {loc} (ID: `{address_id}`).\n"
                f"- You do NOT need to call `get_saved_addresses` or `select_delivery_address` unless the customer explicitly requests to change their address."
            )

        if cart and cart.items:
            items_summary = ", ".join(
                f"{it.quantity}x {it.name} ({_format_inr(it.total_price)})"
                for it in cart.items
            )
            delivery_str = "FREE (₹0)" if cart.delivery_fee == 0.0 else _format_inr(cart.delivery_fee)
            system_text += (
                f"\n\n### LIVE BASKET STATE (ACTIVE ON SWIGGY INSTAMART):\n"
                f"- Active Basket Item Count: {len(cart.items)}\n"
                f"- Basket Contents: {items_summary}\n"
                f"- Subtotal: {_format_inr(cart.item_total)}\n"
                f"- Delivery Fee: {delivery_str}\n"
                f"- Grand Total: {_format_inr(cart.grand_total)}\n"
                f"- Delivery Destination: {loc} (ID: `{address_id}`)\n"
                f"- CRITICAL INVARIANT: The customer already has these {len(cart.items)} items in their basket. "
                f"Never assume the basket is empty. If the delivery address changed, immediately show the updated receipt and ask for confirmation. "
                f"Never ask 'what would you like to order?' when there are already items in the basket."
            )
        else:
            system_text += (
                f"\n\n### LIVE BASKET STATE:\n"
                f"- The basket is currently empty (0 items).\n"
            )

        url = f"{_API_ROOT}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "tools": [{"functionDeclarations": GEMINI_TOOL_DECLARATIONS}],
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        max_retries = 6
        backoff = 5.0
        client = await self._get_client()

        for attempt in range(max_retries):
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    sleep_time = float(retry_after) if retry_after else backoff
                    logger.warning(
                        "Gemini 429 rate limit encountered. Retrying in %.1fs (attempt %d/%d)...",
                        sleep_time,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(sleep_time)
                    backoff = min(backoff * 1.8, 25.0)
                    continue

                if resp.status_code == 400 and len(contents) > 1:
                    logger.warning(
                        "Gemini 400 invalid argument on multi-turn history (%s). Self-healing by retrying from last user turn.",
                        resp.text[:200],
                    )
                    # Find last user text message index
                    last_user_idx = max(
                        (
                            i
                            for i, entry in enumerate(contents)
                            if entry.get("role") == "user"
                            and any("text" in p for p in entry.get("parts", []))
                        ),
                        default=len(contents) - 1,
                    )
                    salvaged = contents[last_user_idx:]
                    contents.clear()
                    contents.extend(salvaged)
                    payload["contents"] = salvaged
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        return resp.json()

                if resp.status_code != 200:
                    err_text = f"HTTP {resp.status_code}: {resp.text[:300]}"
                    logger.error("Gemini API returned %s", err_text)
                    self.last_gemini_error = err_text
                    return None
                return resp.json()
            except Exception as exc:
                err_text = f"Exception: {type(exc).__name__} - {exc}"
                logger.error("Gemini request failed on attempt %d: %s", attempt + 1, exc)
                self.last_gemini_error = err_text
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(backoff)
        return None
