"""
LangGraph Restock Agent — Task 2.5
Stateful multi-turn agent for the WhatsApp grocery restock flow.

Graph nodes:
  1. generate_alert    — Writes a WhatsApp low-stock alert message via LLM
  2. parse_reply       — Interprets user reply to a stock-check alert (YES/NO/partial)
  3. parse_order_intent — Parses a direct order request (e.g. "2 milk, eggs")
  4. reset_to_order    — Cancels current flow and returns to order prompt
  5. build_cart        — Searches MCP catalog and builds the PreFill cart
  6. place_order       — Places the order via MCP

State transitions:
  generate_alert    → END              (alert sent; await async reply via webhook)
  parse_reply       → build_cart       (user confirmed items)
  parse_reply       → END              (user declined)
  parse_order_intent → confirm_add_to_cart stage → build_cart
  reset_to_order    → awaiting_order stage
  build_cart        → place_order      (cart built)
  build_cart        → END              (no items found)
  place_order       → END

Why LangGraph?
  The restock flow is a multi-turn conversation over WhatsApp. Between the
  initial alert and the user's reply, minutes or hours may pass. LangGraph
  gives us explicit state management so we can serialize state to DB, resume
  from any node, and handle partial/ambiguous replies gracefully.
"""

import json
import logging
import string
from typing import Optional

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from backend.mcp.client import mcp_client

logger = logging.getLogger(__name__)


from backend.ml.text_matching import is_fuzzy_match
from backend.agents.llm_client import get_llm
from langchain_core.messages import HumanMessage

# ---------------------------------------------------------------------------
# Agent State — everything the graph needs to track across nodes
# ---------------------------------------------------------------------------
class RestockState(TypedDict):
    household_id: str
    depleting_items: list           # list of dicts with item_name, confidence_score, days_remaining
    stage: str                      # greeting | awaiting_order | confirm_add_to_cart | alert | awaiting_reply | building_cart | awaiting_confirm | done
    user_message: Optional[str]     # the raw WhatsApp text from the user
    confirmed_items: list           # subset of depleting_items the user said YES to
    confirmed_quantities: dict      # item_name -> quantity mapping for direct orders
    cart_id: Optional[str]
    cart_total: Optional[float]
    order_id: Optional[str]
    response_message: str           # the message to send back via WhatsApp
    error: Optional[str]


# ---------------------------------------------------------------------------
# Node 1: Generate Alert Message
# ---------------------------------------------------------------------------
async def generate_alert_message(state: RestockState) -> dict:
    """
    Use Claude to write a natural, friendly WhatsApp alert message listing
    items that are predicted to run out soon.

    Why Claude instead of a template?
      Templates sound robotic. Claude writes messages that feel like a helpful
      human assistant: "Hey! Looks like your cooking oil might run out in ~2 days."
      This is one of the three Claude API uses defined in CLAUDE.md Part 3.
    """
    from backend.seed.catalog import lookup_catalog_item

    detailed_lines = []
    total_amount = 0.0
    for i in state["depleting_items"]:
        item_name = i.get("item_name") or i.get("name") or "Unknown Item"
        cat = lookup_catalog_item(item_name)
        
        name = cat["name"] if cat else item_name
        price = cat["price"] if cat else 0.0
        category = cat["category"] if cat else "unknown"
        unit = cat["unit"] if cat else "N/A"
        qty = 1
        
        total_amount += price * qty
        conf = int(i.get('confidence_score', 0.5) * 100)
        days = round(i.get('days_remaining', 1.0), 1)
        
        detailed_lines.append(
            f"- {name} (Qty: {qty}) - Price: ₹{price:.0f} (Category: {category}, Unit: {unit}, Confidence: {conf}%, Days remaining: {days})"
        )
        
    items_text = "\n".join(detailed_lines)

    message = None

    try:
        prompt = (
            f"You are a smart household assistant for PreFill.\n\n"
            f"Items likely running low:\n{items_text}\n\n"
            f"Write a WhatsApp message under 150 words. You MUST list all items from the list above, showing for each item:\n"
            f"- Its whole name\n"
            f"- Qty: 1\n"
            f"- Price (e.g. ₹X)\n"
            f"- Unit and Category\n"
            f"- Confidence % and Days remaining\n\n"
            f"At the end of the item list, calculate and mention the estimated total amount (Estimated Total: ₹{total_amount:.0f}).\n"
            f"Be friendly but brief. Max 2 emojis. End with: "
            f"'Would you like to order them?' "
            f"Mention this is based on their purchase pattern. Write ONLY the message."
        )
        llm = get_llm()
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        message = resp.content
    except Exception as e:
        logger.error(f"LLM API error in generate_alert: {e}")

    if not message:
        # Fallback to a template if Claude, Groq, and NVIDIA are unavailable
        item_lines = "\n".join([
            f"• {line[2:]}" if line.startswith("- ") else f"• {line}"
            for line in detailed_lines
        ])
        message = (
            f"🛒 Based on your purchase patterns, you're running low on:\n\n"
            f"{item_lines}\n\n"
            f"Estimated Total: ₹{total_amount:.0f}\n\n"
            f"Would you like to order them?"
        )

    return {
        "response_message": message,
        "stage": "awaiting_reply",
    }


