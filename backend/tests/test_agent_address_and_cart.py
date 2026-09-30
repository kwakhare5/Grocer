"""Tests for the autonomous GroceryAgentEngine and Swiggy function-calling tools."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.engine import GroceryAgentEngine
from backend.agent.tools import SwiggyAgentTools
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.integrations.commerce.exceptions import CommerceError, ProviderAuthError
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


@pytest.fixture
def mock_commerce():
    return MockCommerceAdapter()


@pytest.fixture
def agent_engine(mock_commerce):
    return GroceryAgentEngine(mock_commerce)




@pytest.mark.asyncio
async def test_honest_failure_explanation_retains_explanation_and_appends_disclaimer(agent_engine):
    """When LLM provides an honest failure explanation without claiming success,
    the explanation is preserved and the non-placement disclaimer is guaranteed.
    """
    customer_id = "cust_honest_fail"
    agent_engine._customer_address[customer_id] = "addr_home"

    honest_text = "I apologize, but Swiggy Instamart is experiencing high demand right now. Please try again in a few minutes."
    gemini_responses = [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "checkout",
                                    "args": {
                                        "cart_id": "cart_123",
                                        "address_id": "addr_home",
                                        "is_user_confirmed": True,
                                    },
                                }
                            }
                        ]
                    }
                }
            ]
        },
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": honest_text}]
                    }
                }
            ]
        },
    ]

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value={"success": False, "error": "HIGH_DEMAND"})):
        msg = NormalizedIncomingMessage(
            message_id="msg_honest_fail",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id=customer_id,
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "FAILED"
        assert response.order_id is None
        assert "high demand" in response.text.casefold()
        assert "Your order has NOT been placed and your account has not been charged." in response.text


@pytest.mark.asyncio
async def test_auth_expired_uses_default_connect_base(agent_engine, mock_commerce):
    """When CONNECT_BASE_URL is not set, connect link defaults to production Render URL."""
    from backend import config
    with patch.object(mock_commerce, "get_addresses", side_effect=ProviderAuthError("Token expired")), \
         patch.object(config.settings, "CONNECT_BASE_URL", None):
        msg = NormalizedIncomingMessage(
            message_id="msg_auth_default_test",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_default_base",
            text="I need milk",
        )
        response = await agent_engine.handle_message(msg)
        assert "https://grocerr.vercel.app/" in response.text
        assert "?phone=" not in response.text


@pytest.mark.asyncio
async def test_default_address_prioritization(agent_engine, mock_commerce):
    """Engine should prioritize customer's is_default address over other addresses."""
    from backend.integrations.commerce.models import DeliveryAddress
    secondary = DeliveryAddress(id="addr_secondary", label="Work", street="Tower B, Business Hub", city="Bangalore")
    primary = DeliveryAddress(id="addr_primary", label="Home", street="Flat 402, Green Park", city="Bangalore", is_default=True)
    mock_commerce.get_addresses = AsyncMock(return_value=[secondary, primary])

    msg = NormalizedIncomingMessage(
        message_id="msg_addr_test_1",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543210",
        customer_id="cust_addr_pref",
        text="hi",
    )
    with patch.object(agent_engine, "_call_gemini", return_value={"candidates": [{"content": {"parts": [{"text": "Hello!"}]}}]}):
        await agent_engine.handle_message(msg)
        assert agent_engine._customer_address.get("cust_addr_pref") == "addr_primary"


@pytest.mark.asyncio
async def test_select_delivery_address_tool(agent_engine, mock_commerce):
    """Tool can switch delivery address to any valid saved address."""
    from backend.integrations.commerce.models import DeliveryAddress
    addr1 = DeliveryAddress(id="addr_home", label="Home", street="Flat 402, Green Park", city="Bangalore")
    addr2 = DeliveryAddress(id="addr_work", label="Work", street="Tower B, Tech Park", city="Bangalore")
    mock_commerce.get_addresses = AsyncMock(return_value=[addr1, addr2])

    res = await agent_engine._execute_tool(
        "select_delivery_address",
        {"address_id": "addr_home"},
        customer_id="cust_switch_test",
        address_id="addr_work",
    )
    assert res["success"] is True
    assert res["address_id"] == "addr_home"
    assert agent_engine._customer_address["cust_switch_test"] == "addr_home"


