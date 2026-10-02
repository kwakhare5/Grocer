"""Adversarial failure-mode tests for critical safety invariants (Tracks E, F, G).

Enforces:
1. CHECKOUT_MODE=review completely blocks upstream MCP checkout calls and returns a safe simulation.
2. TokenVault never writes plaintext credentials to local disk.
3. TokenVault enforces strict customer isolation (no wildcard sharing of owner token with cust_wa_*).
4. Confirmation detection checks negations FIRST ("don't confirm", "not now" are never confirmed; "yes", "confirm" are).
5. Payment tracking poller enforces a minimum 10.0-second interval per Swiggy rate-limit rules.
"""
from __future__ import annotations

import inspect
import pathlib
import pytest
from unittest.mock import AsyncMock

from backend.agent.guards import is_explicit_confirmation
from backend.agent.engine import GroceryAgentEngine
from backend.config import settings
from backend.integrations.commerce.models import CommerceCart, CartItem
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.token_vault import SwiggyTokenVault
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.channels.models import ChannelType, NormalizedOutgoingResponse, InteractiveAction


@pytest.mark.asyncio
async def test_checkout_mode_review_blocks_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """When CHECKOUT_MODE is 'review', checkout MUST NOT call Swiggy MCP tool 'checkout'."""
    monkeypatch.setattr(settings, "CHECKOUT_MODE", "review")
    adapter = SwiggyMCPAdapter(auth_token="dummy_token")

    # Spy on _call_mcp_tool
    mock_mcp_call = AsyncMock()
    monkeypatch.setattr(adapter, "_call_mcp_tool", mock_mcp_call)

    # Mock get_cart to provide current cart context if needed
    mock_cart = CommerceCart(
        cart_id="cart_review_1",
        items=[
            CartItem(
                spin_id="spin_1",
                sku_id="sku_1",
                name="Amul Milk",
                quantity=2,
                unit_price=30.0,
                total_price=60.0,
                pack_size="500ml",
            )
        ],
        item_total=60.0,
        delivery_fee=15.0,
        packaging_fee=5.0,
        handling_fee=0.0,
        taxes=0.0,
        grand_total=80.0,
    )
    monkeypatch.setattr(adapter, "get_cart", AsyncMock(return_value=mock_cart))

    res = await adapter.checkout(
        cart_id="cart_review_1",
        payment_method="UPI",
        explicit_confirmation=True,
        address_id="addr_123",
        payment_option_id="pay_opt_1",
        payment_option_kind="intent",
    )

    # 1. Must NOT call upstream MCP checkout
    mock_mcp_call.assert_not_called()

    # 2. Must return a safe simulated order result
    assert res.is_simulated is True
    assert res.grand_total == 80.0
    assert "REVIEW MODE" in str(res.message) or "REVIEW" in str(res.status)


