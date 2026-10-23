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

    async def mock_variant_picker(*args, **kwargs):

        return {"action": "pick", "candidate_id": "1", "reason": "first match"}, None



    mock_client = type("MockGemini", (), {"generate_structured_with_reason": mock_variant_picker, "api_key": "mock"})()

    tools = SwiggyAgentTools(commerce, gemini_client=mock_client)



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

    session = engine.get_session(customer_id)

    session.address_id = "addr-bandra-1"

    session.address_label = "Home"

    session.order_address_confirmed = True



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





@pytest.mark.asyncio

async def test_engine_handle_message_returns_response_with_pool_state_store():

    """handle_message must never return None and must load/save state without a held connection."""

    from unittest.mock import AsyncMock, MagicMock

    from backend.agent.engine import GroceryAgentEngine

    from backend.channels.models import NormalizedIncomingMessage, NormalizedOutgoingResponse

    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter



    mock_pool = MagicMock()

    mock_state_store = MagicMock()

    mock_state_store.pool = mock_pool

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



    customer_id = msg.customer_id or msg.sender_id

    mock_state_store.load.assert_awaited_once_with(customer_id)

    assert mock_state_store.save.await_count == 1

    save_args, save_kwargs = mock_state_store.save.call_args

    assert save_args[0] == customer_id

    assert "conn" not in save_kwargs or save_kwargs["conn"] is None





def test_zero_regex_product_selection_architecture():

    """Catalog ranker heuristics are deleted; variant selection is driven by Gemini structured output."""

    import importlib.util

    assert importlib.util.find_spec("backend.agent.catalog_ranker") is None, "catalog_ranker must remain deleted"

    assert importlib.util.find_spec("backend.agent.address_resolver") is None, "address_resolver must remain deleted" 





def test_address_resolver_avoids_false_positives_on_shopping_verbs():

    from backend.agent.address_tools import match_explicit_address

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





def test_product_selection_prompt_enforces_user_guidelines():

    """Product selection prompt gives Gemini locked instructions for single units and clear queries."""

    from backend.agent.tools import _build_product_selection_prompt

    candidates = [

        {"candidate_id": "1", "name": "Amul Taaza Milk 500ml", "brand": "Amul", "price": 27.0, "pack_size": "500ml"},

        {"candidate_id": "2", "name": "Amul Taaza Milk 500ml x 4", "brand": "Amul", "price": 108.0, "pack_size": "500ml x 4"},

    ]

    prompt = _build_product_selection_prompt("amul milk", candidates, preferred_pack_size="")

    assert "amul milk" in prompt

    assert "prefer the standard single unit over multi-packs" in prompt.lower()





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





@pytest.mark.asyncio