def test_token_vault_fallback_to_configured_swiggy_auth_token():
    """Token vault should fall back to settings.SWIGGY_AUTH_TOKEN if not in cache."""
    from backend.integrations.commerce.token_vault import default_token_vault
    from backend import config
    default_token_vault._tokens.clear()
    with patch.object(config.settings, "SWIGGY_AUTH_TOKEN", "fallback_token_xyz"), \
         patch.object(config.settings, "SWIGGY_CUSTOMER_ID", "cust_owner_123"):
        token = default_token_vault.get_token("cust_owner_123")
        assert token == "fallback_token_xyz"
    # Numeric Swiggy customer ID (e.g. 26057200) should match customer
    with patch.object(config.settings, "SWIGGY_AUTH_TOKEN", "fallback_token_numeric"), \
         patch.object(config.settings, "SWIGGY_CUSTOMER_ID", "26057200"):
        token = default_token_vault.get_token("cust_wa_test_owner")
        assert token == "fallback_token_numeric"
    default_token_vault._tokens.clear()


@pytest.mark.asyncio
async def test_track_order_tool(agent_engine, mock_commerce):
    """Tool can track order status, driver info, and ETA."""
    from backend.integrations.commerce.models import DeliveryTrackingStatus
    mock_status = DeliveryTrackingStatus(
        order_id="ord_12345",
        status="OUT_FOR_DELIVERY",
        eta_minutes=12,
        eta_text="~12 mins",
        driver_name="Rahul Sharma",
        driver_phone="9876543210",
        status_message="Rider is on the way",
    )
    mock_commerce.track_order = AsyncMock(return_value=mock_status)

    res = await agent_engine._execute_tool(
        "track_order",
        {"order_id": "ord_12345"},
        customer_id="cust_track_test",
        address_id="addr_pune",
    )
    assert res["success"] is True
    assert res["order_id"] == "ord_12345"
    assert res["status"] == "OUT_FOR_DELIVERY"
    assert res["eta_minutes"] == 12
    assert res["driver_name"] == "Rahul Sharma"


@pytest.mark.asyncio
async def test_preformatted_currency_in_cart_tools(mock_commerce):
    """Verify SwiggyAgentTools returns formatted currency strings for receipt rendering."""
    tools = SwiggyAgentTools(mock_commerce)
    search_res = await tools.search_products("milk", address_id="addr_home")
    assert search_res["success"] is True
    first_var = search_res["products"][0]["variants"][0]
    assert "formatted_price" in first_var
    assert first_var["formatted_price"].startswith("₹")

    cart_res = await tools.get_cart()
    assert cart_res["success"] is True
    assert "formatted_item_total" in cart_res
    assert "formatted_total_fees" in cart_res
    assert "formatted_grand_total" in cart_res
    assert cart_res["formatted_grand_total"].startswith("₹")
    assert "min_order_threshold" in cart_res
    assert "is_serviceable" in cart_res


@pytest.mark.asyncio
async def test_unsupported_media_instant_reply(agent_engine):
    """Voice notes, audio, and images receive an immediate friendly text response."""
    msg = NormalizedIncomingMessage(
        message_id="msg_media_1",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543210",
        customer_id="cust_media",
        text="UNSUPPORTED_MEDIA",
    )
    response = await agent_engine.handle_message(msg)
    assert response.conversation_state == "READY"
    assert "text messages right now" in response.text


@pytest.mark.asyncio
async def test_concurrent_tool_execution_gather(agent_engine):
    """Verify multiple function calls in a single turn are executed concurrently via asyncio.gather."""
    gemini_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "search_products",
                                "args": {"query": "bread"},
                                "id": "call_1",
                            }
                        },
                        {
                            "functionCall": {
                                "name": "search_products",
                                "args": {"query": "eggs"},
                                "id": "call_2",
                            }
                        },
                    ]
                }
            }
        ]
    }
    gemini_final = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Found bread and eggs."}
                    ]
                }
            }
        ]
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=[gemini_resp, gemini_final]):
        msg = NormalizedIncomingMessage(
            message_id="msg_concurrent_1",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_concurrent",
            text="need bread and eggs",
        )
        response = await agent_engine.handle_message(msg)
        assert response.text == "Found bread and eggs."
        # History should have tool responses for both function calls
        history = agent_engine.get_history("cust_concurrent")
        tool_turn = next(h for h in history if h["role"] == "user" and "functionResponse" in h["parts"][0])
        assert len(tool_turn["parts"]) == 2