def test_token_vault_never_writes_plaintext_disk(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TokenVault must not write plaintext tokens to .vault_tokens.json or any file when postgres is absent."""
    vault_file = tmp_path / ".vault_tokens.json"
    monkeypatch.setenv("TOKEN_STORAGE_PATH", str(vault_file))

    vault = SwiggyTokenVault(persistence_file=str(vault_file))
    vault.store_token(
        customer_id="cust_test_1",
        access_token="secret_plain_jwt_token_123",
        expires_in=3600,
    )

    # The file should not exist, or if it does, it must NOT contain the plaintext token
    if vault_file.exists():
        content = vault_file.read_text(encoding="utf-8")
        assert "secret_plain_jwt_token_123" not in content, "Plaintext token leaked to disk!"
    assert vault.get_token("cust_test_1") == "secret_plain_jwt_token_123"


def test_token_vault_customer_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner SWIGGY_AUTH_TOKEN must NOT be leaked to arbitrary cust_wa_* customers."""
    monkeypatch.setattr(settings, "SWIGGY_AUTH_TOKEN", "super_secret_owner_token")
    monkeypatch.setattr(settings, "SWIGGY_CUSTOMER_ID", "9876543210")

    vault = SwiggyTokenVault()
    # A customer with a whatsapp prefix must NOT get the owner's token
    unknown_customer_token = vault.get_token("cust_wa_9999999999")
    assert unknown_customer_token is None, "Owner token was illegally leaked to cust_wa_9999999999!"

    # The actual owner DOES get their configured token
    owner_token = vault.get_token("9876543210")
    assert owner_token == "super_secret_owner_token"


def test_negation_before_confirmation() -> None:
    """Negation phrases must reject confirmation even if they contain 'confirm' or 'order'."""
    assert is_explicit_confirmation("don't confirm") is False
    assert is_explicit_confirmation("dont confirm") is False
    assert is_explicit_confirmation("do not confirm") is False
    assert is_explicit_confirmation("do not order") is False
    assert is_explicit_confirmation("not now") is False
    assert is_explicit_confirmation("stop") is False
    assert is_explicit_confirmation("cancel") is False
    assert is_explicit_confirmation("no, wait a minute") is False
    assert is_explicit_confirmation("wait") is False

    # Positive affirmations must be confirmed
    assert is_explicit_confirmation("confirm") is True
    assert is_explicit_confirmation("confirm order") is True
    assert is_explicit_confirmation("yes") is True
    assert is_explicit_confirmation("yes please") is True
    assert is_explicit_confirmation("proceed") is True
    assert is_explicit_confirmation("ok") is True
    assert is_explicit_confirmation("okay") is True


def test_tracking_cadence_ten_seconds() -> None:
    """_poll_payment_status must enforce a minimum 10.0s interval per Swiggy rate limits."""
    sig = inspect.signature(GroceryAgentEngine._poll_payment_status)
    default_interval = sig.parameters["interval_seconds"].default
    assert default_interval >= 10.0, f"Tracking poll interval {default_interval}s violates Swiggy 10s rule!"


def test_whatsapp_long_receipt_splitting() -> None:
    """When receipt text exceeds 1,000 chars with interactive actions, WhatsApp adapter splits payloads."""
    adapter = WhatsAppChannelAdapter()
    long_receipt_text = "🛒 *Order Summary*\n" + ("Item 1: ₹100\n" * 80) + "\n*Grand Total: ₹8000*"
    assert len(long_receipt_text) > 1000

    resp = NormalizedOutgoingResponse(
        recipient_id="+919876543210",
        channel=ChannelType.WHATSAPP,
        text=long_receipt_text,
        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        interactive_actions=[
            InteractiveAction(action_type="button", id="confirm_order", title="Confirm Order"),
        ],
    )

    payloads = adapter.build_message_payloads(resp)
    # Must produce 2 payloads: full text payload, then button payload
    assert len(payloads) == 2
    assert payloads[0]["type"] == "text"
    assert payloads[0]["text"]["body"] == long_receipt_text
    assert payloads[1]["type"] == "interactive"
    assert payloads[1]["interactive"]["type"] == "button"


@pytest.mark.asyncio
async def test_deterministic_budget_gate() -> None:
    """Deterministic Python code must reject checkout if grand total exceeds session budget_inr."""
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.agent.tools import SwiggyAgentTools

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce=commerce)

    # Set up a cart with total 540
    mock_cart = CommerceCart(
        cart_id="cart_budget_1",
        items=[
            CartItem(
                spin_id="spin_1",
                sku_id="sku_1",
                name="Olive Oil",
                quantity=1,
                unit_price=500.0,
                total_price=500.0,
                pack_size="1L",
            )
        ],
        item_total=500.0,
        delivery_fee=25.0,
        packaging_fee=15.0,
        handling_fee=0.0,
        taxes=0.0,
        grand_total=540.0,
    )
    commerce.get_cart = AsyncMock(return_value=mock_cart)

    # Attempt checkout with budget_inr = 500
    res = await tools.checkout(
        cart_id="cart_budget_1",
        address_id="addr_1",
        payment_method="UPI",
        is_user_confirmed=True,
        budget_inr=500.0,
    )

    assert res["success"] is False
    assert res["error"] == "BUDGET_EXCEEDED"
    assert "exceeds your budget of ₹500" in res["message"]


