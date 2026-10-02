"""Failure modes that must be rejected before review mode can be trusted.

These cases cover mixed consent, missing money, account isolation, and unknown
checkout outcomes. The assertions are written before their production fixes.
"""
from __future__ import annotations

import asyncio
import copy
import time
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
import httpx

from backend.agent.guards import is_explicit_confirmation
from backend.agent.approval import cart_fingerprint
from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
from backend.agent.engine import GroceryAgentEngine
from backend.agent.tools import SwiggyAgentTools, format_cart_receipt
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.channels.models import InteractiveAction, NormalizedOutgoingResponse
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.integrations.commerce.exceptions import OrderStateUnknownError
from backend.integrations.commerce.exceptions import UpstreamTimeoutError
from backend.integrations.commerce.models import CartItem, CommerceCart, DeliveryAddress
from backend.integrations.commerce.models import CommerceProductItem, ProductVariant
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_client import SwiggyMcpClient
from backend.integrations.commerce.token_vault import SwiggyTokenVault


def test_durable_history_prunes_expired_and_undated_turns() -> None:
    engine = GroceryAgentEngine(MockCommerceAdapter(), state_store=object())
    now = time.time()
    engine._history["customer-1"] = [
        {"role": "user", "parts": [{"text": "old milk"}], "recorded_at": now - 31 * 86400},
        {"role": "model", "parts": [{"text": "old reply"}], "recorded_at": now - 31 * 86400},
        {"role": "user", "parts": [{"text": "unknown age"}]},
        {"role": "user", "parts": [{"text": "fresh bread"}], "recorded_at": now},
        {"role": "model", "parts": [{"text": "fresh reply"}], "recorded_at": now},
    ]

    engine._prune_history("customer-1")

    assert [entry["parts"][0]["text"] for entry in engine.get_history("customer-1")] == [
        "fresh bread", "fresh reply",
    ]


def test_approval_requires_provider_confirmed_delivery_address() -> None:
    item = CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L",
                    quantity=1, unit_price=100, total_price=100)
    assert cart_fingerprint(CommerceCart(cart_id="cart-1", address_id=None,
                                         grand_total=100, items=[item]), "address-1") is None
    assert cart_fingerprint(CommerceCart(cart_id="cart-1", address_id="address-2",
                                         grand_total=100, items=[item]), "address-1") is None


@pytest.mark.asyncio
async def test_paid_but_unplaced_order_remains_on_checkout_hold() -> None:
    class Pool:
        def __init__(self) -> None:
            self.args = None

        async def execute(self, query: str, *args):
            self.args = args
            return "UPDATE 1"

    pool = Pool()
    await PostgresCheckoutAttemptStore(pool).finish(
        "attempt-1", {"success": True, "status": "PAYMENT_CONFIRMED", "order_id": "order-1"},
    )

    assert pool.args[1] == "PAYMENT_PENDING"


def test_whatsapp_identity_requires_full_indian_e164_number() -> None:
    from backend.identity import whatsapp_customer_id

    assert whatsapp_customer_id("+919876543210", "test-secret") == whatsapp_customer_id(
        "919876543210", "test-secret"
    )
    for invalid in ("9876543210", "+19876543210", "+91987654321", "+9198765432100", "abc919876543210"):
        with pytest.raises(ValueError):
            whatsapp_customer_id(invalid, "test-secret")


@pytest.mark.asyncio
async def test_public_login_cannot_bind_an_arbitrary_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.api import oauth as oauth_api

    initiate = AsyncMock()
    monkeypatch.setattr(oauth_api.default_oauth_manager, "initiate_flow", initiate)
    with pytest.raises(Exception) as rejected:
        await oauth_api.swiggy_login(oauth_api.LoginRequest(phone_number="+919876543210"))
    assert getattr(rejected.value, "status_code", None) in (400, 403, 422)
    initiate.assert_not_called()


@pytest.mark.asyncio
async def test_oauth_callback_does_not_reflect_provider_error_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.api import oauth as oauth_api

    monkeypatch.setattr(oauth_api.default_oauth_manager, "exchange_code", AsyncMock(
        side_effect=ValueError("<script>alert('xss')</script>")))
    response = await oauth_api.swiggy_callback_browser(code="bad", state="bad")
    assert response.status_code == 400
    assert b"<script>" not in response.body