def test_clean_address_deduplication_and_formatting():
    """Verify full address (flat, building, area, city, state) is preserved without truncation or wrapper."""
    from backend.agent.tools import clean_address

    raw_addr = "John Doe: flat number 1204, Green Park, Green Park, Central Avenue, Sector 5, Bangalore, Karnataka 560001, India"
    cleaned = clean_address(raw_addr, "Bangalore")
    assert "John Doe:" not in cleaned
    assert "India" not in cleaned
    assert "560001" not in cleaned
    assert "Karnataka" in cleaned
    assert "Green Park, Green Park" not in cleaned
    assert "flat number 1204" in cleaned
    assert "Central Avenue" in cleaned
    assert "Sector 5" in cleaned
    assert "Bangalore" in cleaned

    # Test Google Plus Code stripping while keeping full address (flat, building, area, city, state)
    plus_code_raw = "Flat 402, Green Acres, HRC8+HWV, Clover Park, Viman Nagar, Pune, Maharashtra 411014"
    plus_code_cleaned = clean_address(plus_code_raw, "Pune", label="Home")
    assert "HRC8+HWV" not in plus_code_cleaned
    assert "411014" not in plus_code_cleaned
    assert "Home (" not in plus_code_cleaned
    assert "Flat 402, Green Acres, Clover Park, Viman Nagar, Pune, Maharashtra" == plus_code_cleaned

    # Test full address with India stripping
    landmark_raw = "Villa 12, Palm Meadows, Pancard Club Road, Baner, Pune, Maharashtra 411045, India"
    landmark_cleaned = clean_address(landmark_raw, "")
    assert "Villa 12, Palm Meadows, Pancard Club Road, Baner, Pune, Maharashtra" == landmark_cleaned



def test_format_cart_receipt_mathematical_consistency():
    """Verify format_cart_receipt guarantees exact rupee math without mystery fees."""
    from backend.agent.tools import format_cart_receipt
    from backend.integrations.commerce.models import CommerceCart, CartItem

    cart = CommerceCart(
        cart_id="cart_math_test",
        items=[
            CartItem(
                spin_id="SPIN-PASTA",
                name="Yu Zero Maida Penne Pasta",
                pack_size="500g",
                unit_price=49.0,
                quantity=1,
                total_price=49.0,
            ),
            CartItem(
                spin_id="SPIN-SAUCE",
                name="Veeba Pasta Sauce",
                pack_size="280g",
                unit_price=79.0,
                quantity=1,
                total_price=79.0,
            ),
        ],
        item_total=128.0,
        delivery_fee=0.0,
        packaging_fee=0.0,
        handling_fee=15.0,
        taxes=6.0,
        discount=0.0,
        grand_total=149.0,
    )

    receipt = format_cart_receipt(cart, "Flat 402, Green Park, Bangalore")
    assert "*Subtotal:* ₹128" in receipt
    assert "*Delivery Fee:* FREE (₹0)" in receipt
    assert "*Packaging & Handling:* ₹15" in receipt
    assert "*Taxes (GST):* ₹6" in receipt
    assert "*Grand Total:* ₹149" in receipt
    assert "📍 *Delivering to:* Flat 402, Green Park, Bangalore" in receipt


