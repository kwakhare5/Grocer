"""Grocer — WhatsApp webhook plumbing.

Runs on PostgreSQL with a scripted Swiggy boundary and a recording outbound
client. It proves the exact JSON Meta posts for a button tap reaches the right
handler. It does not prove Meta's delivery or a human tap.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fixture_client import FixtureSwiggyClient

from backend.channels.link_tokens import verify_link_token
from backend.channels.whatsapp import _park_and_prompt, handle_webhook
from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.schemas import SearchProductsData, ToolEnvelope
from backend.integrations.commerce.token_vault import store_user_token

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _catalog() -> SearchProductsData:
    raw = json.loads((FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8"))
    envelope = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert envelope.data is not None
    return envelope.data


def _catalog_with_bananas() -> SearchProductsData:
    raw = json.loads((FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8"))
    product = copy.deepcopy(raw["data"]["products"][2])
    product.update(
        {
            "displayName": "Fresh Bananas",
            "brand": "Local",
            "productId": "prod_banana_01",
        }
    )
    variation = product["variations"][0]
    variation.update(
        {
            "spinId": "spin_banana_6",
            "skuId": "sku_banana_6",
            "quantityDescription": "6 pcs",
            "displayName": "Fresh Bananas (6 pcs)",
            "brandName": "Local",
            "maxQuantity": 4,
        }
    )
    raw["data"]["products"].append(product)
    envelope = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert envelope.data is not None
    return envelope.data


def _catalog_with_paneer_and_rice() -> SearchProductsData:
    raw = json.loads((FIXTURES_DIR / "catalog_samples.json").read_text(encoding="utf-8"))
    template = copy.deepcopy(raw["data"]["products"][2])

    def product(
        name: str,
        brand: str,
        product_id: str,
        spin_id: str,
        size: str,
        display_name: str,
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
                "displayName": display_name,
                "brandName": brand,
                "maxQuantity": 4,
            }
        )
        variation["price"]["mrp"] = price
        variation["price"]["offerPrice"] = price
        return item

    raw["data"]["products"].extend(
        [
            product(
                "Amul Fresh Paneer",
                "Amul",
                "prod_paneer_200",
                "spin_paneer_200g",
                "200 g",
                "Amul Fresh Paneer (200 g)",
                85,
            ),
            product(
                "Amul Fresh Paneer Family Pack",
                "Amul",
                "prod_paneer_400",
                "spin_paneer_400g",
                "400 g",
                "Amul Fresh Paneer (400 g)",
                170,
            ),
            product(
                "Daawat Rozana Basmati Rice",
                "Daawat",
                "prod_rice_1kg",
                "spin_rice_1kg",
                "1 kg",
                "Daawat Rozana Basmati Rice (1 kg)",
                149,
            ),
            product(
                "Mtr Gulab Jamun Mix",
                "Mtr",
                "prod_jamun_500",
                "spin_jamun_500g",
                "500 g",
                "Mtr Gulab Jamun Mix (500 g)",
                144,
            ),
        ]
    )
    envelope = ToolEnvelope[SearchProductsData].model_validate(raw)
    assert envelope.data is not None
    return envelope.data


async def _seed_text_user(pool: Any) -> tuple[str, Any]:
    wa_id = _new_wa_id()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;", wa_id
        )
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id, last_active_at)
            VALUES ($1, 'addr_01HXYZ', now())
            ON CONFLICT (user_id) DO UPDATE
            SET active_address_id = 'addr_01HXYZ', last_active_at = now();
            """,
            user_id,
        )
    await store_user_token(user_id=user_id, access_token="swiggy_webhook_token")
    return wa_id, user_id


def _plan_row(
    query: str,
    packs: int,
    spin_id: str,
    name: str,
    size: str = "1 L",
    price_paise: int = 0,
) -> dict[str, Any]:
    return {
        "query": query,
        "amount": None,
        "unit": None,
        "packs": packs,
        "spin_id": spin_id,
        "sku_id": f"sku_{spin_id}",
        "name": name,
        "size": size,
        "price_paise": price_paise,
    }