@pytest.mark.asyncio
async def test_verified_connect_ticket_is_single_use_and_owns_oauth_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.api import oauth as oauth_api
    from backend.integrations.commerce.connect_tickets import ConnectTickets

    tickets = ConnectTickets()
    monkeypatch.setattr(oauth_api, "default_connect_tickets", tickets)
    initiate = AsyncMock(return_value=("https://provider.invalid/authorize", "state"))
    monkeypatch.setattr(oauth_api.default_oauth_manager, "initiate_flow", initiate)
    ticket = await tickets.issue("verified-alice")
    first = await oauth_api.swiggy_login(oauth_api.LoginRequest(ticket=ticket, phone_number="+919999999999"))
    assert first["authorize_url"] == "https://provider.invalid/authorize"
    assert initiate.await_args.kwargs["customer_id"] == "verified-alice"
    with pytest.raises(Exception) as replay:
        await oauth_api.swiggy_login(oauth_api.LoginRequest(ticket=ticket))
    assert getattr(replay.value, "status_code", None) == 403
    assert initiate.await_count == 1


@pytest.mark.asyncio
async def test_signed_webhook_requires_durable_intake_before_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import hmac
    import json
    from backend.main import create_app
    from backend.channels.whatsapp import default_whatsapp_adapter

    app = create_app()
    app.state.agent_engine = SimpleNamespace(handle_message=AsyncMock())
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "webhook-secret")
    body = json.dumps({"object": "whatsapp_business_account", "entry": [{"changes": [{
        "value": {"messages": [{"id": "durable-required", "from": "919999988888",
                               "type": "text", "text": {"body": "hi"}}]}
    }]}]}).encode()
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        result = await client.post("/api/whatsapp/webhook", content=body,
                                   headers={"X-Hub-Signature-256": f"sha256={signature}"})
    assert result.status_code == 503


@pytest.mark.asyncio
async def test_verified_delete_request_removes_customer_state_without_model_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.api.whatsapp import drain_message_queue
    from backend.integrations.commerce.token_vault import default_token_vault

    message = NormalizedIncomingMessage(
        message_id="delete-request", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="delete my data",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.pending = message
            self.outbound = None
            self.purge_customer = AsyncMock()
            self.request_deletion = AsyncMock()

        async def claim_next(self):
            pending, self.pending = self.pending, None
            return (1, pending) if pending else None

        async def stage_response(self, _id, response):
            self.outbound = response

        async def claim_outbound(self):
            outbound, self.outbound = self.outbound, None
            return (2, "customer-1", outbound) if outbound else None

        async def mark_outbound(self, _id, delivered):
            assert delivered is True

    store = FakeStore()
    engine = SimpleNamespace(handle_message=AsyncMock(), state_store=SimpleNamespace(delete=AsyncMock()),
                             forget_customer=AsyncMock())
    from backend.channels.whatsapp import default_whatsapp_adapter
    monkeypatch.setattr(default_whatsapp_adapter, "send_response", AsyncMock(return_value=True))
    monkeypatch.setattr(default_token_vault, "revoke_token_durable", AsyncMock())

    await drain_message_queue(store, engine)

    engine.handle_message.assert_not_called()
    store.request_deletion.assert_awaited_once_with("customer-1")
    engine.state_store.delete.assert_awaited_once_with("customer-1")
    default_token_vault.revoke_token_durable.assert_awaited_once_with("customer-1")
    store.purge_customer.assert_awaited_once_with("customer-1")


@pytest.mark.asyncio
async def test_liveness_is_separate_from_missing_dependency_readiness() -> None:
    from backend.main import create_app

    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        live = await client.get("/health")
        ready = await client.get("/ready")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert ready.status_code == 503
    assert "missing" in ready.json()


@pytest.mark.parametrize(
    "message",
    ["ok add milk too", "sure, what about eggs?", "yes, change the address", "what's the total?"],
)
def test_mixed_message_never_authorizes_checkout(message: str) -> None:
    assert is_explicit_confirmation(message) is False


def _checkout_turn() -> dict:
    return {"candidates": [{"content": {"parts": [{"functionCall": {
        "name": "checkout", "args": {"cart_id": "cart-1", "address_id": "address-1",
                                     "is_user_confirmed": True},
    }}]}}]}


def _text_turn(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_missing_customer_token_never_uses_another_account() -> None:
    tokens = {"alice": "alice-token"}
    client = SwiggyMcpClient(
        "https://provider.invalid",
        token_resolver=lambda customer_id: tokens.get(customer_id) if customer_id else "alice-token",
    )
    assert client.resolve_token("bob") is None


@pytest.mark.asyncio
async def test_provider_uses_fresh_customer_token_after_another_instance_updates_it() -> None:
    current = {"alice": "first-token"}

    async def resolve(customer_id: str) -> str | None:
        return current.get(customer_id)

    seen: list[str | None] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"result": {"success": True}})

    client = SwiggyMcpClient("https://provider.invalid", token_resolver=resolve)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        await client.call_tool("get_cart", {}, customer_id="alice")
        current["alice"] = "second-token"
        await client.call_tool("get_cart", {}, customer_id="alice")
    finally:
        await client.close()

    assert seen == ["Bearer first-token", "Bearer second-token"]