@pytest.mark.asyncio
async def test_tools_cart_fee_itemization(agent_engine):
    """Verify get_cart and update_cart expose complete fee breakdown and verified receipt."""
    from backend.integrations.commerce.models import CommerceCart

    agent_engine.tools.commerce.get_cart = AsyncMock(
        return_value=CommerceCart(
            cart_id="cart_itemized",
            items=[],
            item_total=128.0,
            delivery_fee=0.0,
            packaging_fee=5.0,
            handling_fee=10.0,
            taxes=6.0,
            grand_total=149.0,
        )
    )

    res = await agent_engine.tools.get_cart(delivery_location="Green Park, Bangalore")
    assert res["success"] is True
    assert res["item_total"] == 128.0
    assert res["packaging_fee"] == 5.0
    assert res["handling_fee"] == 10.0
    assert res["taxes"] == 6.0
    assert res["total_fees"] == 21.0
    assert res["grand_total"] == 149.0
    assert res["formatted_delivery_fee"] == "FREE (₹0)"
    assert res["formatted_packaging_and_handling"] == "₹15"
    assert res["formatted_taxes"] == "₹6"
    assert "formatted_receipt" in res


def test_swiggy_parser_bill_reconciliation():
    """Verify build_commerce_cart extracts handling fee, taxes, and reconciles sum to grand_total."""
    from backend.integrations.commerce.swiggy_parsers import build_commerce_cart

    raw_swiggy_data = {
        "cartId": "swiggy_cart_123",
        "items": [],
        "billBreakdown": {
            "lineItems": [
                {"label": "Item Total", "value": "₹128"},
                {"label": "Delivery Partner Fee", "value": "₹0"},
                {"label": "Packaging & Handling", "value": "₹15"},
                {"label": "Govt Taxes & Other Charges", "value": "₹6"},
            ],
            "toPay": {"value": "₹149"},
        },
    }

    cart = build_commerce_cart(raw_swiggy_data)
    assert cart.item_total == 128.0
    assert cart.delivery_fee == 0.0
    assert cart.packaging_fee + cart.handling_fee == 15.0
    assert cart.taxes == 6.0
    assert cart.grand_total == 149.0
    # Strict reconciliation check: 128 + 0 + 15 + 6 == 149
    assert cart.item_total + cart.delivery_fee + cart.packaging_fee + cart.handling_fee + cart.taxes - cart.discount == cart.grand_total


@pytest.mark.asyncio
async def test_self_healing_on_http_400(agent_engine):
    """Verify that _call_gemini recovers cleanly when multi-turn history returns 400 Bad Request."""
    import httpx

    call_count = 0

    async def mock_post(url, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1 and len(json.get("contents", [])) > 1:
            # Simulate Gemini rejecting corrupted history with 400
            return httpx.Response(
                400,
                text="Function call is missing a thought_signature",
                request=httpx.Request("POST", url),
            )
        # Self-healed turn returns 200
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Self healed response"}]}}]},
            request=httpx.Request("POST", url),
        )

    client = await agent_engine._get_client()
    agent_engine._client.post = mock_post

    corrupt_history = [
        {"role": "user", "parts": [{"text": "old message"}]},
        {"role": "model", "parts": [{"functionCall": {"name": "test", "args": {}}}]},
        {"role": "user", "parts": [{"text": "bourbon and jim jam"}]},
    ]
    res = await agent_engine._call_gemini(corrupt_history)
    assert res is not None
    assert call_count == 2
    assert len(corrupt_history) == 1
    assert corrupt_history[0]["parts"][0]["text"] == "bourbon and jim jam"


@pytest.mark.asyncio
async def test_select_delivery_address_returns_active_cart_context(mock_commerce):
    """select_delivery_address attaches active cart state, receipt, and anti-amnesia instructions."""
    from backend.integrations.commerce.models import DeliveryAddress, CartItemUpdate
    addr1 = DeliveryAddress(id="addr_mumbai", label="Mumbai Home", street="Flat 201, Sea View Apartments, Bandra West", city="Mumbai")
    addr2 = DeliveryAddress(id="addr_pune", label="Pune Home", street="Flat 102, Koregaon Park", city="Pune")
    mock_commerce.get_addresses = AsyncMock(return_value=[addr1, addr2])

    tools = SwiggyAgentTools(mock_commerce)
    # Populate cart
    await mock_commerce.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=2, sku_id="sku_1")],
        address_id="addr_mumbai",
    )

    res = await tools.select_delivery_address(customer_id="cust_test_cart", address_id="addr_pune")
    assert res["success"] is True
    assert res["address_id"] == "addr_pune"
    assert res["has_active_cart"] is True
    assert res["item_count"] >= 1
    assert "🛒 *Your Basket" in res["formatted_receipt"]
    assert "Koregaon Park" in res["formatted_receipt"]
    assert "DO NOT ask 'What would you like to order today?'" in res["instruction"]


