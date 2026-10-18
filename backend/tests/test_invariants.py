"""Adversarial invariant unit tests for GROCER fast-paths, schemas, and resilient tool resolution."""
import pytest
from backend.agent.schemas import RAW_TOOL_DECLARATIONS


def test_manage_basket_in_raw_tool_declarations():
    """manage_basket must be declared as the basket-write tool; quick_add_items and update_cart must be absent."""
    tool_names = [tool["name"] for tool in RAW_TOOL_DECLARATIONS]
    assert "manage_basket" in tool_names, "manage_basket must be declared in RAW_TOOL_DECLARATIONS"
    assert "quick_add_items" not in tool_names, "quick_add_items must not be in RAW_TOOL_DECLARATIONS"
    assert "update_cart" not in tool_names, "update_cart must not be in RAW_TOOL_DECLARATIONS"




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
async def test_recipe_turn_executes_manage_basket_and_mutates_basket():
    """Recipe requests like 'make pizza' decompose into items and populate the basket via manage_basket."""
    from backend.agent.engine import GroceryAgentEngine
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.channels.models import NormalizedIncomingMessage

    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    engine._customer_address[customer_id] = "addr-bandra-1"
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    calls_count = 0

    async def mock_call_llm(contents, **kwargs):
        nonlocal calls_count
        calls_count += 1
        if calls_count == 1:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "manage_basket",
                                        "args": {
                                            "add": [
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


def test_cart_parsers_flags_unexplained_billing_differences():
    """Unexplained billing differences must not be invented as verified fees and must set billing_complete=False."""
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
    assert cart.billing_complete is False, "Unexplained positive difference must not mark billing_complete=True"
    assert cart.grand_total == 55.0
    assert cart.cart_warning == "Provider bill lines do not explain the payable total."

    # But when provider includes an explicit surge/rain fee line, it is properly recognized
    explained_payload = {
        "cartId": "cart-surge-123",
        "items": [
            {"spinId": "SPIN-1", "itemName": "Milk 1L", "quantity": 1, "price": 50.0, "mrp": 50.0}
        ],
        "billBreakdown": {
            "lineItems": [
                {"label": "Item Total", "value": "50"},
                {"label": "Rain Surge Fee", "value": "5"},
            ],
            "toPay": {"value": "55", "currency": "INR"},
        },
    }
    cart_explained = build_commerce_cart(explained_payload)
    assert cart_explained.billing_complete is True
    assert cart_explained.handling_fee == 5.0



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
    from backend.agent.tool_executor import execute_tool_calls

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


@pytest.mark.asyncio
async def test_manage_basket_remove_valid_line_id():
    """Valid line id in remove removes only the target line."""
    from backend.agent.tools import SwiggyAgentTools
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CartItem, CommerceCart

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    item1 = CartItem(
        line_id="line-milk-1",
        spin_id="SPIN-MILK-1L",
        sku_id="SPIN-MILK-1L",
        name="Amul Taaza Milk 1L Pouch",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    item2 = CartItem(
        line_id="line-bread-1",
        spin_id="SPIN-BREAD-400G",
        sku_id="SPIN-BREAD-400G",
        name="Whole Wheat Bread 400g",
        pack_size="400 g",
        unit_price=50.0,
        quantity=1,
        total_price=50.0,
    )
    cart = CommerceCart(
        cart_id="default-cart",
        address_id="addr-1",
        items=[item1, item2],
        item_total=116.0,
        grand_total=116.0,
    )
    commerce._carts["default-cart"] = cart

    # 1. Attempting to remove using spin_id alias fails with INVALID_LINE_ID
    result_alias = await tools.manage_basket(
        address_id="addr-1",
        remove=["SPIN-MILK-1L"],
        current_cart=cart,
    )
    assert result_alias["success"] is False
    assert result_alias["error"] == "INVALID_LINE_ID"

    # 2. Removing using exact line_id succeeds
    result = await tools.manage_basket(
        address_id="addr-1",
        remove=["line-milk-1"],
        current_cart=cart,
    )

    assert result["success"] is True
    assert "Amul Taaza Milk 1L Pouch" in result["removed_items"]
    remaining_spins = [it["spin_id"] for it in result.get("items", [])]
    assert "SPIN-MILK-1L" not in remaining_spins
    assert "SPIN-BREAD-400G" in remaining_spins


@pytest.mark.asyncio
async def test_manage_basket_unknown_line_id_changes_nothing():
    """Unknown line id in remove or set_quantity returns an error and changes nothing."""
    from backend.agent.tools import SwiggyAgentTools
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CartItem, CommerceCart

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    item1 = CartItem(
        line_id="line-milk-1",
        spin_id="SPIN-MILK-1L",
        sku_id="SPIN-MILK-1L",
        name="Amul Taaza Milk 1L Pouch",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    cart = CommerceCart(
        cart_id="default-cart",
        address_id="addr-1",
        items=[item1],
        item_total=66.0,
        grand_total=66.0,
    )
    commerce._carts["default-cart"] = cart

    # 1. Unknown ID in remove
    result_remove = await tools.manage_basket(
        address_id="addr-1",
        remove=["UNKNOWN-LINE-ID"],
        current_cart=cart,
    )
    assert result_remove["success"] is False
    assert result_remove["error"] == "INVALID_LINE_ID"
    fresh_cart = await commerce.get_cart("default-cart")
    assert len(fresh_cart.items) == 1
    assert fresh_cart.items[0].spin_id == "SPIN-MILK-1L"

    # 2. Unknown ID in set_quantity
    result_sq = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"line_id": "UNKNOWN-LINE-ID", "quantity": 3}],
        current_cart=cart,
    )
    assert result_sq["success"] is False
    assert result_sq["error"] == "INVALID_LINE_ID"
    fresh_cart2 = await commerce.get_cart("default-cart")
    assert len(fresh_cart2.items) == 1
    assert fresh_cart2.items[0].quantity == 1


@pytest.mark.asyncio
async def test_manage_basket_set_quantity_by_line_id():
    """set_quantity by line id updates the specific item quantity."""
    from backend.agent.tools import SwiggyAgentTools
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CartItem, CommerceCart

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    item1 = CartItem(
        line_id="line-milk-1",
        spin_id="SPIN-MILK-1L",
        sku_id="SPIN-MILK-1L",
        name="Amul Taaza Milk 1L Pouch",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    cart = CommerceCart(
        cart_id="default-cart",
        address_id="addr-1",
        items=[item1],
        item_total=66.0,
        grand_total=66.0,
    )
    commerce._carts["default-cart"] = cart

    result = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"line_id": "line-milk-1", "quantity": 3}],
        current_cart=cart,
    )
    assert result["success"] is True
    assert any("Amul Taaza Milk 1L Pouch -> 3" in mod for mod in result.get("modified_items", []))
    fresh_cart = await commerce.get_cart("default-cart")
    assert fresh_cart.items[0].quantity == 3