@pytest.mark.asyncio
async def test_checkout_network_disconnect_is_classified_as_uncertain() -> None:
    client = SwiggyMcpClient("https://provider.invalid", auth_token="test-token")
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(
        httpx.ConnectError("connection dropped", request=request)))
    client._client = httpx.AsyncClient(transport=transport)
    try:
        with pytest.raises(UpstreamTimeoutError):
            await client.call_tool("checkout", {"addressId": "address-1"})
    finally:
        await client.close()


def test_token_vault_requires_explicit_customer_for_lookup() -> None:
    vault = SwiggyTokenVault()
    vault.store_token("alice", "ey.mock.jwt", expires_in=3600)
    assert vault.get_token() is None


def test_legacy_token_file_is_ignored_without_boot_deletion(tmp_path) -> None:
    path = tmp_path / ".vault_tokens.json"
    path.write_text('{"historical":"needs-private-review"}', encoding="utf-8")
    vault = SwiggyTokenVault(persistence_file=str(path))
    assert path.exists()
    assert vault.get_token("historical") is None


def test_live_factory_does_not_use_owner_static_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.config import settings
    from backend.integrations.commerce.factory import get_commerce_adapter

    monkeypatch.setattr(settings, "COMMERCE_ADAPTER_TYPE", "swiggy_mcp")
    monkeypatch.setattr(settings, "SWIGGY_AUTH_TOKEN", "owner-token")
    monkeypatch.setattr(settings, "SWIGGY_CUSTOMER_ID", "owner")
    adapter = get_commerce_adapter()
    assert adapter._resolve_token("owner") is None


@pytest.mark.asyncio
async def test_oauth_callback_does_not_copy_token_to_owner_or_global_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.api import oauth as oauth_api
    from backend.config import settings

    save = AsyncMock()
    monkeypatch.setattr(oauth_api, "default_token_vault", SimpleNamespace(store_token_durable=save))
    monkeypatch.setattr(oauth_api.default_oauth_manager, "exchange_code", AsyncMock(return_value={
        "customer_id": "alice", "access_token": "alice-token", "expires_in": 3600,
    }))
    monkeypatch.setattr(settings, "SWIGGY_CUSTOMER_ID", "bob")
    monkeypatch.setattr(settings, "SWIGGY_AUTH_TOKEN", None)

    result = await oauth_api.swiggy_callback(oauth_api.CallbackRequest(code="code", state="state"))

    assert result == {"success": True}
    assert save.await_count == 1
    assert save.await_args.kwargs["customer_id"] == "alice"
    assert settings.SWIGGY_AUTH_TOKEN is None


@pytest.mark.asyncio
async def test_confirmation_without_reviewed_cart_never_calls_checkout() -> None:
    engine = GroceryAgentEngine(MockCommerceAdapter())
    engine.tools.checkout = AsyncMock()

    result = await engine._execute_tool(
        "checkout", {"cart_id": "cart-1", "address_id": "address-1", "is_user_confirmed": True},
        customer_id="customer-1", address_id="address-1", user_confirmed=True,
    )

    assert result["success"] is False
    assert result["error"] == "CONFIRMATION_REQUIRED"
    engine.tools.checkout.assert_not_called()


@pytest.mark.asyncio
async def test_live_checkout_requires_durable_attempt_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "CHECKOUT_MODE", "live")
    cart = CommerceCart(cart_id="cart-1", address_id="address-1", grand_total=100,
                        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk",
                                        pack_size="1L", quantity=1, unit_price=100, total_price=100)])
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=cart)
    engine = GroceryAgentEngine(commerce)
    engine._record_pending_approval("customer-1", cart, "address-1")
    engine.tools.checkout = AsyncMock()

    result = await engine._execute_tool(
        "checkout", {"cart_id": "cart-1", "address_id": "address-1"},
        customer_id="customer-1", address_id="address-1", user_confirmed=True,
    )

    assert result["error"] == "DURABLE_ATTEMPT_REQUIRED"
    engine.tools.checkout.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_live_checkout_holds_later_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "CHECKOUT_MODE", "live")
    cart = CommerceCart(cart_id="cart-1", address_id="address-1", grand_total=100,
                        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk",
                                        pack_size="1L", quantity=1, unit_price=100, total_price=100)])
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=cart)
    store = SimpleNamespace(start=AsyncMock(side_effect=["attempt-1", None]), finish=AsyncMock())
    engine = GroceryAgentEngine(commerce, attempt_store=store)
    engine.tools.checkout = AsyncMock(return_value={"success": False, "error": "ORDER_STATE_UNKNOWN"})

    engine._record_pending_approval("customer-1", cart, "address-1")
    first = await engine._execute_tool("checkout", {"cart_id": "cart-1", "address_id": "address-1"},
                                       customer_id="customer-1", address_id="address-1", user_confirmed=True)
    engine._record_pending_approval("customer-1", cart, "address-1")
    second = await engine._execute_tool("checkout", {"cart_id": "cart-1", "address_id": "address-1"},
                                        customer_id="customer-1", address_id="address-1", user_confirmed=True)

    assert first["error"] == "ORDER_STATE_UNKNOWN"
    store.finish.assert_awaited_once_with("attempt-1", first)
    assert second["error"] == "ATTEMPT_UNRESOLVED"
    assert engine.tools.checkout.await_count == 1


