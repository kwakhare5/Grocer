"""Grocer v1.0 — WhatsApp webhook plumbing.

Runs on PostgreSQL with a scripted Swiggy boundary and a recording outbound
client. It proves the exact JSON Meta posts for a button tap reaches the right
handler. It does not prove Meta's delivery or a human tap.
"""

from __future__ import annotations

import asyncio
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
async def test_one_existing_item_asks_add_more_or_make_total(monkeypatch):
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
            items=[{"query": "milk", "quantity": 1}],
        ),
    )

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text="add milk")),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "basket_quantity_choice"
    assert client.last_update_items == []
    assert outbound.buttons
    _to, body, buttons = outbound.buttons[-1]
    assert "Add 1 more, or make the total 1?" in body
    assert buttons == [
        ("cart:addqty:spin_amul_1l:1", "Add 1 more"),
        ("cart:qty:spin_amul_1l:1", "Make total 1"),
    ]


@pytest.mark.asyncio
async def test_plan_add_tap_writes_every_ingredient_and_reissues_pay(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent import customer_advocate
    from backend.agent.meal_planner import encode_plan

    monkeypatch.setattr(customer_advocate, "optimize_coupons", lambda **kwargs: None)
    button_id = encode_plan([("milk", 1), ("bread", 1)])
    assert button_id is not None

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id=button_id)),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "plan_added"
    quantities = {item.spinId: item.quantity for item in client.get_cart("addr_01HXYZ").items}
    assert quantities["spin_amul_1l"] == 3
    assert quantities["spin_bread_white"] == 1
    assert outbound.buttons
    assert outbound.buttons[-1][2][0][0].startswith("pay:")


@pytest.mark.asyncio
async def test_plan_add_tap_writes_nothing_when_an_ingredient_is_missing():
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
    client = FixtureSwiggyClient(FIXTURES_DIR, catalog_data=_catalog())
    outbound = RecordingWA()

    from backend.agent.meal_planner import encode_plan

    button_id = encode_plan([("milk", 1), ("unicorn steak", 1)])
    assert button_id is not None

    result = await handle_webhook(
        SignedRequest(_message(wa_id, button_id=button_id)),
        swiggy_client=client,
        wa_client=outbound,
    )

    assert result["status"] == "plan_unavailable"
    assert client.last_update_items == []
    assert outbound.texts
    assert "unicorn steak" in outbound.texts[-1][1]


@pytest.mark.asyncio
async def test_recipe_question_shows_a_plan_and_writes_nothing(monkeypatch):
    pool = await get_db_pool()
    wa_id, _user_id = await _seed_text_user(pool)
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
    assert buttons[0][1] == "Add all"
    assert outbound.reactions == [(wa_id, wamid, "🍳")]
