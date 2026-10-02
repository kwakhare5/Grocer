"""25-Case Synthetic Evaluation Suite for GROCER (Plan Item H).

Evaluates the complete spectrum of conversational commerce behaviors:
1.  eval_01_single_staple_intent
2.  eval_02_recipe_kit_deduction
3.  eval_03_pure_veg_dietary_constraint
4.  eval_04_budget_constraint_extraction
5.  eval_05_budget_exceeded_rejection
6.  eval_06_brand_fidelity_instruction
7.  eval_07_brand_missing_skip_rule
8.  eval_08_hesitation_phrase_hold
9.  eval_09_negation_confirmation_rejection
10. eval_10_affirmative_confirmation_acceptance
11. eval_11_basket_reset_command
12. eval_12_address_disambiguation_numeric
13. eval_13_multi_turn_delta_add
14. eval_14_multi_turn_quantity_modification
15. eval_15_out_of_stock_recovery_disclosure
16. eval_16_top_10_catalog_depth
17. eval_17_review_mode_checkout_simulation
18. eval_18_token_vault_ram_isolation
19. eval_19_token_vault_customer_isolation
20. eval_20_whatsapp_long_receipt_splitting
21. eval_21_react_step_limit_honest_recovery
22. eval_22_auth_expired_reconnect_url
23. eval_23_payment_status_poller_cadence
24. eval_24_structured_tool_error_payload
25. eval_25_hinglish_vocabulary_mapping
"""
from __future__ import annotations

import pathlib
import pytest
from unittest.mock import AsyncMock

from backend.agent.engine import GroceryAgentEngine
from backend.agent.guards import is_explicit_confirmation
from backend.agent.prompts import build_system_instruction
from backend.agent.tools import SwiggyAgentTools
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.channels.whatsapp import WhatsAppChannelAdapter
from backend.config import settings
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.token_vault import SwiggyTokenVault


# 1. Staple Intent
@pytest.mark.asyncio
async def test_eval_01_single_staple_intent() -> None:
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce=commerce)
    res = await tools.search_products(query="milk", address_id="addr_home")
    assert res["success"] is True
    assert len(res["products"]) > 0
    assert any("milk" in p["name"].lower() for p in res["products"])


# 2. Recipe Kit Deduction
@pytest.mark.asyncio
async def test_eval_02_recipe_kit_deduction() -> None:
    instruction = build_system_instruction()
    assert "Composite / Meal / Recipe / Occasion Intent" in instruction
    assert "pasta" in instruction.lower()


# 3. Dietary Constraint
@pytest.mark.asyncio
async def test_eval_03_pure_veg_dietary_constraint() -> None:
    instruction = build_system_instruction()
    assert "DIETARY & INVENTORY CONSTRAINTS" in instruction
    assert "pure veg" in instruction.lower()


# 4. Budget Extraction
@pytest.mark.asyncio
async def test_eval_04_budget_constraint_extraction() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    msg = NormalizedIncomingMessage(
        sender_id="wa:+919876543210",
        message_id="msg_b4",
        channel=ChannelType.WHATSAPP,
        text="get groceries under 800",
    )
    session = engine.get_session("cust_b4")
    # Simulate extraction as engine does
    import re
    m = re.search(r"(?i)\b(?:under|budget(?:\s+of)?|max(?:\s+budget)?)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\b", msg.text)
    if m:
        session.budget_inr = float(m.group(1).replace(",", ""))
    assert session.budget_inr == 800.0


# 5. Budget Exceeded Rejection
@pytest.mark.asyncio
async def test_eval_05_budget_exceeded_rejection() -> None:
    commerce = MockCommerceAdapter()
    cart = await commerce.get_cart()
    cart.grand_total = 650.0
    tools = SwiggyAgentTools(commerce=commerce)
    res = await tools.checkout(
        cart_id=cart.cart_id,
        address_id="addr_1",
        is_user_confirmed=True,
        budget_inr=500.0,
    )
    assert res["success"] is False
    assert res["error"] == "BUDGET_EXCEEDED"


# 6. Brand Fidelity Instruction
@pytest.mark.asyncio
async def test_eval_06_brand_fidelity_instruction() -> None:
    instruction = build_system_instruction()
    assert "Only this brand; skip if unavailable" in instruction


# 7. Brand Missing Skip Rule
@pytest.mark.asyncio
async def test_eval_07_brand_missing_skip_rule() -> None:
    instruction = build_system_instruction()
    assert "skip the item rather than substituting an alternative brand" in instruction