@pytest.mark.asyncio
async def test_catalog_search_depth_up_to_ten() -> None:
    """Catalog search must return up to 10 items (not sliced at 6) with variant metadata."""
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CommerceProductItem, ProductVariant
    from backend.agent.tools import SwiggyAgentTools

    commerce = MockCommerceAdapter()
    # Mock returning 12 items
    fake_products = [
        CommerceProductItem(
            product_id=f"p_{i}",
            name=f"Item {i}",
            brand="BrandX",
            category="Staples",
            variants=[
                ProductVariant(
                    spin_id=f"spin_{i}",
                    sku_id=f"sku_{i}",
                    name=f"Item {i}",
                    pack_size="500g",
                    price=50.0 + i,
                    mrp=60.0 + i,
                    in_stock=True,
                )
            ],
        )
        for i in range(12)
    ]
    commerce.search_products = AsyncMock(return_value=fake_products)

    tools = SwiggyAgentTools(commerce=commerce)
    res = await tools.search_products(query="items", address_id="addr_1")

    assert res["success"] is True
    assert res["count"] == 10
    assert len(res["products"]) == 10
    first = res["products"][0]["variants"][0]
    assert first["pack_size"] == "500g"
    assert first["savings"] is not None


@pytest.mark.asyncio
async def test_structured_tool_error_payload() -> None:
    """Tools must return structured error objects with reason and retryable classification."""
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.agent.tools import SwiggyAgentTools

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce=commerce)

    # Missing address_id should return structured failure
    res = await tools.search_products(query="milk", address_id="")
    assert res["success"] is False
    assert "error" in res
    assert res.get("retryable") is False


@pytest.mark.asyncio
async def test_prompt_contains_8_step_procedure_and_worked_examples() -> None:
    """Prompt must encode the 8-step procedural shopping protocol and 4 worked examples."""
    from backend.agent.prompts import build_system_instruction

    instruction = build_system_instruction()

    # Verify 8-step procedure
    assert "8-STEP PROCEDURAL SHOPPING PROTOCOL" in instruction
    assert "1. Parse" in instruction
    assert "2. Search" in instruction
    assert "3. Select" in instruction
    assert "4. Pre-check" in instruction
    assert "5. Cart Mutation" in instruction
    assert "6. Budget Enforcement" in instruction
    assert "7. Explain & Receipt" in instruction
    assert "8. Self-Check" in instruction

    # Verify 4 worked examples
    assert "WORKED EXAMPLES" in instruction
    assert "Milk and eggs under Rs 300" in instruction
    assert "No dairy. Buy breakfast" in instruction
    assert "Only this brand; skip if unavailable" in instruction
    assert "Make that two packs, keeping my earlier budget" in instruction


@pytest.mark.asyncio
async def test_react_loop_step_limit_honest_recovery() -> None:
    """When ReAct loop hits 8-step limit without concluding, engine must output honest status and current basket."""
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.channels.models import NormalizedIncomingMessage, ChannelType

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)

    # Mock _call_llm to endlessly propose search_products tool calls
    async def infinite_tool_calls(*args, **kwargs):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "search_products",
                                    "args": {"query": "staple", "address_id": "addr_1"},
                                }
                            }
                        ]
                    }
                }
            ]
        }

    engine._call_llm = infinite_tool_calls  # type: ignore[assignment]

    msg = NormalizedIncomingMessage(
        sender_id="wa:+919876543210",
        message_id="msg_step_limit_1",
        channel=ChannelType.WHATSAPP,
        text="get me huge groceries",
    )
    engine._customer_address[msg.sender_id] = "addr_1"
    engine._order_address_confirmed[msg.sender_id] = True

    resp = await engine.handle_message(msg)

    # Invariant: Must not crash, must not return empty, must provide honest explanation
    assert resp is not None
    assert resp.text
    assert "maximum" in resp.text.casefold() or "steps" in resp.text.casefold()
    assert len(resp.interactive_actions) > 0
    assert all(a.id != "confirm_order" for a in resp.interactive_actions)
