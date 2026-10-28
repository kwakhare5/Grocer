"""Grocer — Phase 5 account and address lifecycle.

Runs on PostgreSQL. The Swiggy boundary is a scripted client so store-specific
behavior (an item missing at the new address, an active delivery) can be forced;
nothing here claims live Swiggy behavior.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from backend.agent.address_actions import (
    apply_delete,
    apply_switch,
    ensure_active_address,
    resolve_default_address,
)
from backend.agent.address_lifecycle import AddressOnboardingFlow, OnboardingStep
from backend.agent.read_actions import ReadReply
from backend.channels.link_tokens import issue_link_token, verify_link_token
from backend.channels.swiggy_auth import replay_parked_request
from backend.config import settings
from backend.database import get_db_pool
from backend.integrations.commerce.schemas import (
    AddressPagination,
    AddressResolution,
    CartData,
    CartItem,
    ClearCartData,
    CreateAddressData,
    DeleteAddressData,
    GetAddressesData,
    OrderHistoryItem,
    OrdersListData,
    RecommendAddressData,
    SavedAddress,
)
from backend.integrations.commerce.token_vault import store_user_token

pytestmark = [pytest.mark.db, pytest.mark.scripted]


def _address(address_id: str, label: str) -> SavedAddress:
    return SavedAddress(
        id=address_id,
        addressLine=f"{label} line, Bengaluru",
        addressCategory="HOME",
        addressTag=label,
    )


def _addresses(addresses: list[SavedAddress], default_id: str) -> GetAddressesData:
    return GetAddressesData(
        addresses=addresses,
        pagination=AddressPagination(
            page=1,
            pageSize=10,
            total=len(addresses),
            totalPages=1,
            hasMore=False,
        ),
        resolution=AddressResolution(
            defaultAddressId=default_id, resolutionSource="user_selected_address"
        ),
    )


def _cart(items: list[tuple[str, str, int, bool]]) -> CartData:
    cart_items = [
        CartItem(
            spinId=spin,
            skuId=f"sku_{spin}",
            productId=f"prod_{spin}",
            itemName=name,
            quantity=quantity,
            isInStockAndAvailable=in_stock,
            mrp=50.0,
            discountedFinalPrice=50.0,
        )
        for spin, name, quantity, in_stock in items
    ]
    return CartData(
        cartId="cart_stub",
        cartTotalAmount="50.00",
        items=cart_items,
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": "₹50.00"}],
            "toPay": {"label": "To Pay", "value": "₹55.00"},
        },
    )


class StubSwiggy:
    """Scripted Swiggy boundary for account flows only."""

    def __init__(
        self,
        addresses: GetAddressesData,
        carts: dict[str, CartData] | None = None,
        orders: OrdersListData | None = None,
        drop_spins: set[str] | None = None,
    ) -> None:
        self.addresses = addresses
        self.carts = {key: value for key, value in (carts or {}).items()}
        self.orders = orders or OrdersListData(orders=[])
        self.drop_spins = drop_spins or set()
        self.clear_calls = 0
        self.last_update: tuple[list[dict[str, Any]], str | None] | None = None
        self.delete_calls = 0
        self.created: dict[str, Any] | None = None

    def get_addresses(self, page: int = 1, page_size: int = 10) -> GetAddressesData:
        return self.addresses

    def get_cart(self, address_id: str | None = None) -> CartData:
        return self.carts.get(address_id or "", CartData(
            cartTotalAmount="0.00",
            items=[],
            billBreakdown={
                "lineItems": [],
                "toPay": {"label": "To Pay", "value": "₹0.00"},
            },
        ))

    def clear_cart(self) -> ClearCartData:
        self.clear_calls += 1
        self.carts = {}
        return ClearCartData(verified=True)

    def update_cart(
        self, items: list[dict[str, Any]], address_id: str | None = None
    ) -> CartData:
        self.last_update = (items, address_id)
        cart = _cart(
            [
                (item["spinId"], item["spinId"], item["quantity"], True)
                for item in items
                if item["spinId"] not in self.drop_spins
            ]
        )
        self.carts[address_id or ""] = cart
        return cart

    def get_orders(
        self,
        count: int = 20,
        order_type: str = "INSTAMART",
        active_only: bool = True,
    ) -> OrdersListData:
        return self.orders

    def delete_address(self, address_id: str) -> DeleteAddressData:
        self.delete_calls += 1
        return DeleteAddressData(statusCode=200, statusMessage="deleted")

    def recommend_address(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        query: str | None = None,
    ) -> RecommendAddressData:
        if query is not None and "nowhere" in query:
            raise ValueError("no match")
        return RecommendAddressData(
            latitude=12.93,
            longitude=77.62,
            formattedAddress=f"{query}, Bengaluru",
        )

    def create_address(self, **kwargs: Any) -> CreateAddressData:
        self.created = kwargs
        return CreateAddressData(addressId="addr_created_01")


async def _user(pool: Any) -> tuple[str, uuid.UUID]:
    wa_id = f"91{uuid.uuid4().int % 10000000000:010d}"
    user_id = await pool.fetchval(
        "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;", wa_id
    )
    return wa_id, user_id


def test_default_address_wins_over_list_order():
    data = _addresses(
        [_address("addr_first", "Home"), _address("addr_default", "Work")],
        default_id="addr_default",
    )
    assert resolve_default_address(data).id == "addr_default"


@pytest.mark.asyncio
async def test_session_grounds_to_the_default_address():
    pool = await get_db_pool()
    _, user_id = await _user(pool)
    client = StubSwiggy(
        _addresses(
            [_address("addr_first", "Home"), _address("addr_default", "Work")],
            default_id="addr_default",
        )
    )
    async with pool.acquire() as conn:
        resolved = await ensure_active_address(conn, user_id, client)
        saved = await conn.fetchval(
            "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
            user_id,
        )
    assert resolved == "addr_default"
    assert saved == "addr_default"


@pytest.mark.asyncio
async def test_switch_clears_and_rebuilds_at_the_new_store():
    pool = await get_db_pool()
    _, user_id = await _user(pool)
    client = StubSwiggy(
        _addresses([_address("addr_old", "Home"), _address("addr_new", "Work")], "addr_old"),
        carts={
            "addr_old": _cart(
                [
                    ("spin_milk", "Amul Taaza Toned Milk", 2, True),
                    ("spin_eggs", "Farm Eggs 6", 1, False),
                ]
            )
        },
    )
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO grocer.sessions (user_id, active_address_id, last_active_at)
            VALUES ($1, 'addr_old', now());
            """,
            user_id,
        )
        reply = await apply_switch(client, conn, user_id, "addr_new")
        saved = await conn.fetchval(
            "SELECT active_address_id FROM grocer.sessions WHERE user_id = $1;",
            user_id,
        )

    assert isinstance(reply, ReadReply)
    assert saved == "addr_new"
    assert client.clear_calls == 1
    items, address_id = client.last_update
    assert address_id == "addr_new"
    assert [item["spinId"] for item in items] == ["spin_milk"]
    assert "Moved 1 of 1" in reply.text