async def _seed_plan(
    pool: Any,
    user_id: Any,
    rows: list[dict[str, Any]],
    minutes: int = 30,
) -> None:
    plan = {
        "dish": "breakfast",
        "servings": 2,
        "items": rows,
        "total_paise": 0,
        "missing": [],
    }
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE grocer.sessions SET pending_plan = $2::jsonb, "
            "pending_plan_expires_at = now() + ($3 * interval '1 minute') "
            "WHERE user_id = $1;",
            user_id,
            json.dumps(plan),
            minutes,
        )


async def _stored_plan(pool: Any, user_id: Any) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        stored = await conn.fetchval(
            "SELECT pending_plan FROM grocer.sessions WHERE user_id = $1;", user_id
        )
    if isinstance(stored, str):
        return json.loads(stored)
    return stored

pytestmark = [pytest.mark.db, pytest.mark.scripted]


class RecordingWA:
    """Captures outbound calls instead of sending them to Meta."""

    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []
        self.buttons: list[tuple[str, str, list[tuple[str, str]]]] = []
        self.ctas: list[tuple[str, str, str, str]] = []
        self.reads: list[str] = []
        self.reactions: list[tuple[str, str, str]] = []

    async def mark_read(self, message_id: str) -> None:
        self.reads.append(message_id)

    async def send_text_message(self, to_wa_id: str, text: str) -> None:
        self.texts.append((to_wa_id, text))

    async def send_quick_reply_buttons(
        self, to_wa_id: str, body_text: str, buttons: list[tuple[str, str]]
    ) -> None:
        self.buttons.append((to_wa_id, body_text, buttons))

    async def send_cta_url_button(
        self, to_wa_id: str, body_text: str, button_text: str, url: str
    ) -> None:
        self.ctas.append((to_wa_id, body_text, button_text, url))

    async def send_reaction(
        self, to_wa_id: str, message_id: str, emoji: str
    ) -> None:
        self.reactions.append((to_wa_id, message_id, emoji))


class SignedRequest:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            settings.WHATSAPP_APP_SECRET.encode("utf-8"), self._body, hashlib.sha256
        ).hexdigest()
        self.headers = {"X-Hub-Signature-256": f"sha256={signature}"}

    async def body(self) -> bytes:
        return self._body


def _message(
    wa_id: str,
    *,
    wamid: str | None = None,
    text: str | None = None,
    button_id: str | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "from": wa_id,
        "id": wamid or f"wamid.{uuid.uuid4()}",
        "timestamp": str(int(time.time())),
    }
    if button_id:
        message["type"] = "interactive"
        message["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": button_id, "title": button_id[:20]},
        }
    else:
        message["type"] = "text"
        message["text"] = {"body": text or ""}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_01",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210"},
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }


def _new_wa_id() -> str:
    return f"91{uuid.uuid4().int % 10000000000:010d}"


def _all_bodies(outbound: RecordingWA) -> list[str]:
    return [text for _to, text in outbound.texts] + [
        body for _to, body, _buttons in outbound.buttons
    ]


@pytest.mark.asyncio
async def test_duplicate_tap_is_dropped_before_it_runs_twice():
    wa_id = _new_wa_id()
    wamid = f"wamid.{uuid.uuid4()}"
    client = FixtureSwiggyClient(FIXTURES_DIR)
    outbound = RecordingWA()
    payload = _message(wa_id, wamid=wamid, button_id="cart:add:spin_test_cookie:1")

    first = await handle_webhook(
        SignedRequest(payload), swiggy_client=client, wa_client=outbound
    )
    second = await handle_webhook(
        SignedRequest(_message(wa_id, wamid=wamid, button_id="cart:add:spin_test_cookie:1")),
        swiggy_client=client,
        wa_client=outbound,
    )
    await asyncio.sleep(0.05)

    assert first["status"] == "basket_updated"
    assert second["status"] == "duplicate_dropped"
    assert outbound.reads == [wamid]
    spins = [item.spinId for item in client.get_cart("addr_01HXYZ").items]
    assert spins.count("spin_test_cookie") == 1
    assert any("Added" in text for _, text in outbound.texts)