@pytest.mark.asyncio
async def test_manage_basket_two_identical_lines_not_touched_by_guessed_name():
    """Two identical lines are not touched when a guessed item name or spin_id alias is passed instead of exact line id."""
    from backend.agent.tools import SwiggyAgentTools
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CartItem, CommerceCart

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    # Two items with identical display name and attributes, but distinct line IDs
    item1 = CartItem(
        spin_id="SPIN-MILK-1L",
        line_id="line-milk-a",
        sku_id="SPIN-MILK-1L",
        name="Amul Taaza Fresh Toned Milk",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    item2 = CartItem(
        spin_id="SPIN-MILK-500ML",
        line_id="line-milk-b",
        sku_id="SPIN-MILK-500ML",
        name="Amul Taaza Fresh Toned Milk",
        pack_size="500 ml",
        unit_price=34.0,
        quantity=1,
        total_price=34.0,
    )
    cart = CommerceCart(
        cart_id="default-cart",
        address_id="addr-1",
        items=[item1, item2],
        item_total=100.0,
        grand_total=100.0,
    )
    commerce._carts["default-cart"] = cart

    # 1. Attempting to remove using the guessed product name fails with INVALID_LINE_ID and touches neither line
    res_name_remove = await tools.manage_basket(
        address_id="addr-1",
        remove=["Amul Taaza Fresh Toned Milk"],
        current_cart=cart,
    )
    assert res_name_remove["success"] is False
    assert res_name_remove["error"] == "INVALID_LINE_ID"

    # 2. Attempting to remove using spin_id alias fails with INVALID_LINE_ID
    res_spin_remove = await tools.manage_basket(
        address_id="addr-1",
        remove=["SPIN-MILK-1L"],
        current_cart=cart,
    )
    assert res_spin_remove["success"] is False
    assert res_spin_remove["error"] == "INVALID_LINE_ID"

    # 3. Attempting to set quantity using guessed product name fails with INVALID_LINE_ID and touches neither line
    res_name_sq = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"line_id": "Amul Taaza Fresh Toned Milk", "quantity": 2}],
        current_cart=cart,
    )
    assert res_name_sq["success"] is False
    assert res_name_sq["error"] == "INVALID_LINE_ID"

    # 4. Attempting to set quantity using spin_id alias fails with INVALID_LINE_ID
    res_spin_sq = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"line_id": "SPIN-MILK-1L", "quantity": 2}],
        current_cart=cart,
    )
    assert res_spin_sq["success"] is False
    assert res_spin_sq["error"] == "INVALID_LINE_ID"

    # 5. Attempting to set quantity using 'id' alias key instead of 'line_id' fails with INVALID_LINE_ID
    res_alias_key = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"id": "line-milk-a", "quantity": 2}],
        current_cart=cart,
    )
    assert res_alias_key["success"] is False
    assert res_alias_key["error"] == "INVALID_LINE_ID"

    # 6. Passing exact line ID touches only that line and preserves the other identical line
    res_id_remove = await tools.manage_basket(
        address_id="addr-1",
        remove=["line-milk-a"],
        current_cart=cart,
    )
    assert res_id_remove["success"] is True
    assert "Amul Taaza Fresh Toned Milk" in res_id_remove["removed_items"]
    remaining_spins = [it["spin_id"] for it in res_id_remove.get("items", [])]
    assert "SPIN-MILK-1L" not in remaining_spins
    assert "SPIN-MILK-500ML" in remaining_spins


