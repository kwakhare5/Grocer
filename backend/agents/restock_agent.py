"""
LangGraph Restock Agent — Task 2.5
Stateful multi-turn agent for the WhatsApp grocery restock flow.

Graph nodes:
  1. generate_alert  — Calls Claude API to write a natural WhatsApp alert message
  2. parse_reply     — Interprets user's WhatsApp reply (YES/NO/partial)
  3. build_cart       — Searches MCP for items, builds Instamart cart
  4. place_order      — Places the order via MCP

State transitions:
  generate_alert → END (message sent, awaiting async reply via webhook)
  parse_reply → build_cart (if user confirmed items)
  parse_reply → END (if user declined)
  build_cart → place_order (if cart built successfully)
  build_cart → END (if no items could be found)
  place_order → END

Why LangGraph?
  The restock flow is a multi-turn conversation over WhatsApp. Between the
  initial alert and the user's reply, minutes or hours may pass. LangGraph
  gives us explicit state management so we can serialize state to DB, resume
  from any node, and handle partial/ambiguous replies gracefully.
"""

import json
import logging
from typing import Optional

from langgraph.graph import StateGraph, END
from anthropic import Anthropic
from typing_extensions import TypedDict
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client — uses ANTHROPIC_API_KEY from .env via config
# ---------------------------------------------------------------------------
anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# Claude model to use for message generation and reply parsing.
# Sonnet is the right choice here: fast, cheap, and the prompts are
# well-structured enough that Opus-level reasoning isn't needed at runtime.
CLAUDE_MODEL = "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# Agent State — everything the graph needs to track across nodes
# ---------------------------------------------------------------------------
class RestockState(TypedDict):
    household_id: str
    depleting_items: list           # list of dicts with item_name, confidence_score, days_remaining
    stage: str                      # alert | awaiting_reply | building_cart | awaiting_confirm | done
    user_message: Optional[str]     # the raw WhatsApp text from the user
    confirmed_items: list           # subset of depleting_items the user said YES to
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
    items_text = "\n".join([
        f"- {i['item_name']}: {int(i.get('confidence_score', 0.5) * 100)}% likely running low "
        f"({round(i.get('days_remaining', 1), 1)} days remaining)"
        for i in state["depleting_items"]
    ])

    try:
        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a smart household assistant for Swiggy Instamart.\n\n"
                    f"Items likely running low:\n{items_text}\n\n"
                    f"Write a WhatsApp message under 80 words. List top 3 items with confidence %. "
                    f"Be friendly but brief. Max 2 emojis. End with: "
                    f"'Reply YES to reorder all, or tell me which ones.' "
                    f"Mention this is based on their purchase pattern. Write ONLY the message."
                ),
            }],
        )
        message = response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error in generate_alert: {e}")
        # Fallback to a template if Claude is unavailable (e.g. no API key in dev)
        item_lines = "\n".join([
            f"• {i['item_name']} ({int(i.get('confidence_score', 0.5) * 100)}% confident)"
            for i in state["depleting_items"][:3]
        ])
        message = (
            f"🛒 Based on your purchase patterns, you're likely running low on:\n\n"
            f"{item_lines}\n\n"
            f"Reply YES to reorder all, or tell me which ones."
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
    msg = (state.get("user_message") or "").strip().upper()

    # Case 1: Clear affirmative
    if msg in ["YES", "Y", "REORDER", "ORDER ALL", "OK", "OKAY", "YES PLEASE", "YEP", "SURE"]:
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

    # Case 3: Ambiguous — ask Claude to parse which items they want
    items_list = "\n".join([f"- {i['item_name']}" for i in state["depleting_items"]])

    try:
        resp = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"User was asked to reorder these grocery items:\n{items_list}\n\n"
                    f"Their reply: \"{state['user_message']}\"\n\n"
                    f"Return a JSON array of item names they want to order. "
                    f"Empty array if they want none. Full list if they said 'all'. "
                    f"ONLY output the JSON array, nothing else."
                ),
            }],
        )
        wanted = json.loads(resp.content[0].text)
        confirmed = [
            i for i in state["depleting_items"]
            if any(w.lower() in i["item_name"].lower() for w in wanted)
        ]

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

    except Exception as e:
        logger.error(f"Claude parse error: {e}")
        return {
            "response_message": "Sorry, I didn't catch that. Reply YES to reorder all, or NO to skip.",
            "stage": "awaiting_reply",
        }