@pytest.mark.asyncio
async def test_pay_tap_while_locked_never_calls_swiggy():
    wa_id = _new_wa_id()
    outbound = RecordingWA()
    approval_id = str(uuid.uuid4())

    class SpyClient(FixtureSwiggyClient):
        checkout_calls = 0

        def checkout(self, *args: Any, **kwargs: Any):  # pragma: no cover - must not run
            SpyClient.checkout_calls += 1
            raise AssertionError("checkout must not run while the lock is on")

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id=f"pay:{approval_id}")),
        swiggy_client=SpyClient(fixtures_dir=FIXTURES_DIR),
        wa_client=outbound,
    )
    await asyncio.sleep(0.05)

    assert result["status"] == "checkout_failed"
    assert "locked" in result["error_message"].lower()
    assert SpyClient.checkout_calls == 0
    assert outbound.texts and "locked" in outbound.texts[0][1].lower()


@pytest.mark.asyncio
async def test_park_sends_a_signed_reconnect_link():
    pool = await get_db_pool()
    wa_id = _new_wa_id()
    outbound = RecordingWA()

    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await conn.fetchval(
                "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;", wa_id
            )
            inbound_id = await conn.fetchval(
                """
                INSERT INTO grocer.inbound_messages (wa_message_id, user_id, message_type, status)
                VALUES ($1, $2, 'text', 'received') RETURNING id;
                """,
                f"wamid.{uuid.uuid4()}",
                user_id,
            )
        await _park_and_prompt(conn, inbound_id, wa_id, outbound)

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM grocer.inbound_messages WHERE id = $1;", inbound_id
        )
    assert status == "awaiting_link"
    assert outbound.ctas
    url = outbound.ctas[0][3]
    token = url.split("?t=", 1)[1]
    assert url.startswith("https://grocerr.vercel.app?t=")
    assert verify_link_token(token) == wa_id


@pytest.mark.asyncio
async def test_keep_only_new_button_rebuilds_and_reissues_pay():
    pool = await get_db_pool()
    wa_id = _new_wa_id()
    outbound = RecordingWA()
    client = FixtureSwiggyClient(FIXTURES_DIR)

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;", wa_id
        )
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET active_address_id = $2;
            """,
            user_id,
            "addr_01HXYZ",
        )

    result = await handle_webhook(
        SignedRequest(
            _message(
                wa_id,
                button_id="cart:fresh:spin_bread_white:sku_bread:1",
            )
        ),
        swiggy_client=client,
        wa_client=outbound,
    )
    await asyncio.sleep(0.05)

    assert result["status"] == "cart_fresh"
    assert [item.spinId for item in client.get_cart("addr_01HXYZ").items] == [
        "spin_bread_white"
    ]
    async with pool.acquire() as conn:
        approval = await conn.fetchrow(
            "SELECT to_pay_paise FROM grocer.approvals WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1;",
            user_id,
        )
    assert approval is not None
    assert outbound.buttons
    assert outbound.buttons[-1][2][0][0].startswith("pay:")


@pytest.mark.asyncio
async def test_address_question_gets_one_home_reaction(monkeypatch):
    pool = await get_db_pool()
    wa_id = _new_wa_id()
    wamid = f"wamid.{uuid.uuid4()}"
    client = FixtureSwiggyClient(FIXTURES_DIR)
    outbound = RecordingWA()

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;", wa_id
        )
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id, last_active_at)
            VALUES ($1, 'addr_01HXYZ', now())
            ON CONFLICT (user_id) DO UPDATE
            SET active_address_id = 'addr_01HXYZ', last_active_at = now();
            """,
            user_id,
        )
    await store_user_token(user_id=user_id, access_token="swiggy_reaction_token")

    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.LIST_ADDRESSES,
            safety=SafetyClass.READ,
            confidence=1.0,
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, wamid=wamid, text="show my address")),
        swiggy_client=client,
        wa_client=outbound,
    )
    await asyncio.sleep(0.05)

    assert result["status"] == "capability_answered"
    assert result["capability"] == "list_addresses"
    assert outbound.reactions == [(wa_id, wamid, "🏠")]