@pytest.mark.asyncio
async def test_customer_budget_and_history_survive_agent_restart() -> None:
    class FakeStateStore:
        def __init__(self) -> None:
            self.saved: dict[str, dict] = {}

        async def load(self, customer_id: str):
            return copy.deepcopy(self.saved.get(customer_id))

        async def save(self, customer_id: str, state: dict):
            self.saved[customer_id] = copy.deepcopy(state)

    state_store = FakeStateStore()
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=CommerceCart(items=[]))
    commerce.get_addresses = AsyncMock(return_value=[DeliveryAddress(
        id="address-1", label="Home", street="Main Road", city="Pune")])
    first_engine = GroceryAgentEngine(commerce, state_store=state_store)
    first_engine._call_llm = AsyncMock(return_value=_text_turn("I can help."))
    await first_engine.handle_message(NormalizedIncomingMessage(
        message_id="first", channel=ChannelType.WHATSAPP, sender_id="+919876543210",
        customer_id="customer-1", text="groceries under 500 rupees"))
    second_engine = GroceryAgentEngine(commerce, state_store=state_store)
    second_engine._call_llm = AsyncMock(return_value=_text_turn("Okay."))
    await second_engine.handle_message(NormalizedIncomingMessage(
        message_id="second", channel=ChannelType.WHATSAPP, sender_id="+919876543210",
        customer_id="customer-1", text="add milk"))

    assert second_engine.get_session("customer-1").budget_inr == 500
    assert any("under 500" in str(entry) for entry in second_engine.get_history("customer-1"))


@pytest.mark.asyncio
async def test_old_numbered_address_reply_cannot_select_new_choice() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=CommerceCart(items=[]))
    engine = GroceryAgentEngine(commerce)
    engine._awaiting_address_choice["customer-1"] = [
        {"address_id": "address-new", "label": "Home", "_choice_code": "abc123"},
        {"address_id": "address-other", "label": "Work", "_choice_code": "def456"},
    ]
    engine._call_llm = AsyncMock(return_value=_text_turn("Please choose your address."))

    await engine.handle_message(NormalizedIncomingMessage(
        message_id="old-choice", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="1"))

    assert engine._customer_address.get("customer-1") is None
    assert "customer-1" in engine._awaiting_address_choice


@pytest.mark.asyncio
async def test_malformed_model_tool_arguments_never_mutate_cart() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce)
    engine._customer_address["customer-1"] = "address-1"
    engine._order_address_confirmed["customer-1"] = True
    engine.tools.update_cart = AsyncMock()
    malformed = engine._normalize_openai_response({"choices": [{"message": {"tool_calls": [{
        "id": "bad-call", "function": {"name": "update_cart", "arguments": "{bad json"}
    }]}}]})
    engine._call_llm = AsyncMock(side_effect=[malformed, _text_turn("Please restate the items.")])

    await engine.handle_message(NormalizedIncomingMessage(
        message_id="malformed-tool", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="add milk"))

    engine.tools.update_cart.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_or_oversized_cart_proposal_never_reaches_provider() -> None:
    commerce = MockCommerceAdapter()
    commerce.update_cart = AsyncMock()
    tools = SwiggyAgentTools(commerce)

    for items in (
        [{"spin_id": "milk", "quantity": True, "sku_id": "milk-1"}],
        [{"spin_id": "milk", "quantity": 10_000, "sku_id": "milk-1"}],
        [{"spin_id": "milk", "quantity": 1, "sku_id": "milk-1"}] * 31,
    ):
        result = await tools.update_cart(items, "address-1")
        assert result["success"] is False
        assert result["error"] == "INVALID_CART_PROPOSAL"
    commerce.update_cart.assert_not_called()


@pytest.mark.asyncio
async def test_provider_reduced_quantity_is_not_reported_as_complete_cart() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=CommerceCart(items=[]))
    commerce.update_cart = AsyncMock(return_value=CommerceCart(
        cart_id="cart-1", address_id="address-1", grand_total=60,
        items=[CartItem(spin_id="milk", sku_id="milk-1", name="Milk", pack_size="1L",
                        quantity=1, unit_price=60, total_price=60)],
    ))

    result = await SwiggyAgentTools(commerce).update_cart(
        [{"spin_id": "milk", "sku_id": "milk-1", "quantity": 2}], "address-1"
    )

    assert result["success"] is False
    assert result["error"] == "CART_ITEMS_UNRESOLVED"
    assert result["unresolved_items"][0]["requested_quantity"] == 2
    assert result["unresolved_items"][0]["actual_quantity"] == 1