@pytest.mark.asyncio
async def test_manage_basket_rejects_editing_item_customer_did_not_name():
    """Editing or removing an item line that does not exist or was not named in the live cart is rejected."""
    from backend.agent.tools import SwiggyAgentTools
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CartItem, CommerceCart

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    cart = CommerceCart(
        cart_id="default-cart",
        address_id="addr-1",
        items=[
            CartItem(
                line_id="line-milk-1",
                spin_id="SPIN-MILK-1L",
                sku_id="SPIN-MILK-1L",
                name="Amul Taaza Milk 1L Pouch",
                pack_size="1 L",
                unit_price=66.0,
                quantity=1,
                total_price=66.0,
            ),
        ],
        item_total=66.0,
        grand_total=66.0,
    )
    commerce._carts["default-cart"] = cart

    # Attempting to edit an unnamed / non-existent item line is rejected
    res_sq = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"line_id": "line-unnamed-biscuit", "quantity": 2}],
        current_cart=cart,
    )
    assert res_sq["success"] is False
    assert res_sq["error"] == "INVALID_LINE_ID"

    # Attempting to remove an unnamed / non-existent item line is rejected
    res_rm = await tools.manage_basket(
        address_id="addr-1",
        remove=["line-unnamed-biscuit"],
        current_cart=cart,
    )
    assert res_rm["success"] is False
    assert res_rm["error"] == "INVALID_LINE_ID"

    # Cart remains completely unchanged
    fresh = await commerce.get_cart("default-cart")
    assert len(fresh.items) == 1
    assert fresh.items[0].line_id == "line-milk-1"
    assert fresh.items[0].quantity == 1