@pytest.mark.asyncio
async def test_address_switch_preserves_active_cart_and_receipt(agent_engine, mock_commerce):
    """Deterministic guard strictly prevents LLM amnesia when address is changed mid-shopping."""
    from backend.integrations.commerce.models import DeliveryAddress, CartItemUpdate
    addr1 = DeliveryAddress(id="addr_mumbai", label="Mumbai Home", street="Flat 201, Sea View Apartments, Bandra West", city="Mumbai")
    addr2 = DeliveryAddress(id="addr_pune", label="Pune Home", street="Flat 102, Koregaon Park", city="Pune")
    mock_commerce.get_addresses = AsyncMock(return_value=[addr1, addr2])

    agent_engine._customer_address["cust_addr_switch"] = "addr_mumbai"
    agent_engine._customer_address_label["cust_addr_switch"] = "Flat 201, Sea View Apartments, Bandra West, Mumbai"

    # Put items in cart
    await mock_commerce.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=2, sku_id="sku_1")],
        address_id="addr_mumbai",
    )

    # Gemini attempts to switch address, and outputs amnesiac greeting: "What would you like to order today?"
    gemini_responses = [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "select_delivery_address",
                                    "args": {"address_id": "addr_pune"},
                                }
                            }
                        ]
                    }
                }
            ]
        },
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "I've updated your delivery address to Pune! What would you like to order today?"
                            }
                        ]
                    }
                }
            ]
        },
    ]

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses):
        msg = NormalizedIncomingMessage(
            message_id="msg_addr_switch",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_addr_switch",
            text="change address to 2",
        )
        response = await agent_engine.handle_message(msg)

        # Address changed to Pune
        assert agent_engine._customer_address["cust_addr_switch"] == "addr_pune"
        # Amnesiac text must be overridden
        assert "What would you like to order today?" not in response.text
        # Verified receipt must be shown
        assert "🛒 *Your Basket" in response.text
        assert "Koregaon Park" in response.text
        # Confirmation buttons must be present
        assert response.requires_confirmation is True
        assert len(response.interactive_actions) >= 2
        button_ids = [a.id for a in response.interactive_actions]
        assert "confirm_order" in button_ids
        assert "modify_cart" in button_ids
        assert response.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"


@pytest.mark.asyncio
async def test_cart_hesitation_guard_keeps_basket_on_hold(agent_engine, mock_commerce):
    """When user replies 'no' or 'wait' with an active cart, the agent does not abandon the order."""
    from backend.integrations.commerce.models import CartItemUpdate
    await mock_commerce.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1, sku_id="sku_1")],
        address_id="addr_home",
    )
    agent_engine._customer_address["cust_hesitate"] = "addr_home"
    agent_engine._customer_address_label["cust_hesitate"] = "Home"

    for hesitation_input in ["no", "wait", "hold on", "not yet", "no wait"]:
        msg = NormalizedIncomingMessage(
            message_id=f"msg_hesitate_{hesitation_input}",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_hesitate",
            text=hesitation_input,
        )
        response = await agent_engine.handle_message(msg)

        assert "on hold" in response.text.casefold()
        assert "🛒 *Your Basket" in response.text
        assert response.requires_confirmation is True
        action_ids = [a.id for a in response.interactive_actions]
        assert "confirm_order" in action_ids
        assert "modify_cart" in action_ids
        assert "start_fresh" in action_ids
        assert response.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"


