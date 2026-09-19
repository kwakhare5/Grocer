"""Autonomous Gemini ReAct agent engine for Swiggy Instamart grocery ordering."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.parse import quote

import httpx

from backend.agent.tools import GEMINI_TOOL_DECLARATIONS, SwiggyAgentTools
from backend.channels.models import (
    ChannelType,
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.config import settings
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.engine")

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

_SYSTEM_PROMPT = """You are GROCER, a delightful, lightning-fast WhatsApp grocery concierge powered by Swiggy Instamart.
Your goal is to get the customer's groceries delivered to their doorstep with zero friction.

### CONVERSATION & TONE RULES:
1. Speak in warm, concise, natural English formatted specifically for WhatsApp readability.
2. Use clear spacing, bullet points, and WhatsApp markdown (*bold* for emphasis). Never use raw markdown tables or raw JSON.
3. Keep responses brief. Avoid robot fluff, corporate disclaimers, or repetitive pleasantries.

### PRODUCT SEARCH & SELECTION (HYBRID RESOLUTION):
- **Everyday Staples** (milk, brown bread, white bread, eggs, butter, curd, onions, potatoes, tomatoes, atta):
  Search Swiggy, automatically pick the top standard in-stock variant (e.g., Amul Taaza 500ml, Britannia Whole Wheat Bread 400g, Farm Fresh Eggs 6-pack), add it directly to the cart, and notify the user with a single clean basket receipt.
- **Variant-Rich or Ambiguous Requests** (chocolates, biscuits, ice cream, shampoo, chips, cold drinks, snacks):
  Search Swiggy and present the top 2-3 in-stock options with number, name, pack size, and price:
  Example:
  "I found a few options for Dairy Milk:
  1. Cadbury Dairy Milk Silk (60g) — ₹90
  2. Cadbury Dairy Milk Crackle (36g) — ₹50
  3. Cadbury Dairy Milk Fruit & Nut (36g) — ₹50
  Which one would you like?"
- **Brand & Diet Constraints**: Strictly respect dietary preferences (e.g. vegetarian, vegan, gluten-free) and brand requests. If an item is out of stock, suggest the closest in-stock substitute conversationally.

### ZERO-REDUNDANCY & RECEIPT RULES:
- NEVER repeat item names or lists in your message. Never write "I have added X, Y" and then list X, Y again under the basket.
- Present items EXACTLY ONCE inside the clean receipt card.
- Collapse fees into a single line (*Delivery & Fees:* ₹21) or include it cleanly.
- Keep the entire basket message under 10 lines so it fits on any smartphone screen without scrolling:

🛒 *Your Basket (Pune Kingsbury)*
• {quantity}x {item_name} ({pack_size}) — {price}
...

*Subtotal:* {formatted_item_total}
*Delivery & Fees:* {formatted_total_fees}
*Grand Total:* {formatted_grand_total}

📍 *Delivering to:* {street_address}
👉 Reply *Confirm* to place order, or tell me what to change!

### CHECKOUT & UPI PAYMENT FLOW:
1. NEVER call `checkout` until the customer has explicitly approved the basket (e.g. said "Confirm", "Yes", "Place order", or tapped Confirm Order).
2. When the user confirms, call `checkout` with `payment_method='UPI'`, `payment_option_kind='qr'`, and `is_user_confirmed=true`.
3. When `checkout` returns `PAYMENT_PENDING` with a UPI payment link (`bridge_url` or `upi_intent_url`):
   Present the payment link clearly:
   🎉 *Order Created!*
   *Grand Total:* {formatted_grand_total}

   Tap the link below to pay via UPI (GPay / PhonePe / Paytm):
   👉 [Pay {formatted_grand_total} via UPI]({payment_link})

   Once paid, Swiggy Instamart will pack and deliver your groceries in ~15-20 mins!
4. If checkout fails, explain the exact reason honestly. NEVER claim an order was placed if checkout was unsuccessful.

