"""Ranker Experiment (Slice E1b): Catalog Ranker Heuristics vs. Small Check Model.

Evaluates whether deterministic catalog_ranker heuristics (word lists / regex)
are required or whether SMALL_CHECK_MODEL (from backend/config.py) can pick
the best product variant from raw Swiggy Instamart search results.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from typing import Any, Optional

from backend.agent.catalog_ranker import rank_and_select_best_variant
from backend.agent.gemini import GeminiClient
from backend.agent.tools import SwiggyAgentTools
from backend.config import settings
from backend.integrations.commerce.exceptions import (
    CommerceError,
    ProviderAuthError,
    ProviderRateLimitedError,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 31 real customer queries (mix of English, Hinglish, vague, brand, size, diet)
CUSTOMER_QUERIES = [
    "milk",
    "2 amul taaza 500ml",
    "bread",
    "brown bread",
    "eggs 6",
    "dahi",
    "paneer",
    "atta 5kg",
    "basmati rice 1kg",
    "toor dal",
    "sugar free biscuits",
    "chai patti",
    "maggi",
    "olive oil",
    "ghee",
    "curd 400g",
    "tissues",
    "toothpaste",
    "dishwash liquid",
    "bananas",
    "onion 1kg",
    "potato",
    "tomato",
    "amul butter 100g",
    "bournvita",
    "pasta",
    "pizza base",
    "mozzarella",
    "sunflower oil 1L",
    "jaggery",
    "coffee",
]

RESULTS_FILE = Path(__file__).parent / "ranker_experiment_results.json"

MODEL_PICK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "choice": {
            "type": "STRING",
            "description": "Candidate ID (e.g. '1', '2', ...) of the single best product match, 'ask the customer' if multiple plausible candidates differ significantly and clarification is needed, or 'unclear' if the options are completely unrelated or ambiguous.",
        },
        "reason": {
            "type": "STRING",
            "description": "Brief 1-sentence rationale for the choice.",
        },
    },
    "required": ["choice"],
}

_last_gemini_call_time: float = 0.0


async def get_model_pick(
    client: GeminiClient,
    query: str,
    candidates: list[dict[str, Any]],
) -> tuple[str, str]:
    """Ask SMALL_CHECK_MODEL to choose one candidate ID, say 'ask the customer', or 'unclear'."""
    global _last_gemini_call_time

    cand_lines = []
    for c in candidates:
        stock_val = c.get("in_stock")
        if stock_val is True:
            stock_info = " | Status: In Stock"
        elif stock_val is False:
            stock_info = " | Status: OUT OF STOCK"
        else:
            stock_info = ""  # Unknown stock: omitted, never shown as OUT OF STOCK
        pack_size = c.get("pack_size") or ""
        price_val = c.get("price") if c.get("price") is not None else 0.0
        cand_lines.append(
            f"ID: {c['candidate_id']} | Name: {c['name']} | Pack: {pack_size} | Price: ₹{price_val}{stock_info}"
        )
    candidates_text = "\n".join(cand_lines)

    prompt = (
        f"You are a grocery shopping replenishment assistant.\n"
        f"A customer asked for: '{query}'\n\n"
        f"Here are the candidate products returned from store search:\n"
        f"{candidates_text}\n\n"
        f"Select the single best candidate ID (e.g. '1', '2', etc.) that best fulfills the customer's request.\n"
        f"If the request is ambiguous or multiple distinctly different brands/types/sizes could fit and choosing one would assume too much, say 'ask the customer'.\n"
        f"Return your choice in the structured schema."
    )

    model_name = settings.GEMINI_SMALL_CHECK_MODEL
    max_retries = 3

    for attempt in range(max_retries + 1):
        # Throttle so at most 8 calls run per minute (minimum 8.0s between calls)
        now = asyncio.get_running_loop().time()
        elapsed = now - _last_gemini_call_time
        if elapsed < 8.0:
            await asyncio.sleep(8.0 - elapsed)
        _last_gemini_call_time = asyncio.get_running_loop().time()

        res, reason = await client.generate_structured_with_reason(
            model=model_name,
            prompt=prompt,
            response_schema=MODEL_PICK_SCHEMA,
        )

        if res:
            choice = str(res.get("choice", "")).strip()
            reason_str = str(res.get("reason", "")).strip()
            return choice, reason_str

        if reason == "quota 429":
            if attempt < max_retries:
                logger.warning(
                    "Quota 429 on query '%s', waiting 30s before retry %d/%d...",
                    query, attempt + 1, max_retries
                )
                await asyncio.sleep(30.0)
                continue
            return "api_error", "Quota 429 exhausted after 3 retries"

        return "api_error", f"Model API error: {reason}"

    return "api_error", "Exhausted retries"


async def run_experiment() -> None:
    print("=" * 80)
    print("SLICE E1b: CATALOG RANKER vs. SMALL CHECK MODEL EXPERIMENT")
    print("=" * 80)

    # 1. Initialize Swiggy MCP Adapter
    adapter = SwiggyMCPAdapter(
        base_url=settings.SWIGGY_MCP_BASE_URL,
        auth_token=settings.SWIGGY_AUTH_TOKEN,
        owner_customer_id=settings.SWIGGY_CUSTOMER_ID,
    )

    # 2. Verify Live Connection & Address
    print("\n[Step 1] Connecting to live Swiggy Instamart MCP...")
    try:
        with adapter.customer_scope(settings.SWIGGY_CUSTOMER_ID or ""):
            addresses = await adapter.get_addresses(settings.SWIGGY_CUSTOMER_ID or "")
    except ProviderAuthError as exc:
        print(f"\n[FATAL] Swiggy MCP UNAUTHORISED: {exc}")
        print("Stopping experiment immediately per Step 2 rules. Do not use mocks.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[FATAL] Swiggy MCP UNAVAILABLE: {exc}")
        print("Stopping experiment immediately per Step 2 rules. Do not use mocks.")
        sys.exit(1)

    if not addresses:
        print("\n[FATAL] No delivery addresses found for Swiggy customer.")
        sys.exit(1)

    delivery_address = addresses[0]
    address_id = delivery_address.id
    print(f"Active delivery address ID: {address_id}")

    # 3. Initialize Gemini client
    gemini_client = GeminiClient(api_key=settings.GEMINI_API_KEY or "")
    tools = SwiggyAgentTools(commerce=adapter)

    # 4. Run all 31 queries
    results_data = []
    gemini_calls_count = 0
    queries_to_run = CUSTOMER_QUERIES

    for q_idx, query in enumerate(queries_to_run, start=1):
        print(f"\n[{q_idx}/{len(queries_to_run)}] Searching: '{query}'...")
        try:
            with adapter.customer_scope(settings.SWIGGY_CUSTOMER_ID or ""):
                search_res = await tools.search_products(query, address_id=address_id)
        except ProviderAuthError as exc:
            print(f"\n[FATAL] Swiggy MCP UNAUTHORISED on query '{query}': {exc}")
            sys.exit(1)
        except Exception as exc:
            print(f"\n[FATAL] Swiggy MCP error on query '{query}': {exc}")
            sys.exit(1)

        raw_products = search_res.get("products", [])
        candidates = []
        cand_id = 1
        for p in raw_products:
            variants = p.get("variants", [])
            for v in variants:
                in_stock_val = v.get("in_stock")
                if in_stock_val is None:
                    in_stock_val = v.get("is_available")

                raw_price = v.get("price")
                try:
                    price_float = float(raw_price) if raw_price is not None else 0.0
                except (ValueError, TypeError):
                    price_float = 0.0

                candidates.append({
                    "candidate_id": str(cand_id),
                    "product_id": p.get("product_id"),
                    "name": v.get("name") or p.get("name"),
                    "product_name": p.get("name"),
                    "brand": p.get("brand"),
                    "category": p.get("category"),
                    "pack_size": v.get("pack_size", ""),
                    "price": price_float,
                    "in_stock": in_stock_val,
                    "spin_id": v.get("spin_id"),
                    "sku_id": v.get("sku_id"),
                })
                cand_id += 1
                if len(candidates) >= 8:
                    break
            if len(candidates) >= 8:
                break

        plain_first = candidates[0] if candidates else None
        plain_order_pick = {
            "candidate_id": plain_first["candidate_id"],
            "name": plain_first["name"],
            "pack_size": plain_first.get("pack_size", ""),
            "price": plain_first.get("price", 0.0),
        } if plain_first else None

        if not candidates:
            print(f"  No candidates found for '{query}'.")
            results_data.append({
                "query": query,
                "candidates": [],
                "plain_order_pick": None,
                "ranker_pick": None,
                "model_pick": "none",
                "model_reason": "No products returned",
                "agree": False,
                "model_said_ask": False,
                "api_error": False,
            })
            continue

        # Run deterministic catalog ranker
        ranker_pick_item = rank_and_select_best_variant(query, candidates)
        ranker_cand_id = None
        if ranker_pick_item:
            for c in candidates:
                if c.get("spin_id") == ranker_pick_item.get("spin_id"):
                    ranker_cand_id = c["candidate_id"]
                    break

        # Run model selection
        gemini_calls_count += 1
        model_choice, model_reason = await get_model_pick(gemini_client, query, candidates)
        is_api_error = (model_choice == "api_error")
        model_said_ask = ("ask" in model_choice.casefold()) and not is_api_error

        # Normalize model numeric choice
        model_choice_id = model_choice
        m_num = re.search(r"\b(\d+)\b", model_choice)
        if m_num and not model_said_ask and not is_api_error:
            model_choice_id = m_num.group(1)

        # Check agreement
        if is_api_error or model_said_ask:
            agree = False
        elif ranker_cand_id and (model_choice == ranker_cand_id or model_choice_id == ranker_cand_id):
            agree = True
        else:
            agree = False

        results_data.append({
            "query": query,
            "candidates": candidates,
            "plain_order_pick": plain_order_pick,
            "ranker_pick": {
                "candidate_id": ranker_cand_id,
                "name": ranker_pick_item.get("name") if ranker_pick_item else None,
                "pack_size": ranker_pick_item.get("pack_size") if ranker_pick_item else None,
                "price": ranker_pick_item.get("price") if ranker_pick_item else None,
            } if ranker_pick_item else None,
            "model_pick": model_choice,
            "model_reason": model_reason,
            "agree": agree,
            "model_said_ask": model_said_ask,
            "api_error": is_api_error,
        })

    # Save results to JSON
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)
    print(f"\nSaved results to {RESULTS_FILE}")

    # Print Table with Plain Order, Ranker Pick, and Model Pick
    print("\n" + "=" * 115)
    print(f"{'QUERY':<20} | {'PLAIN ORDER (#1)':<24} | {'RANKER PICK':<24} | {'MODEL PICK':<16} | {'AGREE':<5} | {'ASK?':<5} | {'API ERR'}")
    print("-" * 115)
    for r in results_data:
        p_name = r["plain_order_pick"]["name"][:22] if r.get("plain_order_pick") and r["plain_order_pick"].get("name") else "None"
        r_name = r["ranker_pick"]["name"][:22] if r["ranker_pick"] and r["ranker_pick"]["name"] else "None"
        m_pick = r["model_pick"][:16]
        agree_str = "YES" if r["agree"] else "NO"
        ask_str = "YES" if r["model_said_ask"] else "NO"
        api_err_str = "YES" if r.get("api_error") else "NO"
        print(f"{r['query']:<20} | {p_name:<24} | {r_name:<24} | {m_pick:<16} | {agree_str:<5} | {ask_str:<5} | {api_err_str}")

    # Disagreements Side-by-Side
    disagreements = [r for r in results_data if not r["agree"]]
    print("\n" + "=" * 80)
    print(f"DISAGREEMENTS ({len(disagreements)} TOTAL)")
    print("=" * 80)
    for d in disagreements:
        print(f"\nQuery: '{d['query']}'")
        p_info = d.get('plain_order_pick')
        p_str = f"[{p_info['candidate_id']}] {p_info['name']} ({p_info['pack_size']}) - Rs. {p_info['price']}" if p_info else "None"
        print(f"Plain Order: {p_str}")
        print(f"Ranker Pick: {d['ranker_pick']}")
        print(f"Model Pick : {d['model_pick']} (Reason: {d['model_reason']})")
        print("Candidates:")
        for c in d["candidates"]:
            s_val = c.get("in_stock")
            stock_disp = "In Stock" if s_val is True else ("OUT OF STOCK" if s_val is False else "Unknown")
            print(f"  [{c['candidate_id']}] {c['name']} ({c['pack_size']}) - Rs. {c['price']} | InStock: {stock_disp}")

    # Totals
    agree_count = sum(1 for r in results_data if r["agree"])
    disagree_count = len(disagreements)
    model_asked_count = sum(1 for r in results_data if r["model_said_ask"])
    api_error_count = sum(1 for r in results_data if r.get("api_error"))
    print("\n" + "=" * 80)
    print("EXPERIMENT TOTALS")
    print(f"Total Queries: {len(results_data)}")
    print(f"Agreed: {agree_count}")
    print(f"Disagreed: {disagree_count}")
    print(f"Model Asked Customer: {model_asked_count}")
    print(f"API Errors: {api_error_count}")
    print(f"Gemini API Calls: {gemini_calls_count}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_experiment())