@pytest.mark.asyncio
async def test_failed_cart_read_never_replaces_unknown_basket() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    commerce.update_cart = AsyncMock()

    result = await SwiggyAgentTools(commerce).update_cart(
        [{"spin_id": "milk", "sku_id": "milk-1", "quantity": 1}], "address-1"
    )

    assert result["success"] is False
    assert result["error"] == "CART_UNAVAILABLE"
    commerce.update_cart.assert_not_called()


@pytest.mark.asyncio
async def test_unresolved_requested_item_blocks_checkout_even_after_new_review() -> None:
    cart = CommerceCart(cart_id="cart-1", address_id="address-1", grand_total=60,
                        items=[CartItem(spin_id="milk", sku_id="milk-1", name="Milk",
                                        pack_size="1L", quantity=1, unit_price=60, total_price=60)])
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=cart)
    engine = GroceryAgentEngine(commerce)
    engine._record_pending_approval("customer-1", cart, "address-1")
    engine.get_session("customer-1").unresolved_items = [{
        "spin_id": "milk", "requested_quantity": 2, "actual_quantity": 1,
    }]
    engine.tools.checkout = AsyncMock()

    result = await engine._execute_tool(
        "checkout", {"cart_id": "cart-1", "address_id": "address-1"},
        customer_id="customer-1", address_id="address-1", user_confirmed=True,
    )

    assert result["error"] == "ITEMS_UNRESOLVED"
    engine.tools.checkout.assert_not_called()


@pytest.mark.asyncio
async def test_outside_cart_edit_requires_customer_adoption_before_new_write() -> None:
    from backend.agent.approval import cart_fingerprint

    original = CommerceCart(cart_id="cart-1", address_id="address-1", grand_total=60,
                            items=[CartItem(spin_id="milk", sku_id="milk-1", name="Milk",
                                            pack_size="1L", quantity=1, unit_price=60, total_price=60)])
    changed = original.model_copy(update={"grand_total": 120, "items": [
        CartItem(spin_id="milk", sku_id="milk-1", name="Milk", pack_size="1L",
                 quantity=2, unit_price=60, total_price=120)]})
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=changed)
    engine = GroceryAgentEngine(commerce)
    engine._customer_address["customer-1"] = "address-1"
    engine.get_session("customer-1").known_cart_fingerprint = cart_fingerprint(original, "address-1")
    engine.tools.update_cart = AsyncMock()
    engine._call_llm = AsyncMock(return_value=_text_turn("Adding eggs."))

    result = await engine.handle_message(NormalizedIncomingMessage(
        message_id="outside-edit", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="add eggs"))

    assert result.conversation_state == "NEEDS_DECISION"
    assert "changed" in result.text.casefold()
    engine.tools.update_cart.assert_not_called()


@pytest.mark.asyncio
async def test_changed_cart_invalidates_prior_approval() -> None:
    commerce = MockCommerceAdapter()
    reviewed = CommerceCart(
        cart_id="cart-1", address_id="address-1", grand_total=100,
        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L",
                        quantity=1, unit_price=100, total_price=100)],
    )
    changed = reviewed.model_copy(update={"grand_total": 120})
    commerce.get_cart = AsyncMock(return_value=changed)
    engine = GroceryAgentEngine(commerce)
    engine.tools.checkout = AsyncMock()
    engine._record_pending_approval("customer-1", reviewed, "address-1")

    result = await engine._execute_tool(
        "checkout", {"cart_id": "cart-1", "address_id": "address-1", "is_user_confirmed": True},
        customer_id="customer-1", address_id="address-1", user_confirmed=True,
    )

    assert result["success"] is False
    assert result["error"] == "CART_CHANGED"
    engine.tools.checkout.assert_not_called()


@pytest.mark.asyncio
async def test_non_inr_cart_cannot_be_approved_for_inr_budget() -> None:
    cart = CommerceCart(cart_id="cart-1", address_id="address-1", grand_total=100,
                        currency="USD", items=[CartItem(spin_id="spin-1", sku_id="sku-1",
                                                         name="Milk", pack_size="1L", quantity=1,
                                                         unit_price=100, total_price=100)])
    assert cart_fingerprint(cart, "address-1") is None