# ---------------------------------------------------------------------------
# Node 2: Parse User Reply
# ---------------------------------------------------------------------------
async def parse_user_reply(state: RestockState) -> dict:
    """
    Interpret the user's WhatsApp reply. Three cases:
      1. Clear YES → confirm all items
      2. Clear NO  → dismiss, check again tomorrow
      3. Ambiguous → use Claude to parse which items they want

    Why Claude for case 3?
      Users say things like "just the oil and milk", "skip eggs", "get the basics".
      A regex can't handle this. Claude can. (CLAUDE.md Part 3, use case #3)
    """
    # 0. Check if order is already completed
    if state.get("stage") == "done":
        return {
            "response_message": "Your order has already been placed successfully! 👍 If you want to check for new low-stock items, type check.",
            "stage": "done"
        }

    msg = (state.get("user_message") or "").strip().upper()

    # Case 1: Clear affirmative
    if msg in ["YES", "Y", "REORDER", "ORDER ALL", "OK", "OKAY", "YES PLEASE", "YEP", "SURE", "CONFIRM", "CONFIRMED", "PLACE", "PLACE ORDER", "PROCEED"]:
        return {
            "confirmed_items": state["depleting_items"],
            "stage": "building_cart",
        }

    # Case 2: Clear negative
    if msg in ["NO", "NOPE", "CANCEL", "SKIP", "NOT NOW", "LATER", "N"]:
        return {
            "confirmed_items": [],
            "response_message": "Got it! I'll check again tomorrow. 👍",
            "stage": "done",
        }

    # Case 3: Ambiguous — ask LLM to parse which items they want
    active_items = state.get("confirmed_items") or state["depleting_items"]
    items_list = "\n".join([f"- {i['item_name']}" for i in active_items])
    wanted = None
    unrecognized = False

    try:
        prompt = (
            f"The user has these items in their cart:\n{items_list}\n\n"
            f"Their reply: \"{state['user_message']}\"\n\n"
            f"Analyze their reply and return a JSON object with two keys:\n"
            f"1. 'wanted': a list of item names they want to keep or add to the cart. By default, they want to keep all items in their cart unless they specify to skip or remove some.\n"
            f"2. 'unrecognized': a boolean. Set to true ONLY if their reply is completely unrelated garbage, gibberish, or unrelated chit-chat (e.g. 'hello', 'who are you', 'testing'). If they are confirming, rejecting, or editing items, set it to false.\n"
            f"ONLY output valid JSON, like: {{\"wanted\": [\"item1\"], \"unrecognized\": false}}."
        )
        llm = get_llm().with_config({"response_format": {"type": "json_object"}})
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        parsed = json.loads(resp.content)
        wanted = parsed.get("wanted", [])
        unrecognized = parsed.get("unrecognized", False)
    except Exception as e:
        logger.error(f"LLM parse error: {e}")

    # If LLM parsed as unrecognized
    if unrecognized:
        return {
            "response_message": "Sorry, I didn't catch that. Reply YES to reorder all, or tell me what you want.",
            "stage": "awaiting_reply",
        }

    # If LLM succeeded in parsing
    if wanted is not None:
        confirmed = []
        from backend.seed.catalog import CATALOG
        for name in wanted:
            matched = False
            for dep_item in state["depleting_items"]:
                if name.lower() in dep_item["item_name"].lower() or dep_item["item_name"].lower() in name.lower():
                    if not any(c["item_name"] == dep_item["item_name"] for c in confirmed):
                        confirmed.append(dep_item)
                    matched = True
                    break
            if not matched:
                for cat_item in CATALOG:
                    cat_name = str(cat_item["name"])
                    if name.lower() in cat_name.lower() or cat_name.lower() in name.lower():
                        if not any(c["item_name"] == cat_item["name"] for c in confirmed):
                            confirmed.append({
                                "item_name": cat_item["name"],
                                "confidence_score": 1.0,
                                "days_remaining": 0.0
                            })
                        matched = True
                        break
            if not matched:
                if not any(c["item_name"].lower() == name.lower() for c in confirmed):
                    confirmed.append({
                        "item_name": name,
                        "confidence_score": 1.0,
                        "days_remaining": 0.0
                    })

        if confirmed:
            return {
                "confirmed_items": confirmed,
                "stage": "building_cart",
            }
        else:
            return {
                "confirmed_items": [],
                "response_message": "Got it! I'll check again tomorrow. 👍",
                "stage": "done",
            }

    # Case 4: Fallback keyword matching parser in case of Claude, Groq, and NVIDIA API issues
    try:
        user_msg_lower = (state.get("user_message") or "").lower()

        # 1. Check for complete negative
        if any(w in user_msg_lower for w in ["no", "nope", "cancel", "skip all", "no to all", "dont want"]):
            return {
                "confirmed_items": [],
                "response_message": "Got it! I'll check again tomorrow. 👍",
                "stage": "done",
            }

        # 2. Check for "only" or "just" restriction
        restrictive = False
        if any(w in user_msg_lower for w in ["just", "only", "solely"]):
            restrictive = True
            confirmed = []
        else:
            confirmed = list(state.get("confirmed_items") or state["depleting_items"])

        # Preprocess user words: strip all punctuation and exclude stopwords/short words
        user_words = [w.strip(string.punctuation).lower() for w in user_msg_lower.split()]
        user_words = [w for w in user_words if len(w) > 2]
        
        stopwords = {"add", "get", "need", "want", "skip", "dont", "don't", "please", "confirm", "confirmed"}
        search_words = [w for w in user_words if w not in stopwords]

        negation_words = ["skip", "no", "without", "delete", "remove", "dont", "don't", "exclude"]
        negated_items = []
        has_any_match = False
        
        # Check matching of depleting items with fuzzy matching support
        for i in state["depleting_items"]:
            name_lower = i["item_name"].lower()
            matched = False
            for uw in search_words:
                if is_fuzzy_match(uw, name_lower) or any(is_fuzzy_match(uw, part) for part in name_lower.split()):
                    matched = True
                    has_any_match = True
                    # Check if negation is close to this word
                    for neg in negation_words:
                        if f"{neg} {uw}" in user_msg_lower or f"{uw} {neg}" in user_msg_lower or user_msg_lower.startswith(neg):
                            if i not in negated_items:
                                negated_items.append(i)
                            break
                    break
        
        # Apply negations
        for i in negated_items:
            if i in confirmed:
                confirmed.remove(i)

        # If restrictive, add back explicitly mentioned depleting items
        if restrictive:
            for i in state["depleting_items"]:
                name_lower = i["item_name"].lower()
                matched = False
                for uw in search_words:
                    if is_fuzzy_match(uw, name_lower) or any(is_fuzzy_match(uw, part) for part in name_lower.split()):
                        # Check if negated
                        is_neg = False
                        for neg in negation_words:
                            if f"{neg} {uw}" in user_msg_lower or f"{uw} {neg}" in user_msg_lower:
                                is_neg = True
                                break
                        if not is_neg:
                            matched = True
                            break
                if matched and i not in negated_items:
                    if i not in confirmed:
                        confirmed.append(i)

        # 4. Check for additions from CATALOG
        from backend.seed.catalog import CATALOG
        for cat_item in CATALOG:
            cat_name_lower = str(cat_item["name"]).lower()
            matched = False
            for uw in search_words:
                if is_fuzzy_match(uw, cat_name_lower) or any(is_fuzzy_match(uw, part) for part in cat_name_lower.split()):
                    is_negated = False
                    for neg in negation_words:
                        if f"{neg} {uw}" in user_msg_lower or f"{uw} {neg}" in user_msg_lower:
                            is_negated = True
                            break
                    if not is_negated:
                        matched = True
                        has_any_match = True
                        break
            if matched:
                # check if already in confirmed
                if not any(str(c["item_name"]).lower() == str(cat_item["name"]).lower() for c in confirmed):
                    confirmed.append({
                        "item_name": cat_item["name"],
                        "confidence_score": 1.0,
                        "days_remaining": 0.0
                    })

        # Check if user sent negation words or clear affirmatives
        has_negation = any(neg in user_msg_lower for neg in negation_words)
        has_affirmative = any(aff in user_msg_lower for aff in ["yes", "ok", "yep", "sure", "reorder", "confirm", "proceed"])

        # If matched nothing, used no negations, and sent no clear affirmative words, treat as unrecognized
        if not has_any_match and not has_negation and not has_affirmative:
            return {
                "response_message": "Sorry, I didn't catch that. Reply YES to reorder all, or tell me what you want.",
                "stage": "awaiting_reply",
            }

        if confirmed:
            logger.info(f"Fallback keyword parser matched items: {[item['item_name'] for item in confirmed]}")
            return {
                "confirmed_items": confirmed,
                "stage": "building_cart",
            }

        return {
            "response_message": "Sorry, I didn't catch that. Reply YES to reorder all, or tell me what you want.",
            "stage": "awaiting_reply",
        }
    except Exception as e:
        logger.error(f"Fallback parser encountered unexpected error: {e}")
        return {
            "response_message": "Sorry, I didn't catch that. Reply YES to reorder all, or tell me what you want.",
            "stage": "awaiting_reply",
        }


