"""Async reply claim truth judgment using Gemini structured output against ground-truth facts."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("grocer.agent.claim_check")

CLAIM_CHECK_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "verdict": {
            "type": "STRING",
            "enum": ["supported", "unsupported", "no_claim"],
            "description": (
                "supported: all grocery, cart, price, fee, stock, or order claims in the reply are fully verified by the facts. "
                "unsupported: one or more claims in the reply are inaccurate, unverified, or contradicted by the facts. "
                "no_claim: the reply makes no claims about groceries, basket contents, prices, fees, stock, or order status."
            ),
        },
    },
    "required": ["verdict"],
}

CLAIM_CHECK_PROMPT = (
    "Facts from system:\n"
    "{facts_text}\n\n"
    "Assistant reply to customer:\n"
    "\"{reply_text}\"\n\n"
    "Judge whether any claims in the assistant reply are supported by the facts above.\n"
    "- 'supported': Every claim about cart items, quantities, prices, totals, fees, product stock, or order status is completely true according to the facts.\n"
    "- 'unsupported': The reply makes any claim about an item, price, total, fee, availability, or order status that is not supported or is contradicted by the facts.\n"
    "- 'no_claim': The reply makes no claims about grocery items, basket items, prices, totals, fees, stock, or order status (e.g. conversational greetings, general assistance offers, or asking for clarification).\n"
    "Answer with 'supported', 'unsupported', or 'no_claim'."
)


def build_facts_text(
    cart: Any | None = None,
    tool_results: list[dict[str, Any]] | None = None,
) -> str:
    """Build a deterministic plain facts text from real cart state and turn tool outputs."""
    lines: list[str] = []

    # Cart / Basket facts
    items = getattr(cart, "items", None) if cart else None
    if items:
        lines.append("Current Basket:")
        for it in items:
            name = getattr(it, "name", "")
            pack = getattr(it, "pack_size", "")
            qty = getattr(it, "quantity", 0)
            unit_price = getattr(it, "unit_price", 0)
            total_price = getattr(it, "total_price", 0)
            lines.append(f"- {name} ({pack}): qty {qty}, unit price ₹{unit_price}, total ₹{total_price}")
        lines.append(f"- Item Subtotal: ₹{getattr(cart, 'item_total', 0)}")
        if getattr(cart, "delivery_fee", None) is not None:
            lines.append(f"- Delivery Fee: ₹{cart.delivery_fee}")
        if getattr(cart, "packaging_fee", None) is not None:
            lines.append(f"- Packaging Fee: ₹{cart.packaging_fee}")
        if getattr(cart, "handling_fee", None) is not None:
            lines.append(f"- Handling Fee: ₹{cart.handling_fee}")
        if getattr(cart, "taxes", None) is not None:
            lines.append(f"- Taxes: ₹{cart.taxes}")
        lines.append(f"- Grand Total: ₹{getattr(cart, 'grand_total', 0)}")
    else:
        lines.append("Current Basket: empty")

    # Product / Tool facts from this turn
    if tool_results:
        product_lines: list[str] = []
        for res in tool_results:
            if not isinstance(res, dict):
                continue
            # search_products or product list
            products = res.get("products")
            if isinstance(products, list):
                for p in products:
                    if isinstance(p, dict):
                        p_name = p.get("name", "")
                        variants = p.get("variants")
                        if isinstance(variants, list) and variants:
                            for v in variants:
                                if isinstance(v, dict):
                                    v_name = v.get("name") or p_name
                                    v_pack = v.get("pack_size", "")
                                    v_price = v.get("price")
                                    v_stock = "in stock" if v.get("in_stock") is not False else "out of stock"
                                    product_lines.append(f"- {v_name} ({v_pack}): ₹{v_price}, {v_stock}")
                        else:
                            p_price = p.get("price") or p.get("unit_price")
                            p_stock = "in stock" if p.get("in_stock") is not False else "out of stock"
                            product_lines.append(f"- {p_name}: ₹{p_price}, {p_stock}")
            # manage_basket or items list
            elif isinstance(res.get("items"), list):
                for it in res["items"]:
                    if isinstance(it, dict):
                        i_name = it.get("name", "")
                        i_pack = it.get("pack_size", "")
                        i_price = it.get("unit_price") or it.get("price")
                        product_lines.append(f"- {i_name} ({i_pack}): ₹{i_price}")

        if product_lines:
            lines.append("Products from recent search / tool results:")
            lines.extend(product_lines)

    return "\n".join(lines)


async def check_reply_claims(
    client_or_text: Any = None,
    text: str = "",
    *,
    client: Any = None,
    facts_text: str = "",
    timeout: float = 5.0,
) -> str:
    """Judge if an assistant reply's claims are supported, unsupported, or make no claim.

    Returns 'supported', 'unsupported', or 'no_claim'.
    Any error, timeout, or missing configuration returns 'unclear'.
    """
    if isinstance(client_or_text, str):
        target_client = client
        reply_text = client_or_text
    else:
        target_client = client or client_or_text
        reply_text = text

    if not reply_text or not reply_text.strip():
        return "no_claim"

    if not target_client or not getattr(target_client, "api_key", None):
        return "unclear"

    prompt = CLAIM_CHECK_PROMPT.format(
        facts_text=facts_text.strip() if facts_text else "Current Basket: empty",
        reply_text=reply_text.strip(),
    )

    try:
        async with asyncio.timeout(timeout):
            res = await target_client.generate_structured(
                model="gemini-3.5-flash-lite",
                prompt=prompt,
                response_schema=CLAIM_CHECK_SCHEMA,
            )
        if isinstance(res, dict):
            val = str(res.get("verdict") or res.get("claims_cart_or_order", "")).strip().casefold()
            if val in {"supported", "unsupported", "no_claim"}:
                return val
            if val == "no":
                return "no_claim"
            if val == "yes":
                return "supported"
        return "unclear"
    except Exception as exc:
        logger.warning("Claim check failed: %r", exc)
        return "unclear"


async def is_unclaimed_chat(
    client_or_text: Any = None,
    text: str = "",
    *,
    client: Any = None,
    facts_text: str = "",
    timeout: float = 5.0,
) -> bool:
    """Return True only if the check explicitly answers 'no_claim' or 'no'."""
    val = await check_reply_claims(client_or_text, text, client=client, facts_text=facts_text, timeout=timeout)
    return val in {"no_claim", "no"}
