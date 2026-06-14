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
import string
from typing import Optional

from langgraph.graph import StateGraph, END
from anthropic import Anthropic
from typing_extensions import TypedDict
import httpx

from backend.config import settings
from backend.mcp.client import mcp_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client — uses ANTHROPIC_API_KEY from .env via config
# ---------------------------------------------------------------------------
anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# Claude model to use for message generation and reply parsing.
CLAUDE_MODEL = "claude-3-5-sonnet-latest"


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]


def is_fuzzy_match(w1: str, w2: str) -> bool:
    """Check if two words are a fuzzy match based on substring check or Levenshtein distance."""
    w1 = w1.lower().strip()
    w2 = w2.lower().strip()
    
    if len(w1) < 3 or len(w2) < 3:
        return w1 == w2
        
    # Substring match (succeeds first)
    if w1 in w2 or w2 in w1:
        return True
        
    # Levenshtein check for spelling mistakes
    dist = levenshtein_distance(w1, w2)
    max_len = max(len(w1), len(w2))
    if max_len <= 4:
        return dist <= 1
    elif max_len <= 7:
        return dist <= 2
    else:
        return dist <= 3


def is_anthropic_configured() -> bool:
    key = settings.ANTHROPIC_API_KEY
    return bool(key and key.strip() and "your_key_here" not in key)


def is_groq_configured() -> bool:
    key = settings.GROQ_API_KEY
    return bool(key and key.strip() and "your_key_here" not in key)