# ---------------------------------------------------------------------------
# Node 2.5: Parse Direct Order Intent (new "What would you like to order?" flow)
# ---------------------------------------------------------------------------
async def parse_order_intent(state: RestockState) -> dict:
    """
    Parse the user's free-text order request (e.g. "2 milk, eggs, and orange").
    Extracts item names and quantities from the message, looks them up in the catalog,
    and reports matched/unmatched items before asking for cart confirmation.
    """
    from backend.seed.catalog import lookup_catalog_item
    import re

    user_msg = (state.get("user_message") or "").strip()

    # ----- Use LLM to extract (item, quantity) pairs -----
    extraction_prompt = (
        f"The user wants to order grocery items. Their message: \"{user_msg}\"\n\n"
        f"Extract all grocery item requests as a JSON array named 'items'. "
        f"Each element should have 'name' (the item name as spoken by the user) and 'qty' (integer quantity, default 1 if not specified).\n"
        f"If the message contains no grocery items at all (e.g. it's chit-chat, a question, or gibberish), return {{\"items\": [], \"not_an_order\": true}}.\n"
        f"ONLY output valid JSON. Example: {{\"items\": [{{\"name\": \"milk\", \"qty\": 2}}, {{\"name\": \"eggs\", \"qty\": 1}}], \"not_an_order\": false}}"
    )

    raw_items = None
    not_an_order = False

    try:
        llm = get_llm().with_config({"response_format": {"type": "json_object"}})
        resp = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
        parsed = json.loads(resp.content)
        raw_items = parsed.get("items", [])
        not_an_order = parsed.get("not_an_order", False)
    except Exception as e:
        logger.error(f"LLM extraction error in parse_order_intent: {e}")

    # Regex fallback: extract quantities + words if LLM unavailable
    if raw_items is None:
        not_an_order = False
        pattern = re.compile(r"(\d+)?\s*([a-zA-Z][a-zA-Z\s]+?)(?:,|and|$)", re.IGNORECASE)
        raw_items = []
        for m in pattern.finditer(user_msg):
            qty_str, name = m.group(1), m.group(2).strip()
            if name:
                raw_items.append({"name": name, "qty": int(qty_str) if qty_str else 1})

    if not_an_order or not raw_items:
        return {
            "response_message": (
                "Hmm, I didn't catch any items in that. "
                "Could you tell me what you'd like to order? "
                "For example: \"2 milk, eggs\"."
            ),
            "stage": "awaiting_order",
        }

    # ----- Match each raw item to the catalog -----
    matched = []   # list of {item_name, qty, price, category, unit}
    not_found = [] # list of user-spoken names that couldn't be matched

    for entry in raw_items:
        spoken_name = entry.get("name", "").strip()
        qty = max(1, int(entry.get("qty", 1)))
        cat = lookup_catalog_item(spoken_name)
        if cat:
            matched.append({
                "item_name": cat["name"],
                "qty": qty,
                "price": cat["price"],
                "category": cat["category"],
                "unit": cat["unit"],
            })
        else:
            not_found.append(spoken_name)

    if not matched:
        not_found_str = ", ".join(not_found)
        return {
            "response_message": (
                f"Sorry, I couldn't find {not_found_str} in our catalog. "
                f"What else would you like to order?"
            ),
            "stage": "awaiting_order",
        }

    # ----- Build confirmation message -----
    item_lines = []
    total = 0.0
    confirmed_items = []
    confirmed_quantities = {}

    for m in matched:
        line_total = m["price"] * m["qty"]
        total += line_total
        item_lines.append(
            f"• {m['item_name']} (Qty: {m['qty']}) — ₹{line_total:.0f} "
            f"({m['category']}, {m['unit']})"
        )
        confirmed_items.append({
            "item_name": m["item_name"],
            "confidence_score": 1.0,
            "days_remaining": 0.0,
        })
        confirmed_quantities[m["item_name"]] = m["qty"]

    items_text = "\n".join(item_lines)
    note = ""
    if not_found:
        note = f"\n\n(Note: I couldn't find {', '.join(not_found)} in our catalog.)"

    reply = (
        f"I found these items:\n{items_text}\n"
        f"Estimated Total: ₹{total:.0f}{note}\n\n"
        f"Would you like to add them to your cart?"
    )

    return {
        "confirmed_items": confirmed_items,
        "confirmed_quantities": confirmed_quantities,
        "response_message": reply,
        "stage": "confirm_add_to_cart",
    }