@pytest.mark.asyncio
async def test_unknown_checkout_never_claims_no_charge_or_suggests_retry() -> None:
    commerce = MockCommerceAdapter()
    cart = CommerceCart(
        cart_id="cart-1", address_id="address-1", grand_total=100,
        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L",
                        quantity=1, unit_price=100, total_price=100)],
    )
    commerce.get_cart = AsyncMock(return_value=cart)
    engine = GroceryAgentEngine(commerce)
    engine._record_pending_approval("customer-1", cart, "address-1")
    engine._call_llm = AsyncMock(side_effect=[_checkout_turn(), _text_turn("Order placed!")])
    engine.tools.checkout = AsyncMock(return_value={
        "success": False, "error": "ORDER_STATE_UNKNOWN", "retryable": False,
    })

    result = await engine.handle_message(NormalizedIncomingMessage(
        message_id="message-unknown", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="confirm order",
    ))

    assert result.conversation_state == "RECOVERING"
    assert "couldn't verify" in result.text.casefold()
    assert "not charged" not in result.text.casefold()
    assert "try again" not in result.text.casefold()


@pytest.mark.asyncio
async def test_unknown_provider_status_without_error_is_not_called_failed_payment() -> None:
    commerce = MockCommerceAdapter()
    cart = CommerceCart(cart_id="cart-1", address_id="address-1", grand_total=100,
                        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk",
                                        pack_size="1L", quantity=1, unit_price=100, total_price=100)])
    commerce.get_cart = AsyncMock(return_value=cart)
    engine = GroceryAgentEngine(commerce)
    engine._record_pending_approval("customer-1", cart, "address-1")
    engine._call_llm = AsyncMock(side_effect=[_checkout_turn(), _text_turn("Your payment failed")])
    engine.tools.checkout = AsyncMock(return_value={"success": False, "status": "ORDER_STATE_UNKNOWN"})

    result = await engine.handle_message(NormalizedIncomingMessage(
        message_id="unknown-status", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="confirm order"))

    assert result.conversation_state == "RECOVERING"
    assert "not been charged" not in result.text.casefold()


@pytest.mark.asyncio
async def test_live_checkout_failure_never_claims_no_charge_without_provider_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "CHECKOUT_MODE", "live")
    commerce = MockCommerceAdapter()
    cart = CommerceCart(
        cart_id="cart-1", address_id="address-1", grand_total=100,
        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L",
                        quantity=1, unit_price=100, total_price=100)],
    )
    commerce.get_cart = AsyncMock(return_value=cart)
    engine = GroceryAgentEngine(commerce)
    engine._record_pending_approval("customer-1", cart, "address-1")
    engine._call_llm = AsyncMock(side_effect=[_checkout_turn(), _text_turn("Order placed!")])
    engine._execute_tool = AsyncMock(return_value={"success": False, "error": "HIGH_DEMAND"})

    result = await engine.handle_message(NormalizedIncomingMessage(
        message_id="message-live-failure", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="confirm order",
    ))

    assert result.conversation_state == "FAILED"
    assert "not been charged" not in result.text.casefold()
    assert "order status" in result.text.casefold()


@pytest.mark.asyncio
async def test_review_checkout_cannot_be_reported_as_real_order() -> None:
    commerce = MockCommerceAdapter()
    cart = CommerceCart(
        cart_id="cart-1", address_id="address-1", grand_total=100,
        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L",
                        quantity=1, unit_price=100, total_price=100)],
    )
    commerce.get_cart = AsyncMock(return_value=cart)
    engine = GroceryAgentEngine(commerce)
    engine._record_pending_approval("customer-1", cart, "address-1")
    engine._call_llm = AsyncMock(side_effect=[_checkout_turn(), _text_turn("Your order was placed!")])
    engine.tools.checkout = AsyncMock(return_value={
        "success": True, "status": "REVIEW_COMPLETE", "is_simulated": True,
        "message": "No real order was placed.", "grand_total": 100,
    })

    result = await engine.handle_message(NormalizedIncomingMessage(
        message_id="message-review", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="confirm order",
    ))

    assert result.conversation_state == "REVIEW_COMPLETE"
    assert "no real order was placed" in result.text.casefold()


@pytest.mark.asyncio
async def test_cart_writes_and_checkout_execute_in_order() -> None:
    from backend.agent.tool_scheduler import execute_tool_calls

    events: list[str] = []

    async def execute(call: dict) -> str:
        events.append(f"start:{call['name']}:{call['id']}")
        await asyncio.sleep(0)
        events.append(f"end:{call['name']}:{call['id']}")
        return call["id"]

    calls = [
        {"name": "search_products", "id": "read"},
        {"name": "update_cart", "id": "first"},
        {"name": "update_cart", "id": "second"},
        {"name": "checkout", "id": "checkout"},
    ]

    assert await execute_tool_calls(calls, execute) == ["read", "first", "second", "checkout"]
    assert events.index("end:update_cart:first") < events.index("start:update_cart:second")
    assert events.index("end:update_cart:second") < events.index("start:checkout:checkout")


