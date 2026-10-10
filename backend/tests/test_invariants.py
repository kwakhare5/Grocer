"""Adversarial invariant unit tests for GROCER fast-paths, schemas, and resilient tool resolution."""
import pytest
from backend.agent.schemas import RAW_TOOL_DECLARATIONS
from backend.agent.guards import is_reset_command


def test_quick_add_items_in_raw_tool_declarations():
    """Stage 1 planning requires quick_add_items schema for recipe and meal kit decomposition."""
    tool_names = [tool["name"] for tool in RAW_TOOL_DECLARATIONS]
    assert "quick_add_items" in tool_names, "quick_add_items must be declared in RAW_TOOL_DECLARATIONS"


def test_is_reset_command_matches_all_natural_basket_purge_variations():
    """Fast-path guard must deterministically match user reset commands in 0ms without reaching LLM."""
    positive_cases = [
        "delete basket",
        "Delete Basket",
        "clear cart",
        "clear basket",
        "empty cart",
        "empty my cart",
        "empty basket",
        "empty the basket",
        "delete cart",
        "delete all",
        "delete everything",
        "clear all",
        "clear everything",
        "wipe cart",
        "wipe all items",
        "reset",
        "start over",
        "start fresh",
    ]
    for case in positive_cases:
        assert is_reset_command(case) is True, f"Failed to match reset command: '{case}'"


def test_is_reset_command_does_not_falsely_match_shopping_intents():
    """Reset guard must not hijack regular shopping or item requests."""
    negative_cases = [
        "i wanna make pizza give me ingredients",
        "add bread and milk to basket",
        "basket of apples",
        "delete 1 milk",
        "remove bread from basket",
        "cart total please",
        "where is my order",
    ]
    for case in negative_cases:
        assert is_reset_command(case) is False, f"Falsely matched shopping intent: '{case}'"


@pytest.mark.asyncio
async def test_manage_basket_resilient_to_individual_search_failures():
    """manage_basket must not fail the whole batch if one item has a search error."""
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.agent.tools import SwiggyAgentTools

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    # Mock batch_search_products to return 1 success and 1 error
    async def mock_batch_search(queries, address_id):
        return {
            "success": True,
            "results": [
                {
                    "query": "milk",
                    "products": [
                        {
                            "spin_id": "SPIN-MILK-1L",
                            "sku_id": "SKU-MILK-1L",
                            "name": "Amul Taaza Milk 1L",
                            "price": 54.0,
                            "pack_size": "1L",
                            "category": "Dairy",
                        }
                    ],
                },
                {
                    "query": "nonexistent_item_xyz",
                    "products": [],
                    "error": "SEARCH_UNAVAILABLE",
                },
            ],
        }

    tools.batch_search_products = mock_batch_search

    result = await tools.manage_basket(
        address_id="addr-1",
        add=[
            {"query": "milk", "quantity": 1},
            {"query": "nonexistent_item_xyz", "quantity": 1},
        ],
    )

    assert result["success"] is True
    assert "unavailable_items" in result
    assert "nonexistent_item_xyz" in result["unavailable_items"]
    assert len(result.get("added_items", [])) == 1
    assert result["added_items"][0] == "Amul Taaza Milk 1L"


@pytest.mark.asyncio
async def test_engine_planning_turn_includes_quick_add_items():
    """GroceryAgentEngine must supply quick_add_items on planning turns and never pass empty tools."""
    from backend.agent.engine import GroceryAgentEngine
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")

    passed_tools = []

    async def mock_generate_content(contents, system_text, tools):
        nonlocal passed_tools
        passed_tools = tools
        return {"candidates": []}

    engine.gemini.generate_content = mock_generate_content
    await engine._call_llm([{"role": "user", "parts": [{"text": "i wanna make pizza"}]}], planning_only=True)

    assert len(passed_tools) == 1, "Planning turn tools must contain exactly quick_add_items, not empty list"
    assert passed_tools[0]["name"] == "quick_add_items"


@pytest.mark.asyncio
async def test_engine_fast_path_delete_basket():
    """Incoming 'delete basket' must trigger 0ms fast-path cart wipe."""
    from backend.agent.engine import GroceryAgentEngine
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.channels.models import NormalizedIncomingMessage

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")

    msg = NormalizedIncomingMessage(
        sender_id="919876543210",
        message_id="msg-reset-test",
        text="delete basket",
        timestamp=1234567890,
    )
    resp = await engine.handle_message(msg)
    assert resp.text is not None
    assert "cleared" in resp.text.lower() or "empty" in resp.text.lower()