@pytest.mark.asyncio
async def test_fast_path_reset_commands_clear_basket(agent_engine, mock_commerce):
    """Reset commands ('start over', 'clear cart') immediately empty basket in <20ms."""
    from backend.integrations.commerce.models import CartItemUpdate
    await mock_commerce.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1, sku_id="sku_1")],
        address_id="addr_home",
    )
    cart = await mock_commerce.get_cart()
    assert len(cart.items) >= 1

    msg = NormalizedIncomingMessage(
        message_id="msg_reset_cmd",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543210",
        customer_id="cust_reset",
        text="start over",
    )
    response = await agent_engine.handle_message(msg)

    assert "Basket Cleared!" in response.text
    assert response.conversation_state == "READY"
    cart_after = await mock_commerce.get_cart()
    assert len(cart_after.items) == 0
    assert len(agent_engine.get_history("cust_reset")) == 0


def test_prune_history_preserves_turn_boundaries(agent_engine):
    """_prune_history cuts strictly at top-level user turn boundaries, never orphaning tool calls."""
    cid = "cust_turn_prune"
    # Build 6 complete conversational turns
    history = []
    for turn in range(6):
        # 1. User message
        history.append({"role": "user", "parts": [{"text": f"Search item {turn}"}]})
        # 2. Model tool call
        history.append({
            "role": "model",
            "parts": [{"functionCall": {"name": "search_products", "args": {"query": f"item {turn}"}}}],
        })
        # 3. User tool response
        history.append({
            "role": "user",
            "parts": [{
                "functionResponse": {
                    "name": "search_products",
                    "response": {"name": "search_products", "content": {"products": [{"name": f"P{turn}_{i}"} for i in range(10)]}},
                }
            }],
        })
        # 4. Model final text
        history.append({"role": "model", "parts": [{"text": f"Found item {turn}!"}]})

    agent_engine._history[cid] = history
    assert len(history) == 24  # 6 turns * 4 messages

    # Prune keeping last 3 user turns
    agent_engine._prune_history(cid, max_user_turns=3)
    pruned = agent_engine._history[cid]

    # Must retain exactly the last 3 turns = 12 messages
    assert len(pruned) == 12
    # The first message in the pruned history MUST be role="user" with text
    assert pruned[0]["role"] == "user"
    assert "text" in pruned[0]["parts"][0]
    assert pruned[0]["parts"][0]["text"] == "Search item 3"
    # Never starts with a functionResponse
    assert "functionResponse" not in pruned[0]["parts"][0]
    # Older search results in pruned history are compacted to <= 2 items
    older_content = pruned[2]["parts"][0]["functionResponse"]["response"]["content"]
    assert len(older_content["products"]) <= 2


@pytest.mark.asyncio
async def test_live_basket_state_injected_into_gemini_prompt(agent_engine, mock_commerce):
    """_call_gemini receives live cart state and injects it into systemInstruction."""
    from backend.integrations.commerce.models import CartItemUpdate
    await mock_commerce.update_cart(
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=2, sku_id="sku_1"),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1, sku_id="sku_2"),
        ],
        address_id="addr_home",
    )
    cart = await mock_commerce.get_cart()

    captured_payload = None

    async def capture_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        import httpx
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
            request=httpx.Request("POST", url),
        )

    await agent_engine._get_client()
    with patch.object(agent_engine._client, "post", side_effect=capture_post):
        await agent_engine._call_gemini(
            [{"role": "user", "parts": [{"text": "hello"}]}],
            address_id="addr_home",
            address_label="Green Park, Bangalore",
            cart=cart,
        )

    assert captured_payload is not None
    system_instruction = captured_payload["systemInstruction"]["parts"][0]["text"]
    assert "### LIVE BASKET STATE (ACTIVE ON SWIGGY INSTAMART):" in system_instruction
    assert "Active Basket Item Count: 2" in system_instruction
    assert "CRITICAL INVARIANT" in system_instruction
    assert "Green Park, Bangalore" in system_instruction


def test_parse_delivery_addresses_combines_address_line_and_formatted_address():
    """parse_delivery_addresses must combine addressLine and formattedAddress so area, city, and state are never dropped."""
    from backend.integrations.commerce.swiggy_parsers import parse_delivery_addresses
    from backend.agent.tools import clean_address

    raw_mcp_payload = {
        "addresses": [
            {
                "id": "addr_baner",
                "annotation": "Other",
                "addressLine": "Villa 12, Palm Meadows, Pancard Club Road",
                "formattedAddress": "Baner, Pune, Maharashtra 411045, India",
                "city": None,
            }
        ]
    }
    parsed = parse_delivery_addresses(raw_mcp_payload)
    assert len(parsed) == 1
    cleaned = clean_address(parsed[0].street, parsed[0].city)
    assert "Villa 12" in cleaned
    assert "Palm Meadows" in cleaned
    assert "Pancard Club Road" in cleaned
    assert "Baner" in cleaned
    assert "Pune" in cleaned
    assert "Maharashtra" in cleaned