# ---------------------------------------------------------------------------
# Node 3: Build Cart
# ---------------------------------------------------------------------------
async def build_cart(state: RestockState) -> dict:
    """
    For each confirmed item, search the MCP catalog to get the current product
    listing, then add all items to a single Instamart cart.

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

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            # Search MCP for each confirmed item
            for item in state["confirmed_items"]:
                try:
                    r = await client.post(
                        f"{settings.MCP_BASE_URL}/search_instamart_items",
                        json={"query": item["item_name"]},
                    )
                    results = r.json().get("items", [])
                    if results:
                        match = results[0]
                        cart_items.append({
                            "item_id": match["id"],
                            "item_name": match["name"],
                            "quantity": 1,
                            "price": match["price"],
                        })
                except Exception as e:
                    logger.warning(f"MCP search failed for {item['item_name']}: {e}")

            if not cart_items:
                return {
                    "response_message": "Couldn't find those items right now. Please try ordering directly on Instamart.",
                    "stage": "done",
                    "error": "no_items_found",
                }

            # Build the cart via MCP
            cart_resp = await client.post(
                f"{settings.MCP_BASE_URL}/update_instamart_cart",
                json={"items": cart_items},
            )
            cart_data = cart_resp.json()

    except Exception as e:
        logger.error(f"Cart build failed: {e}")
        return {
            "response_message": "⚠️ Couldn't build the cart right now. Please try directly on Instamart.",
            "stage": "done",
            "error": str(e),
        }

    cart_id = cart_data.get("cart_id")
    cart_total = cart_data.get("total", sum(i["price"] for i in cart_items))
    names = [i["item_name"] for i in cart_items]

    # Truncate display if too many items
    display_names = ", ".join(names[:3])
    if len(names) > 3:
        display_names += f"... (+{len(names) - 3} more)"

    return {
        "cart_id": cart_id,
        "cart_total": cart_total,
        "response_message": (
            f"Cart ready: {display_names}. "
            f"Total: ₹{cart_total:.0f}. Reply CONFIRM to place order."
        ),
        "stage": "awaiting_confirm",
    }


# ---------------------------------------------------------------------------
# Node 4: Place Order
# ---------------------------------------------------------------------------
async def place_order(state: RestockState) -> dict:
    """
    Final step: call Instamart MCP to place the order.
    On success, returns order ID and ETA for the WhatsApp confirmation.
    """
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            r = await client.post(
                f"{settings.MCP_BASE_URL}/place_instamart_order",
                json={"cart_id": state["cart_id"]},
            )
            data = r.json()

        if data.get("success"):
            order_id = data["order_id"]
            eta = data.get("estimated_delivery_minutes", 15)
            return {
                "order_id": order_id,
                "response_message": f"✅ Order placed! Arriving in ~{eta} mins. Order #{order_id}",
                "stage": "done",
            }
        else:
            return {
                "response_message": "⚠️ Couldn't place order. Please try directly on Instamart.",
                "stage": "done",
                "error": "order_placement_failed",
            }

    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return {
            "response_message": "⚠️ Couldn't place order. Please try directly on Instamart.",
            "stage": "done",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Graph Assembly
# ---------------------------------------------------------------------------
def _should_place_order(state: RestockState) -> str:
    """Conditional edge: only proceed to place_order if a cart was built."""
    if state.get("cart_id"):
        return "place_order"
    return END


def build_restock_graph() -> StateGraph:
    """
    Assemble the 4-node restock graph.

    Entry: generate_alert → END (message is sent, we wait for async webhook)
    Resume: parse_reply → build_cart → place_order → END

    Why two separate entry flows?
      The initial alert and the user's reply arrive via different triggers:
      - Alert: fired by the daily scheduler (enters at generate_alert)
      - Reply: arrives via Twilio webhook (enters at parse_reply)
      LangGraph handles this by letting us invoke with a specific entry node.
    """
    graph = StateGraph(RestockState)

    # Register nodes
    graph.add_node("generate_alert", generate_alert_message)
    graph.add_node("parse_reply", parse_user_reply)
    graph.add_node("build_cart", build_cart)
    graph.add_node("place_order", place_order)

    # Edges
    graph.set_entry_point("generate_alert")
    graph.add_edge("generate_alert", END)      # alert sent; await async reply

    # When invoked from webhook (entry="parse_reply"):
    graph.add_edge("parse_reply", "build_cart")
    graph.add_conditional_edges("build_cart", _should_place_order)
    graph.add_edge("place_order", END)

    return graph


# Compiled graph — importable as `from backend.agents.restock_agent import restock_agent`
restock_agent = build_restock_graph().compile()
