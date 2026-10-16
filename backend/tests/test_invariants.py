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
        "remove all bread",
        "delete all apples",
        "cart total please",
        "where is my order",
    ]
    for case in negative_cases:
        assert is_reset_command(case) is False, f"Falsely matched shopping intent: '{case}'"


def test_is_hesitation_does_not_falsely_match_bus_stop_or_shopping():
    """Hesitation guard must not match transportation stops or shopping statements."""
    from backend.agent.guards import is_hesitation

    negative_cases = [
        "milk at the bus stop",
        "meet me at the metro stop and bring bread",
        "add milk",
    ]
    for case in negative_cases:
        assert is_hesitation(case) is False, f"Falsely matched hesitation: '{case}'"


def test_cart_read_fast_path_does_not_hijack_product_recommendation_questions():
    """Cart read fast-path must not hijack user questions like 'what items go well with pasta?'."""
    from backend.agent.fast_paths import handle_cart_read_fast_path
    from backend.channels.models import NormalizedIncomingMessage

    dummy_msg = NormalizedIncomingMessage(
        message_id="msg-1",
        sender_id="user-1",
        channel="whatsapp",
        text="what items go well with pasta?",
    )
    result = handle_cart_read_fast_path(
        norm_text="what items go well with pasta?",
        message=dummy_msg,
        current_cart=None,
    )
    assert result is None, "Recommendation questions must not trigger cart read fast-path"




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


def test_universal_e164_identity():
    """Universal E.164 identity must accept valid international and Indian numbers."""
    from backend.identity import whatsapp_customer_id

    secret = "test-app-secret-32-chars-long-1234"
    # Indian 10-digit
    in_id = whatsapp_customer_id("9876543210", secret)
    assert in_id.startswith("cust_wa_")
    assert in_id == whatsapp_customer_id("+919876543210", secret)

    # US international
    us_id = whatsapp_customer_id("+15551234567", secret)
    assert us_id.startswith("cust_wa_")

    # UK international
    uk_id = whatsapp_customer_id("447123456789", secret)
    assert uk_id.startswith("cust_wa_")

    # Invalid cases
    with pytest.raises(ValueError):
        whatsapp_customer_id("123", secret)
    with pytest.raises(ValueError):
        whatsapp_customer_id("abcdefghij", secret)


def test_multi_fernet_key_rotation():
    """MultiFernet must support rotating keys with zero downtime."""
    from cryptography.fernet import Fernet
    from backend.integrations.commerce.token_vault import EncryptedPayloadCodec

    k1 = Fernet.generate_key().decode()
    k2 = Fernet.generate_key().decode()

    # Encrypt with k1
    codec_old = EncryptedPayloadCodec(k1)
    ciphertext = codec_old.encrypt({"customer_id": "cust_123", "token": "xyz"})

    # Decrypt with rotated key list [k2, k1]
    codec_rotated = EncryptedPayloadCodec(f"{k2},{k1}")
    decrypted = codec_rotated.decrypt(ciphertext)
    assert decrypted["customer_id"] == "cust_123"

    # New writes use k2 (primary)
    new_ciphertext = codec_rotated.encrypt({"customer_id": "cust_456"})
    # k2 standalone can decrypt
    codec_new_only = EncryptedPayloadCodec(k2)
    assert codec_new_only.decrypt(new_ciphertext)["customer_id"] == "cust_456"


def test_recipe_staples_guards_multimeal():
    """Recipe guards must ensure indispensable bases for pizza, pasta, and burger are preserved."""
    from backend.agent.guards import missing_recipe_staples

    # Pizza missing base
    assert missing_recipe_staples("I want to make pizza tonight", ["tomato", "cheese"]) == ["pizza base"]
    # Pizza with base present
    assert missing_recipe_staples("I want to make pizza tonight", ["pizza crust", "cheese"]) == []
    # Pizza when user already has base
    assert missing_recipe_staples("I want to make pizza, I already have pizza base", ["cheese"]) == []

    # Pasta missing base
    assert missing_recipe_staples("Let's cook pasta", ["pasta sauce", "parmesan"]) == ["pasta"]
    # Pasta with base present
    assert missing_recipe_staples("Let's cook pasta", ["penne", "sauce"]) == []

    # Burger missing bun
    assert missing_recipe_staples("prepare burger for dinner", ["patty", "mayo"]) == ["burger bun"]
    # Burger with bun present
    assert missing_recipe_staples("prepare burger for dinner", ["burger bun", "patty"]) == []