@pytest.mark.asyncio
async def test_switch_names_what_the_new_store_cannot_fill():
    pool = await get_db_pool()
    _, user_id = await _user(pool)
    client = StubSwiggy(
        _addresses([_address("addr_old", "Home"), _address("addr_new", "Work")], "addr_old"),
        carts={
            "addr_old": _cart(
                [
                    ("spin_milk", "Amul Taaza Toned Milk", 2, True),
                    ("spin_bread", "Whole Wheat Bread", 1, True),
                ]
            )
        },
        drop_spins={"spin_bread"},
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO grocer.sessions (user_id, active_address_id) VALUES ($1, 'addr_old');",
            user_id,
        )
        reply = await apply_switch(client, conn, user_id, "addr_new")

    assert "Moved 1 of 2" in reply.text
    assert "spin_bread" in reply.text or "Whole Wheat Bread" in reply.text


@pytest.mark.asyncio
async def test_delete_is_blocked_while_a_delivery_is_in_flight():
    client = StubSwiggy(
        _addresses([_address("addr_home", "Home"), _address("addr_work", "Work")], "addr_home"),
        orders=OrdersListData(
            orders=[
                OrderHistoryItem(
                    orderId="order_live_1",
                    status="OUT_FOR_DELIVERY",
                    createdAt="2026-10-27T10:00:00Z",
                    itemCount=2,
                    totalAmount=150.0,
                    isActive=True,
                    deliveryAddress={"id": "addr_work"},
                )
            ]
        ),
    )
    reply = await apply_delete(client, "addr_home", "addr_work")

    assert "active delivery" in reply.text
    assert client.delete_calls == 0


@pytest.mark.asyncio
async def test_delete_runs_when_nothing_is_in_flight():
    client = StubSwiggy(
        _addresses([_address("addr_home", "Home"), _address("addr_work", "Work")], "addr_home")
    )
    reply = await apply_delete(client, "addr_home", "addr_work")

    assert "Deleted" in reply.text
    assert client.delete_calls == 1