@pytest.mark.asyncio
async def test_upfront_multi_address_disambiguation_and_resume_on_choice(agent_engine, mock_commerce):
    """When user has multiple non-default addresses on a new order, ask upfront and resume Turn 1 order upon selection."""
    from backend.integrations.commerce.models import DeliveryAddress

    addr1 = DeliveryAddress(
        id="addr_viman",
        label="Home",
        street="Flat 402, Green Acres, Clover Park, Viman Nagar, Pune, Maharashtra",
        city="Pune",
        is_default=False,
    )
    addr2 = DeliveryAddress(
        id="addr_baner",
        label="Other",
        street="Villa 12, Palm Meadows, Pancard Club Road, Baner, Pune, Maharashtra",
        city="Pune",
        is_default=False,
    )
    mock_commerce.get_addresses = AsyncMock(return_value=[addr1, addr2])

    # Turn 1: User sends grocery request on a fresh session
    msg1 = NormalizedIncomingMessage(
        message_id="msg_disambig_1",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543210",
        customer_id="cust_multi_addr",
        text="i want milk and bread",
    )
    resp1 = await agent_engine.handle_message(msg1)
    assert "Which address should I deliver this order to?" in resp1.text
    assert "Green Acres" in resp1.text
    assert "Palm Meadows" in resp1.text
    assert "cust_multi_addr" in agent_engine._awaiting_address_choice

    # Turn 2: User replies "2" -> selects addr_baner and immediately processes "i want milk and bread"
    gemini_turn2_responses = [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "update_cart",
                                    "args": {
                                        "items": [{"spin_id": "SPIN-MILK-1L", "quantity": 1, "sku_id": "sku_1"}],
                                        "address_id": "addr_baner",
                                    },
                                }
                            }
                        ]
                    }
                }
            ]
        },
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "I have added milk for your Baner address!"}]
                    }
                }
            ]
        },
    ]
    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_turn2_responses) as mock_gemini:
        msg2 = NormalizedIncomingMessage(
            message_id="msg_disambig_2",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_multi_addr",
            text="2",
        )
        resp2 = await agent_engine.handle_message(msg2)
        assert agent_engine._customer_address["cust_multi_addr"] == "addr_baner"
        assert agent_engine._order_address_confirmed["cust_multi_addr"] is True
        assert "Villa 12, Palm Meadows, Pancard Club Road, Baner, Pune, Maharashtra" in resp2.text
        assert "🛒 *Your Basket" in resp2.text
        assert mock_gemini.called


@pytest.mark.asyncio
async def test_update_cart_delta_merge_preserves_existing_items_and_handles_removal(mock_commerce):
    """SwiggyAgentTools.update_cart must merge partial item updates with existing cart items instead of wiping them."""
    tools = SwiggyAgentTools(mock_commerce)

    # Step 1: Add Milk (qty 2) and Bread (qty 1)
    res1 = await tools.update_cart(
        items=[
            {"spin_id": "SPIN-MILK-1L", "quantity": 2, "sku_id": "sku_milk"},
            {"spin_id": "SPIN-BREAD-400G", "quantity": 1, "sku_id": "sku_bread"},
        ],
        address_id="addr-bandra-1",
    )
    assert res1["success"] is True
    assert len(res1["items"]) == 2

    # Step 2: Partial update adding Eggs (qty 1) without repeating Milk and Bread -> must have 3 items!
    res2 = await tools.update_cart(
        items=[{"spin_id": "SPIN-EGGS-6", "quantity": 1, "sku_id": "sku_eggs"}],
        address_id="addr-bandra-1",
    )
    assert res2["success"] is True
    spin_ids_in_cart = {it["spin_id"] for it in res2["items"]}
    assert spin_ids_in_cart == {"SPIN-MILK-1L", "SPIN-BREAD-400G", "SPIN-EGGS-6"}

    # Step 3: Remove Bread by passing quantity=0 -> Milk and Eggs must remain!
    res3 = await tools.update_cart(
        items=[{"spin_id": "SPIN-BREAD-400G", "quantity": 0, "sku_id": "sku_bread"}],
        address_id="addr-bandra-1",
    )
    assert res3["success"] is True
    spin_ids_after_remove = {it["spin_id"] for it in res3["items"]}
    assert spin_ids_after_remove == {"SPIN-MILK-1L", "SPIN-EGGS-6"}