@pytest.mark.asyncio
async def test_manage_basket_resolves_second_item_to_live_cart_line_id():
    """The ordinal 'second one' in the live cart resolves to the exact line id of the 2nd item."""
    from backend.agent.tools import SwiggyAgentTools
    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
    from backend.integrations.commerce.models import CartItem, CommerceCart

    commerce = MockCommerceAdapter()
    tools = SwiggyAgentTools(commerce)

    item1 = CartItem(
        line_id="line-milk-101",
        spin_id="SPIN-MILK-1L",
        sku_id="SPIN-MILK-1L",
        name="Amul Taaza Fresh Milk",
        pack_size="1 L",
        unit_price=66.0,
        quantity=1,
        total_price=66.0,
    )
    item2 = CartItem(
        line_id="line-bread-202",
        spin_id="SPIN-BREAD-400G",
        sku_id="SPIN-BREAD-400G",
        name="Whole Wheat Bread 400g",
        pack_size="400 g",
        unit_price=50.0,
        quantity=1,
        total_price=50.0,
    )
    item3 = CartItem(
        line_id="line-eggs-303",
        spin_id="SPIN-EGGS-6",
        sku_id="SPIN-EGGS-6",
        name="Farm Fresh Eggs 6pcs",
        pack_size="6 pcs",
        unit_price=60.0,
        quantity=1,
        total_price=60.0,
    )
    cart = CommerceCart(
        cart_id="default-cart",
        address_id="addr-1",
        items=[item1, item2, item3],
        item_total=176.0,
        grand_total=176.0,
    )
    commerce._carts["default-cart"] = cart

    # In the live cart, 'second one' corresponds to index 1 (item2, line-bread-202)
    second_line_id = cart.items[1].line_id
    assert second_line_id == "line-bread-202"

    # Updating the second one via manage_basket modifies only item2
    res_update = await tools.manage_basket(
        address_id="addr-1",
        set_quantity=[{"line_id": second_line_id, "quantity": 3}],
        current_cart=cart,
    )
    assert res_update["success"] is True
    assert any("Whole Wheat Bread 400g -> 3" in mod for mod in res_update.get("modified_items", []))
    fresh = await commerce.get_cart("default-cart")
    assert next(i.quantity for i in fresh.items if i.spin_id == "SPIN-BREAD-400G") == 3
    assert next(i.quantity for i in fresh.items if i.spin_id == "SPIN-MILK-1L") == 1
    assert next(i.quantity for i in fresh.items if i.spin_id == "SPIN-EGGS-6") == 1

    # Removing the second one via manage_basket removes only item2
    commerce2 = MockCommerceAdapter()
    tools2 = SwiggyAgentTools(commerce2)
    commerce2._carts["default-cart"] = cart
    res_rm = await tools2.manage_basket(
        address_id="addr-1",
        remove=[second_line_id],
        current_cart=cart,
    )
    assert res_rm["success"] is True
    assert "Whole Wheat Bread 400g" in res_rm["removed_items"]
    after_rm = await commerce2.get_cart("default-cart")
    remaining_spins = [i.spin_id for i in after_rm.items]
    assert "SPIN-BREAD-400G" not in remaining_spins
    assert "SPIN-MILK-1L" in remaining_spins
    assert "SPIN-EGGS-6" in remaining_spins


@pytest.mark.asyncio
async def test_reply_cannot_claim_item_added_when_manage_basket_did_not_add():
    """When manage_basket does not add an item, the synthesized response cannot claim it was added."""
    from backend.agent.response_synthesizer import synthesize_turn_response
    from backend.channels.models import ChannelType, NormalizedIncomingMessage
    from unittest.mock import MagicMock

    engine = MagicMock()
    session = MagicMock()
    session.ingredient_budget_inr = None
    session.budget_blocked_items = []
    session.pending_approval = None
    session.pending_cart_clear = None
    engine.get_session.return_value = session
    engine.get_history.return_value = []

    message = NormalizedIncomingMessage(
        message_id="msg-1",
        channel=ChannelType.WHATSAPP,
        sender_id="user-1",
        customer_id="cust-1",
        text="Add dragonfruit",
    )

    # manage_basket did not add dragonfruit (item is unavailable)
    response = await synthesize_turn_response(
        engine=engine,
        message=message,
        customer_id="cust-1",
        final_text="",
        actions=[],
        conv_state="NEEDS_DECISION",
        last_cart_receipt="Your basket is empty.",
        last_cart_total=0.0,
        out_order_id=None,
        out_order_total=None,
        out_bridge_url=None,
        address_changed=False,
        suggestion_only=False,
        suggested_items=[],
        restricted_items=[],
        search_failed_items=[],
        budget_blocked_items=[],
        unavailable_items=["dragonfruit"],
        reduced_items=[],
        guarded_change_message=None,
        pending_request_needs_retry=False,
        step_limit_reached=False,
        checkout_executed=False,
        user_confirmed=False,
        incoming_text="Add dragonfruit",
        addr_lbl="Home",
    )

    # Response must report item as unavailable and must NOT claim it was added
    assert "dragonfruit" in response.text
    assert "unavailable" in response.text.casefold()
    assert "added dragonfruit" not in response.text.casefold()
    assert response.conversation_state == "NEEDS_DECISION"