# ---------------------------------------------------------------------------
# Node 3: Build Cart
# ---------------------------------------------------------------------------
async def build_cart(state: RestockState) -> dict:
    """
    For each confirmed item, search the MCP catalog to get the current product
    listing, then add all items to a single PreFill cart.

    Why search before carting?
      The consumption model tracks item_ids (INS_001), but the cart needs the
      current live product listing. Prices may have changed. Searching first
      ensures we always use the latest catalog data.
    """
    if not state.get("confirmed_items"):
        return {
            "response_message": "Nothing to order — I'll check again tomorrow!",
            "stage": "done",
        }

    cart_items = []

    # Use confirmed_quantities from direct-order flow (parse_order_intent)
    # or default to qty=1 for the stock-check flow.
    confirmed_quantities = state.get("confirmed_quantities") or {}

    try:
        # Search MCP for each confirmed item
        for item in state["confirmed_items"]:
            try:
                r = await mcp_client.search_platform_items(item["item_name"])
                results = r.get("items", [])
                if results:
                    match = None
                    # 1. First check if any search results are a fuzzy match for the target item
                    for res in results:
                        if is_fuzzy_match(item["item_name"], res["name"]) or any(is_fuzzy_match(part, res["name"]) for part in item["item_name"].split()):
                            match = res
                            break
                    
                    # 2. If no matching item found but we have results, fallback to the first result ONLY if there is word overlap
                    if not match and results:
                        query_words = [w.strip(string.punctuation).lower() for w in item["item_name"].split() if len(w) > 2]
                        first_res_name = results[0]["name"].lower()
                        if any(qw in first_res_name for qw in query_words):
                            match = results[0]
                            
                    if match:
                        qty = confirmed_quantities.get(item["item_name"], 1)
                        cart_items.append({
                            "item_id": match["id"],
                            "item_name": match["name"],
                            "quantity": qty,
                            "price": match["price"],
                        })
            except Exception as e:
                logger.warning(f"MCP search failed for {item['item_name']}: {e}")

        if not cart_items:
            return {
                "response_message": "Couldn't find those items right now. Please try ordering directly on PreFill.",
                "stage": "done",
                "error": "no_items_found",
            }

        # Build the cart via MCP
        cart_data = await mcp_client.update_platform_cart(cart_items)

    except Exception as e:
        logger.error(f"Cart build failed: {e}")
        return {
            "response_message": "⚠️ Couldn't build the cart right now. Please try directly on PreFill.",
            "stage": "done",
            "error": str(e),
        }

    cart_id = cart_data.get("cart_id")
    cart_total = cart_data.get("total", sum(i["price"] * i.get("quantity", 1) for i in cart_items))
    
    from backend.seed.catalog import lookup_catalog_item
    
    cart_lines = []
    for i in cart_items:
        item_name = i["item_name"]
        cat = lookup_catalog_item(item_name)
        
        name = cat["name"] if cat else item_name
        price = cat["price"] if cat else i["price"]
        category = cat["category"] if cat else "unknown"
        unit = cat["unit"] if cat else "N/A"
        qty = i.get("quantity", 1)
        
        cart_lines.append(
            f"• {name} (Qty: {qty}) - Price: ₹{price:.0f} (Category: {category}, Unit: {unit})"
        )
        
    items_list_str = "\n".join(cart_lines)

    return {
        "cart_id": cart_id,
        "cart_total": cart_total,
        "response_message": (
            "🛒 Cart ready with the following items:\n"
            f"{items_list_str}\n\n"
            f"Total Amount: ₹{cart_total:.0f}. Reply CONFIRM to place order."
        ),
        "stage": "awaiting_confirm",
    }