@pytest.mark.asyncio
async def test_post_update_cart_gemini_hiccup_never_hides_built_cart(agent_engine, mock_commerce):
    """If update_cart succeeds on Step 1 and Gemini rate-limits/returns None on Step 2, the verified receipt is still returned."""
    agent_engine._customer_address["cust_hiccup"] = "addr-bandra-1"
    agent_engine._customer_address_label["cust_hiccup"] = "14 Pali Hill Road, Bandra West, Mumbai"
    agent_engine._order_address_confirmed["cust_hiccup"] = True

    gemini_step1 = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "update_cart",
                                "args": {
                                    "items": [{"spin_id": "SPIN-MILK-1L", "quantity": 2, "sku_id": "sku_1"}],
                                    "address_id": "addr-bandra-1",
                                },
                            }
                        }
                    ]
                }
            }
        ]
    }
    # Step 2 returns None (simulating Gemini 429 rate limit after cart was already built)
    with patch.object(agent_engine, "_call_gemini", side_effect=[gemini_step1, None]):
        msg = NormalizedIncomingMessage(
            message_id="msg_hiccup_1",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_hiccup",
            text="2 milk",
        )
        resp = await agent_engine.handle_message(msg)
        assert "connection hiccup" not in resp.text.casefold()
        assert "🛒 *Your Basket" in resp.text
        assert "14 Pali Hill Road, Bandra West, Mumbai" in resp.text
        assert resp.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"


def test_swiggy_mcp_client_resolves_live_settings_token():
    """SwiggyMcpClient.resolve_token dynamically picks up updated settings.SWIGGY_AUTH_TOKEN after OAuth re-login."""
    from backend.integrations.commerce.swiggy_client import SwiggyMcpClient
    from backend.config import settings

    old_setting = settings.SWIGGY_AUTH_TOKEN
    try:
        settings.SWIGGY_AUTH_TOKEN = "initial_boot_token"
        client = SwiggyMcpClient("https://mcp.swiggy.com/im", auth_token="initial_boot_token")
        assert client.resolve_token("cust_123") == "initial_boot_token"

        # Simulate OAuth re-login updating settings.SWIGGY_AUTH_TOKEN at runtime
        settings.SWIGGY_AUTH_TOKEN = "refreshed_oauth_token_999"
        assert client.resolve_token("cust_123") == "refreshed_oauth_token_999"
    finally:
        settings.SWIGGY_AUTH_TOKEN = old_setting


@pytest.mark.asyncio
async def test_gemini_multi_model_fallback_on_503(agent_engine):
    """When the primary Gemini model returns HTTP 503/429, _call_gemini immediately pivots to the next fallback model."""
    import httpx

    called_urls: list[str] = []

    async def fake_post(url: str, json=None):
        called_urls.append(url)
        if "gemini-3.5-flash-lite" in url:
            return httpx.Response(503, text='{"error":{"message":"high demand"}}')
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Recovered via fallback model!"}]}}]},
        )

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.post = AsyncMock(side_effect=fake_post)
    agent_engine._client = mock_client
    agent_engine.model = "gemini-3.5-flash-lite"

    res = await agent_engine._call_gemini([{"role": "user", "parts": [{"text": "hi"}]}])
    assert res is not None
    assert len(called_urls) == 2
    assert "gemini-3.5-flash-lite" in called_urls[0]
    assert "gemini-flash-lite-latest" in called_urls[1]