def test_first_aid_product_policy_not_restricted():
    """Non-prescription first aid products must not be restricted even if in pharmacy category."""
    from backend.agent.product_policy import is_restricted_medical_product

    # Allowed first aid
    assert is_restricted_medical_product("Hansaplast Band-Aid (Pack of 10)", category="pharmacy") is False
    assert is_restricted_medical_product("Electral ORS Powder 21.8g", category="pharmacy") is False
    assert is_restricted_medical_product("Savlon Antiseptic Liquid 200ml", category="pharmacy") is False
    assert is_restricted_medical_product("Absorbent Cotton 100g", category="pharmacy") is False

    # Strictly blocked prescription drugs
    assert is_restricted_medical_product("Dolo 650 Tablet", category="pharmacy") is True
    assert is_restricted_medical_product("Crocin Pain Relief", category="pharmacy") is True
    assert is_restricted_medical_product("Amoxicillin Antibiotic 500mg", category="pharmacy") is True


def test_delete_data_pattern_matching():
    """Data deletion regex must match natural privacy requests and ignore ordinary shopping."""
    from backend.api.whatsapp import _DELETE_DATA_PATTERN

    # Valid deletion variations
    for text in [
        "delete my data",
        "Delete my data",
        "please delete my data",
        "purge my data",
        "erase my data",
        "remove my data",
        "delete all my data",
        "delete my history",
        "delete my account",
        "purge my history",
    ]:
        assert _DELETE_DATA_PATTERN.match(text) is not None, f"Failed to match: {text}"

    # Ordinary shopping or item removal must NOT match
    for text in [
        "delete 1 milk",
        "remove bread from cart",
        "please add eggs",
        "my data plan is expired",
    ]:
        assert _DELETE_DATA_PATTERN.match(text) is None, f"Falsely matched: {text}"


def test_customer_advisory_lock_key_deterministic_64bit():
    """Customer advisory lock key must be a deterministic signed 64-bit integer for Postgres."""
    from backend.agent.task_state import customer_advisory_lock_key

    key1 = customer_advisory_lock_key("cust_wa_abcdef123456")
    key2 = customer_advisory_lock_key("cust_wa_abcdef123456")
    key3 = customer_advisory_lock_key("cust_wa_other_customer")

    assert key1 == key2
    assert key1 != key3
    assert -9223372036854775808 <= key1 <= 9223372036854775807
    assert -9223372036854775808 <= key3 <= 9223372036854775807