def test_typed_address_with_pin_asks_only_for_the_name():
    client = StubSwiggy(
        _addresses([_address("addr_home", "Home")], "addr_home")
    )
    flow = AddressOnboardingFlow(client)
    turn = flow.start_from_text("Add my address: Flat 402, Green Glen Layout, Bengaluru 560103")

    assert turn.next_step == OnboardingStep.AWAITING_NAME
    assert turn.context["latitude"] == 12.93
    assert turn.context["postal_code"] == "560103"

    done = flow.advance(turn.next_step, turn.context, text="Karan", wa_id="919876543210")
    assert done.completed is True
    assert done.address_id == "addr_created_01"
    assert client.created["postal_code"] == "560103"
    assert client.created["user_name"] == "Karan"


def test_typed_address_without_pin_asks_for_city_and_pin():
    client = StubSwiggy(
        _addresses([_address("addr_home", "Home")], "addr_home")
    )
    flow = AddressOnboardingFlow(client)
    turn = flow.start_from_text("Save address: 12 Green Glen Layout, Bellandur")

    assert turn.next_step == OnboardingStep.AWAITING_NAME
    after_name = flow.advance(turn.next_step, turn.context, text="Karan", wa_id="9198")
    assert after_name.next_step == OnboardingStep.AWAITING_CITY_PIN

    done = flow.advance(
        after_name.next_step, after_name.context, text="Bengaluru, 560103", wa_id="9198"
    )
    assert done.completed is True


def test_typed_address_that_cannot_be_found_is_honest():
    client = StubSwiggy(
        _addresses([_address("addr_home", "Home")], "addr_home")
    )
    flow = AddressOnboardingFlow(client)
    turn = flow.start_from_text("add address nowhere at all thanks")

    assert turn.next_step == OnboardingStep.AWAITING_LOCATION
    assert "couldn't find" in turn.prompt.lower()


def test_link_token_roundtrip_and_tampering():
    token = issue_link_token("919876543210")
    assert verify_link_token(token) == "919876543210"

    parts = token.split(".")
    flipped = "1" if parts[2][-1] == "0" else "0"
    assert verify_link_token(f"{parts[0]}.{parts[1]}.{parts[2][:-1]}{flipped}") is None
    assert verify_link_token(issue_link_token("919876543210", ttl_seconds=-10)) is None
    assert verify_link_token("not-a-token") is None


def test_login_rejects_a_caller_supplied_phone():
    from fastapi import HTTPException

    from backend.channels.swiggy_auth import LoginRequest, swiggy_login

    request = LoginRequest(token="919876543210.9999999999.deadbeef")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(swiggy_login(request))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_replay_reruns_a_parked_text_once(monkeypatch):
    pool = await get_db_pool()
    wa_id, user_id = await _user(pool)
    await store_user_token(user_id=user_id, access_token="swiggy_replay_token")

    message = {
        "from": wa_id,
        "id": "wamid.parked.1",
        "timestamp": "1",
        "type": "text",
        "text": {"body": "milk"},
    }
    async with pool.acquire() as conn:
        parked_id = await conn.fetchval(
            """
            INSERT INTO grocer.inbound_messages (wa_message_id, user_id, message_type, raw_payload, status)
            VALUES ($1, $2, 'text', $3::jsonb, 'awaiting_link') RETURNING id;
            """,
            "wamid.parked.1",
            user_id,
            __import__("json").dumps(message),
        )

    class RecordingWA:
        def __init__(self) -> None:
            self.texts: list[str] = []

        async def mark_read(self, message_id: str) -> None:
            return None

        async def send_text_message(self, to_wa_id: str, text: str) -> None:
            self.texts.append(text)

        async def send_quick_reply_buttons(self, *args: Any, **kwargs: Any) -> None:
            return None

        async def send_cta_url_button(self, *args: Any, **kwargs: Any) -> None:
            return None

    monkeypatch.setattr(settings, "LLM_PROVIDER", "scripted")

    client = StubSwiggy(
        _addresses([_address("addr_home", "Home")], "addr_home"),
        carts={"addr_home": _cart([("spin_milk", "Amul Taaza Toned Milk", 1, True)])},
    )
    outbound = RecordingWA()
    result = await replay_parked_request(
        user_id, wa_client=outbound, swiggy_client=client
    )

    async with pool.acquire() as conn:
        parked_status = await conn.fetchval(
            "SELECT status FROM grocer.inbound_messages WHERE id = $1;", parked_id
        )
        replay_rows = await conn.fetchval(
            "SELECT count(*) FROM grocer.inbound_messages WHERE user_id = $1 AND wa_message_id LIKE 'wamid.replay.%';",
            user_id,
        )

    assert result is not None
    assert parked_status == "replayed"
    assert replay_rows == 1
    assert outbound.texts