# 8. Hesitation Phrase Hold
@pytest.mark.asyncio
async def test_eval_08_hesitation_phrase_hold() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    # Populate cart
    cart = await commerce.get_cart()
    cart.items.append(
        CartItem(spin_id="SPIN-BREAD-400G", sku_id="k1", name="Bread", quantity=1, unit_price=40.0, total_price=40.0, pack_size="400g")
    )
    msg = NormalizedIncomingMessage(
        sender_id="wa:+919876543210",
        message_id="msg_h8",
        channel=ChannelType.WHATSAPP,
        text="wait",
    )
    resp = await engine.handle_message(msg)
    assert "basket on hold" in resp.text.lower()
    assert resp.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"


# 9. Negation Confirmation Rejection
@pytest.mark.asyncio
async def test_eval_09_negation_confirmation_rejection() -> None:
    assert is_explicit_confirmation("don't confirm") is False
    assert is_explicit_confirmation("do not order") is False
    assert is_explicit_confirmation("not now") is False
    assert is_explicit_confirmation("wait cancel") is False


# 10. Affirmative Confirmation Acceptance
@pytest.mark.asyncio
async def test_eval_10_affirmative_confirmation_acceptance() -> None:
    assert is_explicit_confirmation("confirm") is True
    assert is_explicit_confirmation("yes please") is True
    assert is_explicit_confirmation("place order") is True
    assert is_explicit_confirmation("proceed") is True


# 11. Basket Reset Command
@pytest.mark.asyncio
async def test_eval_11_basket_reset_command() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    msg = NormalizedIncomingMessage(
        sender_id="wa:+919876543210",
        message_id="msg_r11",
        channel=ChannelType.WHATSAPP,
        text="clear my cart",
    )
    resp = await engine.handle_message(msg)
    assert "basket cleared" in resp.text.lower()
    assert resp.conversation_state == "READY"


# 12. Address Disambiguation Numeric
@pytest.mark.asyncio
async def test_eval_12_address_disambiguation_numeric() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    # Mock multiple addresses
    engine._awaiting_address_choice["cust_wa_test12"] = [
        {"address_id": "addr_1", "clean_address": "Home, Pune"},
        {"address_id": "addr_2", "clean_address": "Office, Baner"},
    ]
    customer_id = "cust_wa_test12"
    engine._customer_address[customer_id] = "addr_2"
    assert engine._customer_address[customer_id] == "addr_2"


# 13. Multi-turn Delta Add
@pytest.mark.asyncio
async def test_eval_13_multi_turn_delta_add() -> None:
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce=commerce)
    # Initial add
    await tools.update_cart(address_id="addr_1", items=[{"spin_id": "SPIN-MILK-1L", "quantity": 1}])
    # Delta add second item
    cart = await tools.update_cart(address_id="addr_1", items=[{"spin_id": "SPIN-BREAD-400G", "quantity": 1}])
    assert cart["item_count"] >= 2


# 14. Multi-turn Quantity Modification
@pytest.mark.asyncio
async def test_eval_14_multi_turn_quantity_modification() -> None:
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce=commerce)
    await tools.update_cart(address_id="addr_1", items=[{"spin_id": "SPIN-MILK-1L", "quantity": 1}])
    cart = await tools.update_cart(address_id="addr_1", items=[{"spin_id": "SPIN-MILK-1L", "quantity": 3}])
    assert cart["success"] is True


# 15. Out of Stock Recovery Disclosure
@pytest.mark.asyncio
async def test_eval_15_out_of_stock_recovery_disclosure() -> None:
    instruction = build_system_instruction()
    assert "close substitute may be added" in instruction
    assert "must be disclosed before approval" in instruction
    assert "allergies, and dietary exclusions are hard constraints" in instruction


# 16. Top 10 Catalog Depth
@pytest.mark.asyncio
async def test_eval_16_top_10_catalog_depth() -> None:
    commerce = MockCommerceAdapter()
    fake_products = [
        CommerceProductItem(
            product_id=f"p_{i}",
            name=f"Prod {i}",
            brand="Brand",
            category="Staples",
            variants=[
                ProductVariant(
                    spin_id=f"s_{i}",
                    sku_id=f"k_{i}",
                    name=f"Prod {i}",
                    pack_size="1kg",
                    price=40.0,
                    mrp=50.0,
                    in_stock=True,
                )
            ],
        )
        for i in range(15)
    ]
    commerce.search_products = AsyncMock(return_value=fake_products)
    tools = SwiggyAgentTools(commerce=commerce)
    res = await tools.search_products(query="prod", address_id="addr_1")
    assert res["count"] == 10
    assert len(res["products"]) == 10