### ORDER TRACKING FLOW:
- If the user asks where their order is ("where is my order?", "track order #..."):
  Call `track_order` with their `order_id` (or the last placed order ID).
  Report order status, ETA, and delivery partner details cleanly:
  "🛵 *Order Status: {status}*
  ETA: ~{eta_minutes} mins
  Delivery Partner: {rider_name}"
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
        # Track pending checkout confirmation per customer
        self._pending_checkout: dict[str, bool] = {}

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

    async def handle_message(
        self, message: NormalizedIncomingMessage
    ) -> NormalizedOutgoingResponse:
        """Process one WhatsApp turn through the autonomous Gemini agent loop."""
        customer_id = message.customer_id or message.sender_id
        with self.commerce.customer_scope(customer_id):
            return await self._process_scoped_message(message, customer_id)

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
            elif message.interactive_id == "start_fresh":
                incoming_text = "Please clear my cart and start fresh."

        # Detect address selection from text or context
        address_id = self._customer_address.get(customer_id)
        if not address_id:
            try:
                addr_res = await self.tools.get_saved_addresses(customer_id)
                if addr_res.get("error") == "AUTH_EXPIRED":
                    return self._auth_expired_response(message)
                if addr_res.get("success") and addr_res.get("addresses"):
                    addresses = addr_res["addresses"]
                    # Smart Pune Default: prioritize Kingsbury / Pune / Charholi
                    pune_addr = next(
                        (
                            a
                            for a in addresses
                            if any(
                                k in (a.get("label", "") + " " + a.get("street", "") + " " + a.get("city", "")).casefold()
                                for k in ("kingsbury", "pune", "charholi")
                            )
                        ),
                        None,
                    )
                    default_addr = pune_addr or next((a for a in addresses if a.get("is_default")), addresses[0])
                    address_id = default_addr["address_id"]
                    self._customer_address[customer_id] = address_id
            except Exception:
                pass

        # Append user message
        history.append({
            "role": "user",
            "parts": [{"text": incoming_text}],
        })

        # Bounded ReAct loop (up to 6 function call steps)
        max_iterations = 6
        final_text = ""
        actions: list[InteractiveAction] = []
        checkout_executed = False
        checkout_result: dict[str, Any] | None = None

        for _ in range(max_iterations):
            response_data = await self._call_gemini(history, address_id=address_id)
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

            # Execute each function call and collect responses
            tool_responses = []
            auth_failed = False

            for call in function_calls:
                fn_name = call.get("name")
                fn_args = call.get("args", {})
                call_id = call.get("id")

                # Inject default address_id if omitted by the model
                if "address_id" in fn_args and not fn_args["address_id"] and address_id:
                    fn_args["address_id"] = address_id

                tool_result = await self._execute_tool(
                    fn_name, fn_args, customer_id=customer_id, address_id=address_id
                )

                if fn_name == "checkout":
                    checkout_executed = True
                    checkout_result = tool_result

                if isinstance(tool_result, dict) and tool_result.get("error") == "AUTH_EXPIRED":
                    auth_failed = True

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

                tool_responses.append(tool_response_part)

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
                elif status == "ORDER_PLACED":
                    conv_state = "ORDER_PLACED"
                else:
                    conv_state = "READY"
        else:
            # Post-process: Add interactive buttons if cart summary is ready for confirmation
            if any(
                phrase in final_text.casefold()
                for phrase in (
                    "place this order",
                    "confirm order",
                    "shall i place",
                    "would you like me to place",
                    "reply *confirm*",
                    "reply confirm",
                    "place order",
                )
            ):
                actions = [
                    InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
                    InteractiveAction(action_type="button", id="modify_cart", title="Change Items"),
                ]
                conv_state = "AWAITING_CHECKOUT_CONFIRMATION"

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
    ) -> Any:
        """Dispatch a single function call to SwiggyAgentTools."""
        logger.info("Executing agent tool call: %s with args: %s", name, args)
        if name == "get_saved_addresses":
            return await self.tools.get_saved_addresses(customer_id)
        elif name == "select_delivery_address":
            res = await self.tools.select_delivery_address(customer_id, args.get("address_id", ""))
            if res.get("success") and res.get("address_id"):
                self._customer_address[customer_id] = res["address_id"]
            return res
        elif name == "search_products":
            addr = args.get("address_id") or address_id
            return await self.tools.search_products(args.get("query", ""), address_id=addr)
        elif name == "get_cart":
            return await self.tools.get_cart()
        elif name == "update_cart":
            addr = args.get("address_id") or address_id
            return await self.tools.update_cart(args.get("items", []), address_id=addr or "")
        elif name == "clear_cart":
            return await self.tools.clear_cart()
        elif name == "checkout":
            return await self.tools.checkout(
                cart_id=args.get("cart_id", ""),
                address_id=args.get("address_id", "") or address_id or "",
                payment_method=args.get("payment_method", "UPI"),
                payment_option_kind=args.get("payment_option_kind", "qr"),
                is_user_confirmed=args.get("is_user_confirmed", False),
            )
        elif name == "track_order":
            return await self.tools.track_order(args.get("order_id", ""))
        return {"error": f"Unknown tool: {name}"}

    async def _call_gemini(
        self, contents: list[dict[str, Any]], *, address_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Perform one HTTP POST request to Gemini v1beta generateContent."""
        url = f"{_API_ROOT}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": contents,
            "tools": [{"functionDeclarations": GEMINI_TOOL_DECLARATIONS}],
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.error("Gemini API returned status %d: %s", resp.status_code, resp.text[:300])
                    return None
                return resp.json()
        except Exception as exc:
            logger.error("Gemini request failed: %s", exc)
            return None