@pytest.mark.asyncio
async def test_multiple_items_all_land_even_when_one_is_already_in_the_basket(
    monkeypatch,
):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[
                {"query": "milk", "quantity": 1},
                {"query": "bread", "quantity": 1},
            ],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add milk and bread")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "cart_updated"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_amul_1l"] == 3
    assert quantities["spin_bread_white"] == 1


@pytest.mark.asyncio
async def test_adding_an_item_already_in_the_basket_increments_it(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[{"query": "milk", "quantity": 1}],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add 1 more milk")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "cart_updated"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_amul_1l"] == 3
    assert not any(
        "Add 1 more, or make the total" in body
        for _to, body, _buttons in outbound.buttons
    )


@pytest.mark.asyncio
async def test_six_bananas_buys_one_six_pack(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog_with_bananas())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[{"query": "bananas", "quantity": 1, "amount": 6, "unit": "piece"}],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add 6 bananas")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "cart_updated"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_banana_6"] == 1


@pytest.mark.asyncio
async def test_two_bananas_never_buys_a_six_pack(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog_with_bananas())
    outbound = RecordingWA()

    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[{"query": "bananas", "quantity": 1, "amount": 2, "unit": "piece"}],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add 2 bananas")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] != "cart_updated"
    assert client.last_update_items == []
    assert all(
        item.spinId != "spin_banana_6" for item in client.get_cart("addr_01HXYZ").items
    )
    assert _all_bodies(outbound)


@pytest.mark.asyncio
async def test_paneer_rice_case_never_swaps_or_drops(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog_with_paneer_and_rice())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[
                {"query": "paneer", "quantity": 1, "amount": 200, "unit": "g"},
                {
                    "query": "gulab jamun",
                    "quantity": 1,
                    "amount": 1,
                    "unit": "pack",
                },
                {"query": "rice", "quantity": 1, "amount": 500, "unit": "g"},
            ],
        ),
    )

    result = await handle_webhook(
        SignedRequest(
            _message(wa_id, text="add 200g paneer, 1 packet gulab jamun and 500g rice")
        ),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "cart_updated"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_paneer_200g"] == 1
    assert quantities["spin_jamun_500g"] == 1
    assert "spin_paneer_400g" not in quantities
    assert "spin_rice_1kg" not in quantities
    assert any(
        "Not added" in body and "rice 500 g" in body
        for body in _all_bodies(outbound)
    )


@pytest.mark.asyncio
async def test_partial_add_names_the_missing_item(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog_with_bananas())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[
                {"query": "milk", "quantity": 1},
                {"query": "bananas", "quantity": 1, "amount": 2, "unit": "piece"},
            ],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add milk and 2 bananas")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "cart_updated"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_amul_1l"] == 3
    assert any(
        "Not added" in body or "Waiting for your pick" in body
        for body in _all_bodies(outbound)
    )


@pytest.mark.asyncio
async def test_more_than_ten_items_is_refused_before_search(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[{"query": f"item {index}", "quantity": 1} for index in range(11)],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add eleven things")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "too_many_items"
    assert client.last_update_items == []
    assert any("up to 10 items" in text for _to, text in outbound.texts)


@pytest.mark.asyncio
async def test_unsupported_media_gets_one_honest_reply():
    wa_id = _new_wa_id()
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    payload = _message(wa_id, text="")
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    message.pop("text", None)
    message["type"] = "image"
    message["image"] = {"id": "media_01", "mime_type": "image/jpeg"}

    result = await handle_webhook(
        SignedRequest(payload), swiggy_client=client, wa_client=outbound
    )

    assert result["status"] == "unsupported_message"
    assert any("only read text" in text for _to, text in outbound.texts)


@pytest.mark.asyncio
async def test_hourly_rate_limit_stops_a_spammer():
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    async with pool.acquire() as conn:
        for _ in range(20):
            await conn.execute(
                "INSERT INTO grocer.inbound_messages "
                "(user_id, wa_message_id, status, raw_payload) "
                "VALUES ($1, $2, 'processed', '{}'::jsonb);",
                user_id,
                f"wamid.seed.{uuid.uuid4()}",
            )
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="hello")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "rate_limited"
    assert any("too fast" in text for _to, text in outbound.texts)


