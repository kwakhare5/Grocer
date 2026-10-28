"""Grocer — offline scorecard.

One message, one expected basket. The plan is handed to the pipeline, so the
model is out of the loop: this scores Python's handling of a correct plan, not
the model's understanding. Live understanding is `scripts/eval_router.py`.

Expectations are written from the customer's intent. A failing case is a
finding to judge, never a snapshot of current behaviour.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fixture_client import FixtureSwiggyClient
from test_whatsapp_webhook import (
    RecordingWA,
    SignedRequest,
    _all_bodies,
    _message,
    _seed_text_user,
)

from backend.agent.router import SAFETY_BY_CAPABILITY, Capability, RoutingDecision
from backend.channels.whatsapp import handle_webhook
from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.schemas import SearchProductsData, ToolEnvelope

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CASES_PATH = Path(__file__).resolve().parent / "scorecard_cases.json"
OUT_PATH = Path(__file__).resolve().parents[1] / ".scratch" / "scorecard_offline.json"

pytestmark = [pytest.mark.db, pytest.mark.scripted]


def _scorecard_catalog() -> SearchProductsData:
    """The committed catalog plus the pack sizes these cases need."""
    raw = json.loads((FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8"))
    template = copy.deepcopy(raw["data"]["products"][2])

    def product(
        name: str,
        brand: str,
        product_id: str,
        spin_id: str,
        size: str,
        price: int,
    ) -> dict[str, Any]:
        item = copy.deepcopy(template)
        item.update({"displayName": name, "brand": brand, "productId": product_id})
        variation = item["variations"][0]
        variation.update(
            {
                "spinId": spin_id,
                "skuId": f"sku_{spin_id}",
                "quantityDescription": size,
                "displayName": f"{name} ({size})",
                "brandName": brand,
                "maxQuantity": 4,
            }
        )
        variation["price"]["mrp"] = price
        variation["price"]["offerPrice"] = price
        return item

    raw["data"]["products"].extend(
        [
            product("Amul Fresh Paneer", "Amul", "prod_paneer_200", "spin_paneer_200g", "200 g", 85),
            product(
                "Amul Fresh Paneer Family Pack", "Amul", "prod_paneer_400",
                "spin_paneer_400g", "400 g", 170,
            ),
            product(
                "Daawat Rozana Basmati Rice", "Daawat", "prod_rice_1kg",
                "spin_rice_1kg", "1 kg", 149,
            ),
            product("Mtr Gulab Jamun Mix", "Mtr", "prod_jamun_500", "spin_jamun_500g", "500 g", 180),
            product("Fresh Bananas", "Local", "prod_banana_01", "spin_banana_6", "6 pcs", 48),
            product("Tata Salt", "Tata", "prod_salt_01", "spin_salt_1kg", "1 kg", 28),
            product(
                "Happilo California Almonds", "Happilo", "prod_almonds_01",
                "spin_almonds_1kg", "1 kg", 899,
            ),
        ]
    )
    envelope = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert envelope.data is not None
    return envelope.data


def _decision(plan: dict[str, Any]) -> RoutingDecision:
    capability = Capability(plan["capability"])
    return RoutingDecision(
        capability=capability,
        safety=SAFETY_BY_CAPABILITY[capability],
        confidence=0.95,
        items=plan.get("items", []),
        change_action=plan.get("change_action"),
        order_ref=plan.get("order_ref"),
        address_ref=plan.get("address_ref"),
    )


def _problems(case: dict[str, Any], cart: dict[str, int], bodies: list[str]) -> list[str]:
    found: list[str] = []
    said = "\n".join(bodies).lower()
    for group in case.get("expect_cart", []):
        options = group["any"]
        wanted = group.get("qty", 1)
        hit = next((spin for spin in options if spin in cart), None)
        if hit is None:
            found.append(f"missing {options}")
        elif cart[hit] != wanted:
            found.append(f"{hit} qty {cart[hit]}, wanted {wanted}")
    for spin in case.get("forbid", []):
        if spin in cart:
            found.append(f"unexpected {spin} qty {cart[spin]}")
    for spin, ceiling in case.get("max_cart_qty", {}).items():
        if cart.get(spin, 0) > ceiling:
            found.append(f"{spin} qty {cart[spin]} over the {ceiling} limit")
    for phrase in case.get("reply_has", []):
        if phrase.lower() not in said:
            found.append(f"reply never said {phrase!r}")
    for phrase in case.get("reply_lacks", []):
        if phrase.lower() in said:
            found.append(f"reply wrongly said {phrase!r}")
    return found


@pytest.mark.asyncio
async def test_scorecard(monkeypatch):
    from backend.agent import customer_advocate
    from backend.agent import router as router_module

    pool = await get_db_pool()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    catalog = _scorecard_catalog()
    rows: list[dict[str, Any]] = []

    for case in cases:
        wa_id, _user_id = await _seed_text_user(pool)
        client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=catalog)
        outbound = RecordingWA()
        # Always start from a known basket; the committed get_cart fixture holds
        # two milk lines and would leak into every case.
        client.update_cart(items=case.get("basket", []), address_id="addr_01HXYZ")

        decision = _decision(case["plan"])
        monkeypatch.setattr(
            router_module, "route_message", lambda *args, _d=decision, **kwargs: _d
        )

        try:
            await handle_webhook(
                SignedRequest(_message(wa_id, text=case["text"])),
                swiggy_client=client,
                wa_client=outbound,
            )
        except Exception as exc:  # noqa: BLE001 - a raised case is a failed case
            rows.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "text": case["text"],
                    "passed": False,
                    "problems": [f"raised {type(exc).__name__}: {exc}"],
                }
            )
            continue

        cart = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
        problems = _problems(case, cart, _all_bodies(outbound))
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "passed": not problems,
                "problems": problems,
                "cart": cart,
                "replies": _all_bodies(outbound),
            }
        )

    per_category: dict[str, list[bool]] = {}
    for row in rows:
        per_category.setdefault(row["category"], []).append(row["passed"])

    print("\n=============== SCORECARD — offline (plan given) ===============")
    for category, results in per_category.items():
        passed = sum(results)
        print(f"  {category:<12} {passed}/{len(results)}  {passed / len(results) * 100:5.1f}%")
    total = len(rows)
    passed_total = sum(1 for row in rows if row["passed"])
    print("  " + "-" * 44)
    print(f"  {'TOTAL':<12} {passed_total}/{total}  {passed_total / total * 100:5.1f}%")
    known = {case["id"]: case["known_failure"] for case in cases if case.get("known_failure")}
    failures = [row for row in rows if not row["passed"]]
    unexpected = [row for row in failures if row["id"] not in known]
    if failures:
        print("\n  Findings:")
        for row in failures:
            label = "known" if row["id"] in known else "NEW"
            print(f"  - [{label}] {row['id']}: {row['text']}")
            if row["id"] in known:
                print(f"      {known[row['id']]}")
            for problem in row["problems"]:
                print(f"      {problem}")
    print("=================================================================\n")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "mode": "offline",
                "total": total,
                "passed": passed_total,
                "percent": round(passed_total / total * 100, 1),
                "categories": {
                    category: {"passed": sum(results), "total": len(results)}
                    for category, results in per_category.items()
                },
                "known_failures": known,
                "rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert not unexpected, f"{len(unexpected)} new scorecard failures"