@pytest.mark.asyncio
async def test_failed_clear_does_not_claim_empty_basket() -> None:
    commerce = MockCommerceAdapter()
    commerce.clear_cart = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    engine = GroceryAgentEngine(commerce)
    engine._customer_address["customer-1"] = "address-1"

    result = await engine.handle_message(NormalizedIncomingMessage(
        message_id="message-1", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="clear cart",
    ))

    assert "cleared" not in result.text.casefold()
    assert engine._customer_address["customer-1"] == "address-1"


@pytest.mark.asyncio
async def test_cancel_order_never_clears_cart() -> None:
    commerce = MockCommerceAdapter()
    commerce.clear_cart = AsyncMock()
    engine = GroceryAgentEngine(commerce)
    engine._call_llm = AsyncMock(return_value=None)

    await engine.handle_message(NormalizedIncomingMessage(
        message_id="message-2", channel=ChannelType.WHATSAPP,
        sender_id="+919876543210", customer_id="customer-1", text="cancel order",
    ))

    commerce.clear_cart.assert_not_called()


@pytest.mark.asyncio
async def test_failed_address_migration_does_not_claim_new_destination() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_addresses = AsyncMock(return_value=[DeliveryAddress(
        id="new-address", label="Office", street="Office Road", city="Pune",
    )])
    commerce.get_cart = AsyncMock(return_value=CommerceCart(
        cart_id="cart-1", address_id="old-address", grand_total=100,
        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L",
                        quantity=1, unit_price=100, total_price=100)],
    ))
    commerce.update_cart = AsyncMock(side_effect=RuntimeError("store unavailable"))

    result = await SwiggyAgentTools(commerce).select_delivery_address(
        "customer-1", "new-address"
    )

    assert result["success"] is False
    assert result["error"] == "ADDRESS_CHANGE_FAILED"
    assert "formatted_receipt" not in result


@pytest.mark.asyncio
async def test_search_filters_stock_before_display_cap_and_keeps_limits() -> None:
    products = [CommerceProductItem(
        product_id=f"product-{index}", name=f"Milk {index}", category="dairy",
        variants=[ProductVariant(spin_id=f"spin-{index}", sku_id=f"sku-{index}",
                                 name=f"Milk {index}", pack_size="1L", price=60, mrp=70,
                                 in_stock=index >= 10, max_quantity=2,
                                 max_quantity_message="Only two available")],
    ) for index in range(11)]
    commerce = MockCommerceAdapter()
    commerce.search_products = AsyncMock(return_value=products)

    result = await SwiggyAgentTools(commerce).search_products("milk", "address-1")

    assert result["count"] == 1
    assert result["products"][0]["product_id"] == "product-10"
    assert result["products"][0]["variants"][0]["max_quantity"] == 2