# ---------------------------------------------------------------------------
# Node 4: Place Order
# ---------------------------------------------------------------------------
async def place_order(state: RestockState) -> dict:
    """
    Final step: call PreFill MCP to place the order.
    On success, returns order ID and ETA for the WhatsApp confirmation.
    """
    try:
        cart_id = state.get("cart_id")
        if not cart_id:
            return {
                "response_message": "⚠️ No active cart found. Please try adding items first.",
                "stage": "done",
                "error": "missing_cart_id",
            }
        data = await mcp_client.place_platform_order(cart_id)

        if data.get("success"):
            order_id = data["order_id"]
            eta = data.get("estimated_delivery_minutes", 15)
            platform = data.get("platform", "quick commerce provider")
            return {
                "order_id": order_id,
                "response_message": f"✅ Order placed on {platform.title()}! Arriving in ~{eta} mins. Order #{order_id}",
                "stage": "done",
            }
        else:
            return {
                "response_message": "⚠️ Couldn't place order. Please try directly on the app.",
                "stage": "done",
                "error": "order_placement_failed",
            }

    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return {
            "response_message": "⚠️ Couldn't place order. Please try directly on the app.",
            "stage": "done",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Graph Assembly
# ---------------------------------------------------------------------------
def _route_entry(state: RestockState) -> str:
    """Determine graph entry point based on stage and user message."""
    prev_stage = state.get("stage") or "awaiting_order"
    user_msg = (state.get("user_message") or "").strip().upper()

    AFFIRMATIVES = {"YES", "Y", "REORDER", "ORDER ALL", "OK", "OKAY", "YES PLEASE", "YEP", "SURE", "CONFIRM", "CONFIRMED", "PLACE", "PLACE ORDER", "PROCEED", "DO IT"}
    NEGATIVES = {"NO", "NOPE", "CANCEL", "SKIP", "NOT NOW", "LATER", "N"}

    # Stage: user saw matched items and needs to confirm adding them to cart
    if prev_stage == "confirm_add_to_cart":
        if user_msg in AFFIRMATIVES:
            return "build_cart"
        elif user_msg in NEGATIVES:
            return "reset_to_order"
        else:
            # Re-parse as a possible edit (e.g. "make it 3 milk")
            return "parse_order_intent"

    # Stage: cart is ready — user needs to CONFIRM or CANCEL the order
    if prev_stage == "awaiting_confirm":
        if user_msg in AFFIRMATIVES:
            return "place_order"
        elif user_msg in NEGATIVES:
            return "reset_to_order"
        else:
            # Allow editing cart at this stage too
            return "parse_order_intent"

    # Stage: stock-check flow — user replied to the low-stock alert
    if prev_stage == "awaiting_reply":
        return "parse_reply"

    # Stage: starting / awaiting_order — try to parse as a direct order
    # If message looks like item names, go to parse_order_intent
    # Non-item messages (chit-chat) will be handled inside parse_order_intent
    return "parse_order_intent"


async def reset_to_order(state: RestockState) -> dict:
    """Cancel current flow and return user to the ordering prompt."""
    return {
        "confirmed_items": [],
        "confirmed_quantities": {},
        "cart_id": None,
        "cart_total": None,
        "response_message": "No problem! What would you like to order? You can tell me item names and quantities.",
        "stage": "awaiting_order",
    }


def _should_build_cart(state: RestockState) -> str:
    """Route to build_cart only if we have confirmed items and the stage is building_cart."""
    if state.get("stage") == "building_cart" and state.get("confirmed_items"):
        return "build_cart"
    return "END"


def build_restock_graph() -> StateGraph:
    """
    Assemble the restock graph with direct-order and stock-check flows.

    Entry: routes dynamically based on conversation stage.
    """
    graph = StateGraph(RestockState)  # type: ignore

    # Register nodes
    graph.add_node("generate_alert", generate_alert_message)
    graph.add_node("parse_reply", parse_user_reply)
    graph.add_node("parse_order_intent", parse_order_intent)
    graph.add_node("build_cart", build_cart)
    graph.add_node("place_order", place_order)
    graph.add_node("reset_to_order", reset_to_order)

    # Conditional entry point to route the start node dynamically
    graph.set_conditional_entry_point(
        _route_entry,
        {
            "generate_alert": "generate_alert",
            "parse_reply": "parse_reply",
            "parse_order_intent": "parse_order_intent",
            "build_cart": "build_cart",
            "place_order": "place_order",
            "reset_to_order": "reset_to_order",
        }
    )
    graph.add_edge("generate_alert", END)      # alert sent; await async reply

    # parse_order_intent: either confirm_add_to_cart (stop and wait) or done/awaiting_order
    graph.add_edge("parse_order_intent", END)

    # parse_reply: route to build_cart or END
    graph.add_conditional_edges(
        "parse_reply",
        _should_build_cart,
        {
            "build_cart": "build_cart",
            "END": END
        }
    )
    graph.add_edge("build_cart", END)          # stop execution to await user confirmation
    graph.add_edge("place_order", END)
    graph.add_edge("reset_to_order", END)

    return graph


# Compiled graph — importable as `from backend.agents.restock_agent import restock_agent`
restock_agent = build_restock_graph().compile()