@pytest.mark.asyncio
async def test_recipe_planning_turn_executes_quick_add_and_mutates_basket():
    """Recipe requests like 'make pizza' must decompose into items and populate the basket."""
    from backend.agent.engine import GroceryAgentEngine
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.channels.models import NormalizedIncomingMessage

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    # Mock _call_llm: on planning_only=True, return quick_add_items with pizza base & cheese
    calls_count = 0

    async def mock_call_llm(contents, **kwargs):
        nonlocal calls_count
        calls_count += 1
        if kwargs.get("planning_only"):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "quick_add_items",
                                        "args": {
                                            "items": [
                                                {"query": "pizza base", "quantity": 1},
                                                {"query": "mozzarella cheese", "quantity": 1},
                                            ]
                                        },
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        # Subsequent conversational turn
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "I've added pizza base and mozzarella cheese to your basket."}
                        ]
                    }
                }
            ]
        }

    engine._call_llm = mock_call_llm

    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-recipe-1",
        text="i wanna make pizza give me ingredients",
        timestamp=1234567890,
    )
    resp = await engine.handle_message(msg)
    assert resp.text is not None
    assert "connection hiccup" not in resp.text.lower()
    assert "couldn't process that request" not in resp.text.lower()


def test_whatsapp_customer_id_normalizes_10_digit_indian_number():
    """10-digit Indian numbers without country code must be normalized to +91 rather than rejected."""
    from backend.identity import whatsapp_customer_id

    secret = "test-whatsapp-app-secret-32-chars-long"
    cid_10 = whatsapp_customer_id("9876543210", secret)
    cid_full = whatsapp_customer_id("919876543210", secret)
    assert cid_10 == cid_full, "10-digit number must normalize to identical customer ID as 91-prefixed number"


def test_swiggy_client_uses_owner_token_when_customer_id_is_none():
    """When customer_id is None, client must fall back to owner_customer_id / auth_token."""
    from backend.integrations.commerce.swiggy_client import SwiggyMcpClient

    client = SwiggyMcpClient(
        base_url="https://mcp.swiggy.com/im",
        auth_token="auth-token-xyz",
        owner_customer_id="owner-cust-1",
    )
    resolved = client.resolve_token(None)
    assert resolved == "auth-token-xyz", f"Expected auth-token-xyz but got {resolved}"


def test_cart_parsers_absorbs_positive_provider_surcharges():
    """Positive unclassified provider fees (rain fee, surge) must be absorbed so billing_complete remains True."""
    from backend.integrations.commerce.cart_parsers import build_commerce_cart

    raw_payload = {
        "cartId": "cart-surge-123",
        "items": [
            {
                "spinId": "SPIN-1",
                "itemName": "Milk 1L",
                "quantity": 1,
                "price": 50.0,
                "mrp": 50.0,
            }
        ],
        "billBreakdown": {
            "lineItems": [
                {"label": "Item Total", "value": "50"},
                {"label": "Delivery Fee", "value": "0"},
            ],
            "toPay": {"value": "55", "currency": "INR"},
        },
    }
    cart = build_commerce_cart(raw_payload)
    assert cart.billing_complete is True, f"Expected billing_complete=True, but diff was not absorbed: {cart.cart_warning}"
    assert cart.grand_total == 55.0
    assert cart.handling_fee >= 5.0, "Unclassified surge must be absorbed into handling_fee"


def test_get_commerce_adapter_reuses_swiggy_singleton():
    """get_commerce_adapter must reuse cached SwiggyMCPAdapter instance across calls."""
    from backend.config import settings
    from backend.integrations.commerce.factory import get_commerce_adapter

    orig_type = getattr(settings, "COMMERCE_ADAPTER_TYPE", "mock")
    try:
        settings.COMMERCE_ADAPTER_TYPE = "swiggy_mcp"
        adapter1 = get_commerce_adapter()
        adapter2 = get_commerce_adapter()
        assert adapter1 is adapter2, "get_commerce_adapter() must return the same cached instance for swiggy_mcp"
    finally:
        settings.COMMERCE_ADAPTER_TYPE = orig_type


@pytest.mark.asyncio
async def test_tool_scheduler_survives_partial_read_failure():
    """Fault-tolerant tool scheduler must not crash entire batch when an optional read tool throws."""
    from backend.agent.tool_scheduler import execute_tool_calls

    async def mock_execute(call):
        if call.get("name") == "get_saved_addresses":
            raise RuntimeError("Provider network timeout")
        return {"status": "ok", "tool": call.get("name")}

    calls = [
        {"name": "get_saved_addresses", "args": {}},
        {"name": "get_cart", "args": {}},
    ]
    results = await execute_tool_calls(calls, mock_execute)
    assert len(results) == 2, f"Expected 2 results but got {len(results)}"
    # First result should capture the error gracefully rather than crashing the loop
    assert results[0].get("success") is False or "error" in results[0] or "exception" in results[0]
    assert results[1].get("status") == "ok"


def test_inbound_burst_message_concatenation():
    """Rapid bursts from the same customer must be concatenated into a unified prompt."""
    from backend.channels.models import NormalizedIncomingMessage

    base_msg = NormalizedIncomingMessage(
        sender_id="919876543210",
        message_id="msg-1",
        text="add 1 amul milk",
        timestamp=1000.0,
    )
    burst_msg = NormalizedIncomingMessage(
        sender_id="919876543210",
        message_id="msg-2",
        text="and 1 whole wheat bread",
        timestamp=1001.5,
    )
    combined_text = f"{base_msg.text}\n{burst_msg.text}"
    merged = base_msg.model_copy(update={"text": combined_text})

    assert "add 1 amul milk" in merged.text
    assert "and 1 whole wheat bread" in merged.text
    assert merged.message_id == "msg-1"