@pytest.mark.asyncio
async def test_long_receipt_keeps_total_and_stops_before_buttons_on_send_failure() -> None:
    adapter = WhatsAppChannelAdapter(phone_number_id="phone-id", access_token="test-token")
    receipt = "Item line\n" * 550 + "*Grand Total: ₹5,500*"
    response = NormalizedOutgoingResponse(
        recipient_id="+919876543210", channel=ChannelType.WHATSAPP,
        text=receipt, conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        interactive_actions=[InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order")],
    )

    payloads = adapter.build_message_payloads(response)
    text_parts = [part["text"]["body"] for part in payloads if part["type"] == "text"]
    assert len(text_parts) >= 2
    assert all(len(part) <= 4096 for part in text_parts)
    assert "".join(text_parts) == receipt
    assert payloads[-1]["type"] == "interactive"

    client = SimpleNamespace(post=AsyncMock(return_value=httpx.Response(500, text="failed")))
    adapter._get_client = AsyncMock(return_value=client)
    assert await adapter.send_response(response) is False
    assert client.post.await_count == 1


@pytest.mark.parametrize("message,expected", [
    ("milk under 2 litres", None),
    ("under 50 rupees each", None),
    ("total under ₹500", 500.0),
    ("budget of 1,000", 1000.0),
    ("groceries under Rs 750", 750.0),
    ("milk under 500", None),
])
def test_total_budget_parser_does_not_confuse_units_or_item_caps(
    message: str, expected: float | None,
) -> None:
    from backend.agent.budget import extract_total_budget
    assert extract_total_budget(message) == expected


def test_provider_billing_difference_is_not_invented_as_a_fee() -> None:
    from backend.integrations.commerce.swiggy_parsers import build_commerce_cart
    basket = {"items": [{"spinId": "spin-1", "skuId": "sku-1", "itemName": "Milk",
                         "quantity": 1, "discountedFinalPrice": 100}],
              "billBreakdown": {"lineItems": [{"label": "Item Total", "value": "₹100"}],
                                "toPay": {"label": "To Pay", "value": "₹130"}}}

    cart = build_commerce_cart(basket)

    assert cart.grand_total == 130
    assert cart.handling_fee == 0
    assert cart.taxes == 0
    assert cart.cart_warning is not None
    assert cart.billing_complete is False
    assert "Reply *Confirm*" not in format_cart_receipt(cart)


def test_missing_provider_payable_total_stays_unknown() -> None:
    from backend.integrations.commerce.swiggy_parsers import build_commerce_cart
    basket = {"items": [{"spinId": "spin-1", "skuId": "sku-1", "itemName": "Milk",
                         "quantity": 1, "discountedFinalPrice": 100}],
              "billBreakdown": {"lineItems": [{"label": "Item Total", "value": "₹100"}]}}

    cart = build_commerce_cart(basket)

    assert cart.grand_total == 0
    assert cart.handling_fee == 0
    assert cart.cart_warning is not None
    assert cart.billing_complete is False


@pytest.mark.asyncio
async def test_http_400_recovery_never_erases_customer_history() -> None:
    engine = GroceryAgentEngine(MockCommerceAdapter(), groq_api_key="test-key")
    history = [
        {"role": "user", "parts": [{"text": "keep my ₹500 budget"}]},
        {"role": "model", "parts": [{"functionCall": {"name": "search_products", "args": {}}}]},
        {"role": "user", "parts": [{"text": "add milk"}]},
    ]
    original = copy.deepcopy(history)
    client = SimpleNamespace(post=AsyncMock(side_effect=[
        httpx.Response(400, text="invalid tool pairing"),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
    ]))
    engine._get_client = AsyncMock(return_value=client)

    assert await engine._call_llm(history) is not None
    assert history == original


@pytest.mark.asyncio
async def test_missing_model_keys_never_send_mock_credential() -> None:
    engine = GroceryAgentEngine(MockCommerceAdapter())
    engine.groq_api_key = None
    engine.openrouter_api_key = None
    engine._get_client = AsyncMock()

    assert await engine._call_llm([{"role": "user", "parts": [{"text": "milk"}]}]) is None
    engine._get_client.assert_not_called()
    assert engine.last_llm_error == "NO_PROVIDER_CONFIGURED"


@pytest.mark.asyncio
async def test_configured_model_provider_is_tried_first_and_clears_old_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.config import settings
    monkeypatch.setattr(settings, "AI_PROVIDER", "openrouter")
    engine = GroceryAgentEngine(
        MockCommerceAdapter(), groq_api_key="groq-key", openrouter_api_key="router-key",
    )
    engine.last_llm_error = "old HTTP 401"
    client = SimpleNamespace(post=AsyncMock(return_value=httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
    )))
    engine._get_client = AsyncMock(return_value=client)

    assert await engine._call_llm([{"role": "user", "parts": [{"text": "milk"}]}]) is not None
    assert "openrouter.ai" in client.post.await_args.args[0]
    assert engine.last_llm_error is None


@pytest.mark.asyncio
async def test_cart_read_failure_blocks_checkout() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(side_effect=RuntimeError("cart unavailable"))
    commerce.checkout = AsyncMock()

    result = await SwiggyAgentTools(commerce).checkout(
        cart_id="cart-1", address_id="address-1", is_user_confirmed=True, budget_inr=500
    )

    assert result["success"] is False
    assert result["error"] == "CART_UNAVAILABLE"
    commerce.checkout.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_payable_total_blocks_checkout() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=CommerceCart(cart_id="cart-1", grand_total=0))
    commerce.checkout = AsyncMock()

    result = await SwiggyAgentTools(commerce).checkout(
        cart_id="cart-1", address_id="address-1", is_user_confirmed=True, budget_inr=500
    )

    assert result["success"] is False
    assert result["error"] == "TOTAL_UNKNOWN"
    commerce.checkout.assert_not_called()


@pytest.mark.asyncio
async def test_ambiguous_checkout_retains_unknown_status() -> None:
    commerce = MockCommerceAdapter()
    commerce.get_cart = AsyncMock(return_value=CommerceCart(
        cart_id="cart-1", grand_total=100,
        items=[CartItem(spin_id="spin-1", sku_id="sku-1", name="Milk", pack_size="1L", quantity=1,
                        unit_price=100, total_price=100)],
    ))
    commerce.checkout = AsyncMock(side_effect=OrderStateUnknownError())

    result = await SwiggyAgentTools(commerce).checkout(
        cart_id="cart-1", address_id="address-1", is_user_confirmed=True
    )

    assert result["success"] is False
    assert result["error"] == "ORDER_STATE_UNKNOWN"
    assert result["retryable"] is False