@pytest.mark.asyncio
async def test_plan_add_tap_writes_every_ingredient_and_reissues_pay(monkeypatch):
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    await _seed_plan(
        pool,
        user_id,
        [
            _plan_row("milk", 1, "spin_amul_1l", "Milk"),
            _plan_row("bread", 1, "spin_bread_white", "Bread", "400 g"),
        ],
    )

    from backend.agent import customer_advocate

    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id="plan:add")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "plan_added"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_amul_1l"] == 3
    assert quantities["spin_bread_white"] == 1
    assert outbound.buttons
    assert outbound.buttons[-1][2][0][0].startswith("pay:")
    assert await _stored_plan(pool, user_id) is None


@pytest.mark.asyncio
async def test_plan_add_tap_writes_nothing_when_an_ingredient_is_missing():
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    await _seed_plan(
        pool,
        user_id,
        [
            _plan_row("milk", 1, "spin_amul_1l", "Milk"),
            _plan_row("unicorn steak", 1, "spin_unicorn", "Unicorn steak", "1 kg"),
        ],
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id="plan:add")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "plan_unavailable"
    assert client.last_update_items == []
    assert outbound.texts
    assert "unicorn steak" in outbound.texts[-1][1]


@pytest.mark.asyncio
async def test_expired_plan_tap_writes_nothing():
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    await _seed_plan(
        pool, user_id, [_plan_row("milk", 1, "spin_amul_1l", "Milk")], minutes=-1
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id="plan:add")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "plan_unavailable"
    assert client.last_update_items == []
    assert "That plan expired" in outbound.texts[-1][1]
    assert await _stored_plan(pool, user_id) is None


@pytest.mark.asyncio
async def test_plan_pick_tap_asks_for_numbers():
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    outbound = RecordingWA()
    await _seed_plan(
        pool, user_id, [_plan_row("milk", 1, "spin_amul_1l", "Milk")]
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id="plan:pick")),
        swiggy_client=FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog()),
        wa_client=outbound,
    )

    assert result["status"] == "plan_pick_requested"
    assert "like 1 and 3" in outbound.texts[-1][1]


@pytest.mark.asyncio
async def test_typed_numbers_add_only_the_chosen_plan_items():
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    wamid = f"wamid.{uuid.uuid4()}"
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    await _seed_plan(
        pool,
        user_id,
        [
            _plan_row("milk", 1, "spin_amul_1l", "Milk"),
            _plan_row("bread", 1, "spin_bread_white", "Bread", "400 g"),
        ],
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, wamid=wamid, text="1")),
        swiggy_client=client,
        wa_client=outbound,
    )
    await asyncio.sleep(0.05)

    assert result["status"] == "plan_picked"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_amul_1l"] == 3
    assert "spin_bread_white" not in quantities
    assert outbound.buttons[-1][2][0][0].startswith("pay:")
    assert outbound.reactions == [(wa_id, wamid, "🛒")]
    assert await _stored_plan(pool, user_id) is None


@pytest.mark.asyncio
async def test_typed_numbers_do_not_hijack_normal_text(monkeypatch):
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    await _seed_plan(
        pool, user_id, [_plan_row("milk", 1, "spin_amul_1l", "Milk")]
    )

    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.CHAT,
            safety=SafetyClass.READ,
            confidence=0.95,
            reply="Tell me what you need.",
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add bread")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "capability_answered"
    assert client.last_update_items == []
    assert await _stored_plan(pool, user_id) is not None


@pytest.mark.asyncio
async def test_expired_plan_numbers_route_normally(monkeypatch):
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()
    await _seed_plan(
        pool, user_id, [_plan_row("milk", 1, "spin_amul_1l", "Milk")], minutes=-1
    )

    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.CHAT,
            safety=SafetyClass.READ,
            confidence=0.95,
            reply="Tell me what you need.",
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="1")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "capability_answered"
    assert client.last_update_items == []
    assert await _stored_plan(pool, user_id) is None