async def call_groq_api(prompt: str, system_prompt: Optional[str] = None, json_mode: bool = False) -> str:
    """
    Call Groq API using HTTPX AsyncClient with model fallback.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set.")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192"]
    last_err = None
    
    for model in models:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(f"Groq API call succeeded with model {model}")
                return content
        except Exception as e:
            logger.warning(f"Groq API call failed with model {model}: {e}")
            last_err = e
            continue
            
    raise last_err or ValueError("Failed to call Groq API with any models.")


def is_nvidia_configured() -> bool:
    key = settings.NVIDIA_API_KEY
    return bool(key and key.strip() and "your_key_here" not in key)


async def call_nvidia_api(prompt: str, system_prompt: Optional[str] = None, json_mode: bool = False) -> str:
    """
    Call NVIDIA NIM API using HTTPX AsyncClient with model fallback.
    """
    if not settings.NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY is not set.")
    
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    models = ["meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct", "meta/llama3-70b-instruct"]
    last_err = None
    
    for model in models:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(f"NVIDIA API call succeeded with model {model}")
                return content
        except Exception as e:
            logger.warning(f"NVIDIA API call failed with model {model}: {e}")
            last_err = e
            continue
            
    raise last_err or ValueError("Failed to call NVIDIA API with any models.")


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
    if is_anthropic_configured():
        try:
            response = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": (
                        f"You are a smart household assistant for Swiggy Instamart.\n\n"
                        f"Items likely running low:\n{items_text}\n\n"
                        f"Write a WhatsApp message under 150 words. You MUST list all items from the list above, showing for each item:\n"
                        f"- Its whole name\n"
                        f"- Qty: 1\n"
                        f"- Price (e.g. ₹X)\n"
                        f"- Unit and Category\n"
                        f"- Confidence % and Days remaining\n\n"
                        f"At the end of the item list, calculate and mention the estimated total amount (Estimated Total: ₹{total_amount:.0f}).\n"
                        f"Be friendly but brief. Max 2 emojis. End with: "
                        f"'Reply YES to reorder all, or tell me which ones.' "
                        f"Mention this is based on their purchase pattern. Write ONLY the message."
                    ),
                }],
            )
            message = response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error in generate_alert: {e}")

    if not message and is_groq_configured():
        try:
            prompt = (
                f"You are a smart household assistant for Swiggy Instamart.\n\n"
                f"Items likely running low:\n{items_text}\n\n"
                f"Write a WhatsApp message under 150 words. You MUST list all items from the list above, showing for each item:\n"
                f"- Its whole name\n"
                f"- Qty: 1\n"
                f"- Price (e.g. ₹X)\n"
                f"- Unit and Category\n"
                f"- Confidence % and Days remaining\n\n"
                f"At the end of the item list, calculate and mention the estimated total amount (Estimated Total: ₹{total_amount:.0f}).\n"
                f"Be friendly but brief. Max 2 emojis. End with: "
                f"'Reply YES to reorder all, or tell me which ones.' "
                f"Mention this is based on their purchase pattern. Write ONLY the message."
            )
            message = await call_groq_api(prompt=prompt)
        except Exception as e:
            logger.error(f"Groq API error in generate_alert: {e}")

    if not message and is_nvidia_configured():
        try:
            prompt = (
                f"You are a smart household assistant for Swiggy Instamart.\n\n"
                f"Items likely running low:\n{items_text}\n\n"
                f"Write a WhatsApp message under 150 words. You MUST list all items from the list above, showing for each item:\n"
                f"- Its whole name\n"
                f"- Qty: 1\n"
                f"- Price (e.g. ₹X)\n"
                f"- Unit and Category\n"
                f"- Confidence % and Days remaining\n\n"
                f"At the end of the item list, calculate and mention the estimated total amount (Estimated Total: ₹{total_amount:.0f}).\n"
                f"Be friendly but brief. Max 2 emojis. End with: "
                f"'Reply YES to reorder all, or tell me which ones.' "
                f"Mention this is based on their purchase pattern. Write ONLY the message."
            )
            message = await call_nvidia_api(prompt=prompt)
        except Exception as e:
            logger.error(f"NVIDIA API error in generate_alert: {e}")

    if not message:
        # Fallback to a template if Claude, Groq, and NVIDIA are unavailable
        item_lines = "\n".join([
            f"• {line[2:]}" if line.startswith("- ") else f"• {line}"
            for line in detailed_lines
        ])
        message = (
            f"🛒 Based on your purchase patterns, you're likely running low on:\n\n"
            f"{item_lines}\n\n"
            f"Estimated Total: ₹{total_amount:.0f}\n\n"
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

    # Try Anthropic (Claude)
    if is_anthropic_configured():
        try:
            resp = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        f"The user has these items in their cart:\n{items_list}\n\n"
                        f"Their reply: \"{state['user_message']}\"\n\n"
                        f"Analyze their reply and return a JSON object with two keys:\n"
                        f"1. 'wanted': a list of item names they want to keep or add to the cart. By default, they want to keep all items in their cart unless they specify to skip or remove some.\n"
                        f"2. 'unrecognized': a boolean. Set to true ONLY if their reply is completely unrelated garbage, gibberish, or unrelated chit-chat (e.g. 'hello', 'who are you', 'testing'). If they are confirming, rejecting, or editing items, set it to false.\n"
                        f"Format the output strictly as a JSON object, like: {{\"wanted\": [\"Amul Taza Milk 1L\"], \"unrecognized\": false}}."
                    ),
                }],
            )
            resp_text = resp.content[0].text.strip()
            if "```json" in resp_text:
                resp_text = resp_text.split("```json")[1].split("```")[0].strip()
            elif "```" in resp_text:
                resp_text = resp_text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(resp_text)
            wanted = parsed.get("wanted", [])
            unrecognized = parsed.get("unrecognized", False)
        except Exception as e:
            logger.error(f"Claude parse error: {e}")

    # Try Groq (Llama)
    if wanted is None and is_groq_configured():
        try:
            prompt = (
                f"The user has these items in their cart:\n{items_list}\n\n"
                f"Their reply: \"{state['user_message']}\"\n\n"
                f"Analyze their reply and return a JSON object with two keys:\n"
                f"1. 'wanted': a list of item names they want to keep or add to the cart. By default, they want to keep all items in their cart unless they specify to skip or remove some.\n"
                f"2. 'unrecognized': a boolean. Set to true ONLY if their reply is completely unrelated garbage, gibberish, or unrelated chit-chat (e.g. 'hello', 'who are you', 'testing'). If they are confirming, rejecting, or editing items, set it to false.\n"
                f"ONLY output valid JSON, like: {{\"wanted\": [\"item1\"], \"unrecognized\": false}}."
            )
            resp_text = await call_groq_api(prompt=prompt, json_mode=True)
            logger.info(f"Groq parse raw response: {resp_text}")
            parsed = json.loads(resp_text)
            wanted = parsed.get("wanted", [])
            unrecognized = parsed.get("unrecognized", False)
        except Exception as e:
            logger.error(f"Groq parse error: {e}")

    # Try NVIDIA (Llama)
    if wanted is None and is_nvidia_configured():
        try:
            prompt = (
                f"The user has these items in their cart:\n{items_list}\n\n"
                f"Their reply: \"{state['user_message']}\"\n\n"
                f"Analyze their reply and return a JSON object with two keys:\n"
                f"1. 'wanted': a list of item names they want to keep or add to the cart. By default, they want to keep all items in their cart unless they specify to skip or remove some.\n"
                f"2. 'unrecognized': a boolean. Set to true ONLY if their reply is completely unrelated garbage, gibberish, or unrelated chit-chat (e.g. 'hello', 'who are you', 'testing'). If they are confirming, rejecting, or editing items, set it to false.\n"
                f"ONLY output valid JSON, like: {{\"wanted\": [\"item1\"], \"unrecognized\": false}}."
            )
            resp_text = await call_nvidia_api(prompt=prompt, json_mode=True)
            logger.info(f"NVIDIA parse raw response: {resp_text}")
            parsed = json.loads(resp_text)
            wanted = parsed.get("wanted", [])
            unrecognized = parsed.get("unrecognized", False)
        except Exception as e:
            logger.error(f"NVIDIA parse error: {e}")

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
                    if name.lower() in cat_item["name"].lower() or cat_item["name"].lower() in name.lower():
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
            cat_name_lower = cat_item["name"].lower()
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
                if not any(c["item_name"].lower() == cat_item["name"].lower() for c in confirmed):
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
        # Search MCP for each confirmed item
        for item in state["confirmed_items"]:
            try:
                r = await mcp_client.search_instamart_items(item["item_name"])
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
        cart_data = await mcp_client.update_instamart_cart(cart_items)

    except Exception as e:
        logger.error(f"Cart build failed: {e}")
        return {
            "response_message": "⚠️ Couldn't build the cart right now. Please try directly on Instamart.",
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
    Final step: call Instamart MCP to place the order.
    On success, returns order ID and ETA for the WhatsApp confirmation.
    """
    try:
        data = await mcp_client.place_instamart_order(state["cart_id"])

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
def _route_entry(state: RestockState) -> str:
    """Determine graph entry point based on stage and user message."""
    prev_stage = state.get("stage")
    user_msg = (state.get("user_message") or "").strip().upper()
    
    # If we were awaiting confirmation, and the user says CONFIRM, YES, or OK
    if prev_stage == "awaiting_confirm":
        if user_msg in ["CONFIRM", "YES", "Y", "OK", "OKAY", "PROCEED", "DO IT"]:
            return "place_order"
        else:
            # User sent something else (like "add tomatoes") - route to parse_reply to edit the cart
            return "parse_reply"
        
    # Otherwise, parse their reply as a new selection (or edit)
    return "parse_reply"


def _should_build_cart(state: RestockState) -> str:
    """Route to build_cart only if we have confirmed items and the stage is building_cart."""
    if state.get("stage") == "building_cart" and state.get("confirmed_items"):
        return "build_cart"
    return "END"


def build_restock_graph() -> StateGraph:
    """
    Assemble the 4-node restock graph.

    Entry: routes dynamically to generate_alert, parse_reply, or place_order.
    """
    graph = StateGraph(RestockState)

    # Register nodes
    graph.add_node("generate_alert", generate_alert_message)
    graph.add_node("parse_reply", parse_user_reply)
    graph.add_node("build_cart", build_cart)
    graph.add_node("place_order", place_order)

    # Conditional entry point to route the start node dynamically
    graph.set_conditional_entry_point(
        _route_entry,
        {
            "generate_alert": "generate_alert",
            "parse_reply": "parse_reply",
            "place_order": "place_order"
        }
    )
    graph.add_edge("generate_alert", END)      # alert sent; await async reply

    # When invoked from webhook:
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

    return graph


# Compiled graph — importable as `from backend.agents.restock_agent import restock_agent`
restock_agent = build_restock_graph().compile()