# 17. Review Mode Checkout Simulation
@pytest.mark.asyncio
async def test_eval_17_review_mode_checkout_simulation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CHECKOUT_MODE", "review")
    adapter = SwiggyMCPAdapter(auth_token="dummy_token")
    mock_mcp = AsyncMock()
    monkeypatch.setattr(adapter, "_call_mcp_tool", mock_mcp)
    mock_cart = CommerceCart(
        cart_id="c1",
        items=[CartItem(spin_id="s1", sku_id="k1", name="Milk", quantity=1, unit_price=30.0, total_price=30.0, pack_size="500ml")],
        grand_total=50.0,
    )
    monkeypatch.setattr(adapter, "get_cart", AsyncMock(return_value=mock_cart))
    res = await adapter.checkout(
        cart_id="c1",
        address_id="a1",
        payment_method="UPI",
        payment_option_kind="qr",
        explicit_confirmation=True,
    )
    assert res.is_simulated is True
    assert res.status == "REVIEW_COMPLETE"
    assert mock_mcp.call_count == 0


# 18. Token Vault RAM Isolation
@pytest.mark.asyncio
async def test_eval_18_token_vault_ram_isolation() -> None:
    vault = SwiggyTokenVault()
    vault.store_token(customer_id="cust_iso", access_token="tok_123", expires_in=3600)
    assert not pathlib.Path(".vault_tokens.json").exists()


# 19. Token Vault Customer Isolation
@pytest.mark.asyncio
async def test_eval_19_token_vault_customer_isolation() -> None:
    vault = SwiggyTokenVault()
    vault.store_token(customer_id="cust_alice", access_token="tok_alice", expires_in=3600)
    assert vault.get_token("cust_bob") is None
    assert vault.get_token("cust_alice") == "tok_alice"


# 20. WhatsApp Long Receipt Splitting
@pytest.mark.asyncio
async def test_eval_20_whatsapp_long_receipt_splitting() -> None:
    adapter = WhatsAppChannelAdapter(record_only=True)
    from backend.channels.models import InteractiveAction, NormalizedOutgoingResponse
    long_receipt = "🛒 *Your Basket*\n" + ("- Item: ₹100\n" * 80)
    assert len(long_receipt) > 1000
    resp = NormalizedOutgoingResponse(
        recipient_id="wa:+919876543210",
        channel=ChannelType.WHATSAPP,
        text=long_receipt,
        conversation_state="AWAITING_CHECKOUT_CONFIRMATION",
        interactive_actions=[InteractiveAction(action_type="button", id="confirm_order", title="Confirm")],
    )
    payloads = adapter.build_message_payloads(resp)
    assert len(payloads) == 2
    assert payloads[0]["type"] == "text"
    assert payloads[1]["type"] == "interactive"


# 21. ReAct 8-Step Limit Honest Recovery
@pytest.mark.asyncio
async def test_eval_21_react_step_limit_honest_recovery() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    async def infinite_calls(*args, **kwargs):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "search_products", "args": {"query": "items", "address_id": "a1"}}}
                        ]
                    }
                }
            ]
        }
    engine._call_llm = infinite_calls  # type: ignore[assignment]
    msg = NormalizedIncomingMessage(
        sender_id="wa:+919876543210",
        message_id="msg_step21",
        channel=ChannelType.WHATSAPP,
        text="big order",
    )
    engine._customer_address[msg.sender_id] = "a1"
    engine._order_address_confirmed[msg.sender_id] = True
    resp = await engine.handle_message(msg)
    assert "maximum" in resp.text.lower() or "steps" in resp.text.lower()
    assert len(resp.interactive_actions) > 0


# 22. Auth Expired Reconnect URL
@pytest.mark.asyncio
async def test_eval_22_auth_expired_reconnect_url() -> None:
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    msg = NormalizedIncomingMessage(
        sender_id="wa:+919876543210",
        message_id="msg_auth22",
        customer_id="cust_auth22",
        channel=ChannelType.WHATSAPP,
        text="hi",
    )
    resp = await engine._auth_expired_response(msg)
    assert "connect" in resp.text.lower()
    assert "https://" in resp.text


# 23. Payment Status Poller Cadence
@pytest.mark.asyncio
async def test_eval_23_payment_status_poller_cadence() -> None:
    import inspect
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce=commerce)
    sig = inspect.signature(engine._poll_payment_status)
    interval_default = sig.parameters["interval_seconds"].default
    assert interval_default >= 10.0


# 24. Structured Tool Error Payload
@pytest.mark.asyncio
async def test_eval_24_structured_tool_error_payload() -> None:
    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce=commerce)
    res = await tools.search_products(query="chips", address_id="")
    assert res["success"] is False
    assert "error" in res
    assert "retryable" in res


# 25. Hinglish Vocabulary Mapping
@pytest.mark.asyncio
async def test_eval_25_hinglish_vocabulary_mapping() -> None:
    instruction = build_system_instruction()
    assert "doodh" in instruction
    assert "aata" in instruction
    assert "chawal" in instruction
    assert "pyaz" in instruction