@pytest.mark.asyncio
async def test_second_message_waits_for_the_first_turn_and_is_answered(monkeypatch):
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[{"query": "bread", "quantity": 1}],
        ),
    )

    holder = await pool.acquire()
    assert await holder.fetchval(
        "SELECT pg_try_advisory_lock(hashtext($1));", str(user_id)
    )

    async def release() -> None:
        await asyncio.sleep(0.4)
        await holder.execute(
            "SELECT pg_advisory_unlock(hashtext($1));", str(user_id)
        )

    releaser = asyncio.create_task(release())
    try:
        result = await handle_webhook(
            SignedRequest(_message(wa_id, text="add bread")),
            swiggy_client=client,
            wa_client=outbound,
        )
    finally:
        await releaser
        await pool.release(holder)

    assert result["status"] == "cart_updated"
    assert outbound.buttons
    assert "spin_bread_white" in {
        item.spinId for item in client.get_cart("addr_01HXYZ").items
    }


@pytest.mark.asyncio
async def test_recipe_question_shows_a_plan_and_writes_nothing(monkeypatch):
    pool = await get_db_pool()
    wa_id, user_id = await _seed_text_user(pool)
    wamid = f"wamid.{uuid.uuid4()}"
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.PLAN_MEAL,
            safety=SafetyClass.READ,
            confidence=0.95,
            items=[
                {"query": "milk", "quantity": 2},
                {"query": "bread", "quantity": 1},
            ],
            dish="breakfast",
            servings=2,
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, wamid=wamid, text="make breakfast for 2")),
        swiggy_client=client,
        wa_client=outbound,
    )
    await asyncio.sleep(0.05)

    assert result["status"] == "capability_answered"
    assert result["capability"] == "plan_meal"
    assert client.last_update_items == []
    assert outbound.buttons
    _to, body, buttons = outbound.buttons[-1]
    assert "Breakfast for 2" in body
    assert buttons[0] == ("plan:add", "Add all")
    assert outbound.reactions == [(wa_id, wamid, "🍳")]

    stored = await _stored_plan(pool, user_id)
    assert stored is not None
    assert [row["query"] for row in stored["items"]] == ["milk", "bread"]
    assert stored["servings"] == 2
    assert stored["items"][0]["packs"] == 2


@pytest.mark.asyncio
async def test_duplicate_items_share_one_search_and_add_up(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent import router as router_module
    from backend.agent.router import Capability, RoutingDecision, SafetyClass

    searches: list[str] = []
    original_search = client.search_products

    def counting_search(query: str, *args, **kwargs):
        searches.append(query)
        return original_search(query, *args, **kwargs)

    monkeypatch.setattr(client, "search_products", counting_search)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")
    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    monkeypatch.setattr(
        router_module,
        "route_message",
        lambda *args, **kwargs: RoutingDecision(
            capability=Capability.ADD_ITEMS,
            safety=SafetyClass.BASKET,
            confidence=0.95,
            items=[
                {"query": "milk", "quantity": 1},
                {"query": "Milk", "quantity": 2},
            ],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="milk and milk")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "cart_updated"
    assert len(searches) == 1
    assert len(client.last_update_items) == 1
    assert client.last_update_items[0]["spinId"] == "spin_amul_1l"
    assert client.last_update_items[0]["quantity"] == 5


@pytest.mark.asyncio
async def test_long_receipt_is_sent_whole_with_buttons_after():
    from backend.channels.button_router import RECEIPT_FOLLOW_UP, send_receipt

    outbound = RecordingWA()
    body = "item line\n" * 120

    await send_receipt(outbound, "919876543210", body, [("pay:1", "Pay ₹500")])

    assert outbound.texts[-1] == ("919876543210", body)
    assert outbound.buttons[-1][1] == RECEIPT_FOLLOW_UP
    assert outbound.buttons[-1][2] == [("pay:1", "Pay ₹500")]


@pytest.mark.asyncio
async def test_short_receipt_stays_one_buttons_message():
    from backend.channels.button_router import send_receipt

    outbound = RecordingWA()

    await send_receipt(outbound, "919876543210", "short receipt", [("pay:1", "Pay ₹500")])

    assert outbound.texts == []
    assert outbound.buttons[-1][1] == "short receipt"