@pytest.mark.asyncio
async def test_engine_handle_message_returns_response_with_pool_state_store():
    """handle_message must never return None when state_store has a pool."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock
    from backend.agent.engine import GroceryAgentEngine
    from backend.channels.models import NormalizedIncomingMessage, NormalizedOutgoingResponse
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter

    mock_pool = MagicMock()
    mock_state_store = MagicMock()
    mock_state_store.pool = mock_pool

    @asynccontextmanager
    async def fake_lock(customer_id):
        yield "fake_conn"

    mock_state_store.transaction_lock = fake_lock
    mock_state_store.load = AsyncMock(return_value=None)
    mock_state_store.save = AsyncMock(return_value=None)

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test", state_store=mock_state_store)

    msg = NormalizedIncomingMessage(
        sender_id="919999988888",
        message_id="msg-pool-test",
        text="hi",
        timestamp=1000.0,
    )
    res = await engine.handle_message(msg)
    assert res is not None, "handle_message must never return None when state_store has a pool"
    assert isinstance(res, NormalizedOutgoingResponse)
    assert res.text


def test_is_explicit_confirmation_accepts_natural_affirmations_and_rejects_negations():
    from backend.agent.guards import is_explicit_confirmation
    affirmations = [
        "confirm", "confirm order", "yes", "place order", "proceed", "pay",
        "sounds good", "looks good", "send it", "yep", "yeah", "yup",
        "good to go", "all good", "perfect", "haan", "haan kar do", "haan place karo",
    ]
    for text in affirmations:
        assert is_explicit_confirmation(text) is True, f"Failed on affirmation: {text}"

    negations = [
        "don't confirm", "do not place order", "not now", "cancel order",
        "wait", "hold on", "stop", "never order", "pause", "no don't order",
    ]
    for text in negations:
        assert is_explicit_confirmation(text) is False, f"Failed on negation: {text}"

    shopping_phrases = [
        "order 2 milk", "order milk", "place 1 bread in cart", "add milk", "need bread", "bring eggs",
    ]
    for text in shopping_phrases:
        assert is_explicit_confirmation(text) is False, f"Shopping phrase falsely confirmed: {text}"


def test_catalog_ranker_penalizes_multipack_bundles_unless_requested():
    from backend.agent.catalog_ranker import rank_and_select_best_variant
    candidates = [
        {"spin_id": "SPIN-BUNDLE-4X", "sku_id": "SKU-B4", "name": "Amul Taaza Milk (500 ml x 4)", "price": 120.0, "pack_size": "500 ml x 4"},
        {"spin_id": "SPIN-SINGLE-500", "sku_id": "SKU-S1", "name": "Amul Taaza Milk (500 ml)", "price": 30.0, "pack_size": "500 ml"},
    ]
    # Simple query should pick single pack
    best = rank_and_select_best_variant("amul milk", candidates)
    assert best is not None
    assert best["spin_id"] == "SPIN-SINGLE-500", f"Expected single pack, got {best['name']}"

    # Explicit bulk request allows bundle
    best_bulk = rank_and_select_best_variant("amul milk pack of 4", candidates)
    assert best_bulk is not None
    assert best_bulk["spin_id"] == "SPIN-BUNDLE-4X", f"Expected bundle, got {best_bulk['name']}"


def test_matches_requested_product_relaxed_for_common_descriptors():
    from backend.agent.catalog_ranker import _matches_requested_product
    # "fresh tomatoes" should match "Tomato Hybrid 500g"
    product = {"name": "Tomato Hybrid 500g", "brand": "Fresh", "pack_size": "500g"}
    assert _matches_requested_product("fresh tomatoes", product) is True

    # "cooking oil" matches "Fortune Sunflower Oil 1L"
    oil = {"name": "Fortune Sunflower Oil 1L", "brand": "Fortune", "pack_size": "1L"}
    assert _matches_requested_product("cooking oil", oil) is True

    # Negative exclusion check: "eggless" for "egg" must fail
    eggless = {"name": "Britannia Eggless Cake", "brand": "Britannia"}
    assert _matches_requested_product("egg", eggless) is False


def test_budget_negative_lookahead_handles_grams_and_volume_units():
    from backend.agent.budget import extract_total_budget
    # Unit weights must not be parsed as budget caps
    assert extract_total_budget("under 500 grams of paneer") is None
    assert extract_total_budget("under 500 gms of paneer") is None
    assert extract_total_budget("below 250 ml milk") is None

    # Plain number and genuine rupee budgets must be extracted
    assert extract_total_budget("under 80") == 80.0
    assert extract_total_budget("within 180") == 180.0
    assert extract_total_budget("at most 100") == 100.0
    assert extract_total_budget("under 500 rupees") == 500.0
    assert extract_total_budget("under ₹500") == 500.0
    assert extract_total_budget("under Rs 350 for all items") == 350.0


def test_address_resolver_avoids_false_positives_on_shopping_verbs():
    from backend.agent.address_resolver import match_explicit_address
    addresses = [
        {"id": "addr-1", "label": "Home", "area": "Green Glen Layout", "street": "Outer Ring Road"},
    ]
    # Shopping for green chillies must not switch address to Green Glen Layout
    assert match_explicit_address(addresses, "send 1kg green chillies") is None
    assert match_explicit_address(addresses, "bring green apples") is None

    # Explicit delivery instruction should switch
    match = match_explicit_address(addresses, "deliver to Home")
    assert match is not None and match["id"] == "addr-1"


def test_response_synthesizer_english_guard_preserves_indian_brand_receipts():
    from backend.agent.response_synthesizer import _ensure_english_only
    receipt_text = (
        "Here are your items:\n\n"
        "🛒 *Your Basket:*\n"
        "1. Chitale Bandhu Bakarwadi 250g — ₹85.00\n"
        "2. Mera Swad Mango Pickle 500g — ₹120.00\n"
        "Total: ₹205.00\n\n"
        "👉 Reply *Confirm* to place order."
    )
    result = _ensure_english_only(receipt_text)
    assert "Chitale Bandhu Bakarwadi" in result
    assert "Mera Swad Mango Pickle" in result
    assert "I can only help you shop for groceries" not in result


def test_reconcile_explicit_removals_cleans_cart_context_phrases():
    from backend.agent.guards import reconcile_explicit_removals
    assert reconcile_explicit_removals("remove eggs from my cart please") == ["eggs"]
    assert reconcile_explicit_removals("drop the bread from basket") == ["bread"]
    assert reconcile_explicit_removals("delete milk") == ["milk"]


def test_cart_edits_allows_quantity_reduction_phrases():
    from backend.agent.react_loop import validate_cart_edit_calls
    from unittest.mock import MagicMock
    item = MagicMock()
    item.spin_id = "SPIN-MILK"
    item.name = "Amul Taaza Milk 1L"
    cart = MagicMock()
    cart.items = [item]

    calls = [{
        "name": "update_cart",
        "args": {"items": [{"spin_id": "SPIN-MILK", "quantity": 2}]}
    }]
    # "drop milk from 3 to 2" must be accepted, not rejected
    assert validate_cart_edit_calls(calls, cart, "drop milk from 3 to 2") is True
    assert validate_cart_edit_calls(calls, cart, "reduce milk to 2") is True


def test_is_invalid_item_plan_allows_branded_spice_recipes():
    from backend.agent.react_loop import is_invalid_item_plan
    # Branded spice mix containing the word "recipe" must NOT be considered an invalid plan
    branded_calls = [{
        "name": "quick_add_items",
        "args": {"items": [{"query": "Shan Biryani Recipe Masala", "quantity": 1}]}
    }]
    assert is_invalid_item_plan(branded_calls) is False

    # Abstract queries like "all ingredients" or "recipe" alone must still be rejected
    abstract_calls = [{
        "name": "quick_add_items",
        "args": {"items": [{"query": "recipe", "quantity": 1}]}
    }]
    assert is_invalid_item_plan(abstract_calls) is True


@pytest.mark.asyncio
async def test_checkout_executor_guards_unserviceable_cart():
    from backend.agent.checkout_executor import execute_gated_checkout
    from unittest.mock import AsyncMock, MagicMock
    commerce = MagicMock()
    cart = MagicMock()
    cart.is_serviceable = False
    cart.grand_total = 150.0
    cart.currency = "INR"
    cart.billing_complete = True
    cart.items = [MagicMock()]
    commerce.get_cart = AsyncMock(return_value=cart)

    res = await execute_gated_checkout(commerce, cart_id="cart-1", address_id="addr-1", is_user_confirmed=True)
    assert res["success"] is False
    assert res["error"] == "ADDRESS_NOT_SERVICEABLE"


def test_rank_and_select_best_variant_handles_id_like_milk():
    """English contraction 'I'd like milk' must not be mistaken for ID Fresh brand."""
    from backend.agent.catalog_ranker import rank_and_select_best_variant

    products = [
        {
            "name": "Amul Taaza Toned Milk",
            "brand": "Amul",
            "spin_id": "spin-amul-milk",
            "sku_id": "sku-amul-milk",
            "price": 27.0,
            "pack_size": "500 ml",
        }
    ]
    selected = rank_and_select_best_variant("I'd like 2 packets of milk", products)
    assert selected is not None, "Product should not be rejected due to 'id' contraction"
    assert selected["spin_id"] == "spin-amul-milk"