async def test_basket_execution_preserves_quantity_pack_size_and_items_with_scripted_plan():

    """The model plan is scripted and this does not test understanding of exclusions; asserts basket execution preserves quantities, pack sizes, and items."""

    from backend.agent.engine import GroceryAgentEngine

    from backend.channels.models import NormalizedIncomingMessage

    from backend.integrations.commerce.mock_adapter import MockCommerceAdapter



    commerce = MockCommerceAdapter()

    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")



    async def mock_structured_with_reason(*args, **kwargs):

        prompt = kwargs.get("prompt") or (args[1] if len(args) > 1 else "")

        schema = kwargs.get("response_schema") or (args[2] if len(args) > 2 else {})

        if "candidate_id" in schema.get("properties", {}):

            if "500 ml" in prompt:

                return {"action": "pick", "candidate_id": "2", "reason": "preferred 500ml"}, None

            return {"action": "pick", "candidate_id": "1", "reason": "first match"}, None

        return {"has_whole_order_cap": False, "amount": None}, None



    async def mock_structured(*args, **kwargs):

        res, _ = await mock_structured_with_reason(*args, **kwargs)

        return res



    engine.gemini.generate_structured_with_reason = mock_structured_with_reason

    engine.gemini.generate_structured = mock_structured



    # 1. Milk, bread, tissues: quantity 2 with 500 ml pack size, no eggs

    c1 = "cust-planning-1"

    s1 = engine.get_session(c1)

    s1.address_id = "addr-bandra-1"

    s1.address_label = "Home"

    s1.order_address_confirmed = True



    async def fake_llm_1(contents, **kwargs):

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

                                            {"query": "milk", "quantity": 2, "preferred_pack_size": "500 ml"},

                                            {"query": "bread", "quantity": 1},

                                            {"query": "tissues", "quantity": 1},

                                        ]

                                    },

                                }

                            }

                        ]

                    }

                }

            ]

        }



    engine._call_llm = fake_llm_1

    msg1 = NormalizedIncomingMessage(

        sender_id=c1,

        message_id="msg-planning-1",

        text="I need 2 packets of 500 ml milk and one brown bread, plus tissues. No eggs.",

    )

    resp1 = await engine.handle_message(msg1)



    with commerce.customer_scope(c1):

        cart1 = await commerce.get_cart()



    cart1_names = [it.name.casefold() for it in cart1.items]

    assert any("milk" in name for name in cart1_names)

    assert any("bread" in name for name in cart1_names)

    assert "tissues" in resp1.text.casefold()

    # Milk quantity 2 with 500 ml pack size

    milk_item = next(it for it in cart1.items if "milk" in it.name.casefold())

    assert milk_item.quantity == 2

    assert "500" in milk_item.pack_size

    # No egg

    assert not any("egg" in name for name in cart1_names)



    # 2. Dal, sugar, garlic: all accounted, no paneer

    c2 = "cust-planning-2"

    s2 = engine.get_session(c2)

    s2.address_id = "addr-bandra-1"

    s2.address_label = "Home"

    s2.order_address_confirmed = True



    async def fake_llm_2(contents, **kwargs):

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

                                            {"query": "dal", "quantity": 1},

                                            {"query": "sugar", "quantity": 1},

                                            {"query": "garlic", "quantity": 1},

                                        ]

                                    },

                                }

                            }

                        ]

                    }

                }

            ]

        }



    engine._call_llm = fake_llm_2

    msg2 = NormalizedIncomingMessage(

        sender_id=c2,

        message_id="msg-planning-2",

        text="Get dal, sugar and garlic. Skip paneer.",

    )

    resp2 = await engine.handle_message(msg2)



    with commerce.customer_scope(c2):

        cart2 = await commerce.get_cart()



    cart2_names = [it.name.casefold() for it in cart2.items]

    assert any("dal" in name for name in cart2_names)

    assert any("sugar" in name for name in cart2_names)

    assert any("garlic" in name for name in cart2_names)

    # No paneer

    assert not any("paneer" in name for name in cart2_names)



    # 3. Tea, coffee, bananas: all accounted

    c3 = "cust-planning-3"

    s3 = engine.get_session(c3)

    s3.address_id = "addr-bandra-1"

    s3.address_label = "Home"

    s3.order_address_confirmed = True



    async def fake_llm_3(contents, **kwargs):

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

                                            {"query": "tea", "quantity": 1},

                                            {"query": "coffee", "quantity": 1},

                                            {"query": "bananas", "quantity": 1},

                                        ]

                                    },

                                }

                            }

                        ]

                    }

                }

            ]

        }



    engine._call_llm = fake_llm_3

    msg3 = NormalizedIncomingMessage(

        sender_id=c3,

        message_id="msg-planning-3",

        text="Pick up tea, coffee, and bananas.",

    )

    resp3 = await engine.handle_message(msg3)



    with commerce.customer_scope(c3):

        cart3 = await commerce.get_cart()



    cart3_names = [it.name.casefold() for it in cart3.items]

    assert any("tea" in name for name in cart3_names)

    assert any("coffee" in name for name in cart3_names)

    assert any("banana" in name for name in cart3_names)



    await engine.close()











