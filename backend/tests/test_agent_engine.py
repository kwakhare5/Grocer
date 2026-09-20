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
async def test_checkout_safety_guard_blocks_unconfirmed_orders(mock_commerce):
    """The checkout tool MUST reject any order if is_user_confirmed is False."""
    tools = SwiggyAgentTools(mock_commerce)
    result = await tools.checkout(
        cart_id="cart_123",
        address_id="addr_home",
        is_user_confirmed=False,
    )
    assert result["success"] is False
    assert result["error"] == "CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_checkout_succeeds_when_user_explicitly_confirms(mock_commerce):
    """When the user has explicitly confirmed and cart has items, checkout succeeds."""
    tools = SwiggyAgentTools(mock_commerce)
    cart_res = await tools.update_cart(
        items=[{"spin_id": "SPIN-MILK-1L", "quantity": 2, "sku_id": "sku_1"}],
        address_id="addr_home",
    )
    result = await tools.checkout(
        cart_id=cart_res["cart_id"],
        address_id="addr_home",
        payment_method="UPI",
        is_user_confirmed=True,
    )
    assert result["success"] is True
    assert "order_id" in result


@pytest.mark.asyncio
async def test_auth_expired_triggers_reconnect_prompt(agent_engine, mock_commerce):
    """When Swiggy MCP returns 401 / auth expired, agent prompts user with reconnect link."""
    with patch.object(
        mock_commerce, "get_addresses", side_effect=ProviderAuthError("Token expired")
    ):
        msg = NormalizedIncomingMessage(
            message_id="msg_auth_test",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_test",
            text="I need milk",
        )
        response = await agent_engine.handle_message(msg)
        assert "expired" in response.text.casefold()
        assert "grocerr.vercel.app" in response.text


@pytest.mark.asyncio
async def test_search_and_update_cart_tools(mock_commerce):
    """Verify SwiggyAgentTools can search products and update cart properly."""
    tools = SwiggyAgentTools(mock_commerce)
    search_res = await tools.search_products("milk", address_id="addr_home")
    assert search_res["success"] is True
    assert search_res["count"] > 0
    first_variant = search_res["products"][0]["variants"][0]

    cart_res = await tools.update_cart(
        items=[{"spin_id": first_variant["spin_id"], "quantity": 2, "sku_id": first_variant["sku_id"]}],
        address_id="addr_home",
    )
    assert cart_res["success"] is True
    assert len(cart_res["items"]) >= 1
    assert cart_res["grand_total"] > 0


@pytest.mark.asyncio
async def test_checkout_passes_qr_and_returns_payment_links(mock_commerce):
    """Checkout tool defaults payment_option_kind to 'qr' and returns payment links."""
    tools = SwiggyAgentTools(mock_commerce)
    cart_res = await tools.update_cart(
        items=[{"spin_id": "SPIN-MILK-1L", "quantity": 2, "sku_id": "sku_1"}],
        address_id="addr_home",
    )
    result = await tools.checkout(
        cart_id=cart_res["cart_id"],
        address_id="addr_home",
        payment_method="UPI",
        is_user_confirmed=True,
    )
    assert result["success"] is True
    assert result["status"] == "PAYMENT_PENDING"
    assert result["is_qr_flow"] is True
    assert result["paas_id"] is not None and result["paas_id"].startswith("paas_mock_")
    assert result["bridge_url"] is not None and "bridge" in result["bridge_url"]
    assert result["upi_intent_url"] is not None and result["upi_intent_url"].startswith("upi://pay")


@pytest.mark.asyncio
async def test_deterministic_fail_closed_guard_overrides_hallucinated_success(agent_engine):
    """Fail-closed guard strictly overrides LLM hallucinations if checkout fails."""
    agent_engine._customer_address["cust_fail_test"] = "addr_home"

    # Step 1: Gemini calls checkout
    # Step 2: Gemini hallucinates that the order has been placed despite checkout failure
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
                        "parts": [
                            {
                                "text": "Your order has been placed! It is on the way and will arrive shortly."
                            }
                        ]
                    }
                }
            ]
        },
    ]

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value={"success": False, "error": "ITEM_OUT_OF_STOCK"})):
        msg = NormalizedIncomingMessage(
            message_id="msg_fail_guard",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_fail_test",
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "FAILED"
        assert response.order_id is None
        assert "order has been placed" not in response.text.casefold()
        assert "NOT been placed" in response.text
        assert "account has not been charged" in response.text
        assert "ITEM_OUT_OF_STOCK" in response.text


@pytest.mark.asyncio
async def test_deterministic_fail_closed_guard_handles_empty_llm_response(agent_engine):
    """Fail-closed guard injects explicit failure notice if LLM text is empty on failed checkout."""
    agent_engine._customer_address["cust_empty_test"] = "addr_home"

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
                                        "cart_id": "cart_empty",
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
                        "parts": [
                            {"text": ""}
                        ]
                    }
                }
            ]
        },
    ]

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value={"success": False, "error": "ADDRESS_UNSERVICEABLE"})):
        msg = NormalizedIncomingMessage(
            message_id="msg_empty_guard",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_empty_test",
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "FAILED"
        assert "NOT been placed" in response.text
        assert "ADDRESS_UNSERVICEABLE" in response.text


@pytest.mark.asyncio
async def test_deterministic_fail_closed_guard_preserves_honest_failure_message(agent_engine):
    """When LLM provides an honest failure explanation without claiming success, preserve its text."""
    agent_engine._customer_address["cust_honest_test"] = "addr_home"

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
                                        "cart_id": "cart_honest",
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
                        "parts": [
                            {
                                "text": "Unfortunately, Swiggy is experiencing high demand right now and cannot take this order."
                            }
                        ]
                    }
                }
            ]
        },
    ]

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value={"success": False, "error": "HIGH_DEMAND"})):
        msg = NormalizedIncomingMessage(
            message_id="msg_honest_guard",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_honest_test",
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "FAILED"
        assert "experiencing high demand" in response.text


@pytest.mark.asyncio
async def test_deterministic_guard_injects_missing_payment_link(agent_engine):
    """Deterministic guard appends the payment link if checkout succeeded with PAYMENT_PENDING but LLM omitted it."""
    agent_engine._customer_address["cust_pay_test"] = "addr_home"
    expected_bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_123"

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
                                        "cart_id": "cart_pay",
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
                        "parts": [
                            {
                                "text": "Your basket is ready and your items are reserved!"
                            }
                        ]
                    }
                }
            ]
        },
    ]

    checkout_success = {
        "success": True,
        "order_id": "OD-TEST-999",
        "status": "PAYMENT_PENDING",
        "grand_total": 350.0,
        "bridge_url": expected_bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=350.0&tr=paas_test_123",
        "paas_id": "paas_test_123",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_success)):
        msg = NormalizedIncomingMessage(
            message_id="msg_pay_test",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_pay_test",
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "AWAITING_PAYMENT"
        assert response.order_id == "OD-TEST-999"
        assert response.order_total == 350.0
        assert response.payment_bridge_url == expected_bridge_url
        assert expected_bridge_url in response.text
        assert "Complete payment to place your order" in response.text


@pytest.mark.asyncio
async def test_deterministic_guard_avoids_duplicate_payment_link(agent_engine):
    """If LLM already included the payment link, guard does not duplicate it."""
    agent_engine._customer_address["cust_dup_test"] = "addr_home"
    expected_bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_123"

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
                                        "cart_id": "cart_dup",
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
                        "parts": [
                            {
                                "text": f"Please click here to pay: {expected_bridge_url}"
                            }
                        ]
                    }
                }
            ]
        },
    ]

    checkout_success = {
        "success": True,
        "order_id": "OD-TEST-999",
        "status": "PAYMENT_PENDING",
        "grand_total": 350.0,
        "bridge_url": expected_bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=350.0&tr=paas_test_123",
        "paas_id": "paas_test_123",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_success)):
        msg = NormalizedIncomingMessage(
            message_id="msg_dup_test",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_dup_test",
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "AWAITING_PAYMENT"
        assert response.text.count(expected_bridge_url) == 1


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_passes_generate_upi_qr():
    """SwiggyMCPAdapter.checkout sets generateUPIQR: True when payment_option_kind='qr'."""
    adapter = SwiggyMCPAdapter()
    adapter._call_mcp_tool = AsyncMock(
        return_value={
            "data": {
                "orderId": "OD-SWIGGY-888",
                "status": "PAYMENT_PENDING",
                "bridgeUrl": "https://instamart.swiggy.com/pay/bridge/paas_888",
                "upiIntentUrl": "upi://pay?pa=swiggy@icici&tr=paas_888",
                "paasId": "paas_888",
                "isQrFlow": True,
            }
        }
    )
    result = await adapter.checkout(
        cart_id="cart_swiggy_test",
        address_id="addr_pune_1",
        payment_method="UPI",
        payment_option_kind="qr",
        explicit_confirmation=True,
    )
    adapter._call_mcp_tool.assert_called_once_with(
        "checkout",
        {
            "addressId": "addr_pune_1",
            "paymentMethod": "UPI",
            "generateUPIQR": True,
        },
    )
    assert result.order_id == "OD-SWIGGY-888"
    assert result.status == "PAYMENT_PENDING"
    assert result.bridge_url == "https://instamart.swiggy.com/pay/bridge/paas_888"
    assert result.upi_intent_url == "upi://pay?pa=swiggy@icici&tr=paas_888"
    assert result.paas_id == "paas_888"
    assert result.is_qr_flow is True


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_rejects_ambiguous_upi():
    """SwiggyMCPAdapter.checkout raises AMBIGUOUS_PAYMENT_OPTION if UPI has no kind."""
    adapter = SwiggyMCPAdapter()
    with pytest.raises(CommerceError) as exc_info:
        await adapter.checkout(
            cart_id="cart_swiggy_test",
            address_id="addr_pune_1",
            payment_method="UPI",
            payment_option_kind=None,
            explicit_confirmation=True,
        )
    assert exc_info.value.code == "AMBIGUOUS_PAYMENT_OPTION"


@pytest.mark.asyncio
async def test_engine_execute_tool_passes_payment_option_kind(agent_engine):
    """_execute_tool correctly forwards payment_option_kind to tools.checkout."""
    with patch.object(agent_engine.tools, "checkout", AsyncMock(return_value={"success": True})) as mock_checkout:
        await agent_engine._execute_tool(
            "checkout",
            {
                "cart_id": "cart_test",
                "address_id": "addr_test",
                "payment_method": "UPI",
                "payment_option_kind": "qr",
                "is_user_confirmed": True,
            },
            customer_id="cust_1",
            address_id="addr_test",
        )
        mock_checkout.assert_called_once_with(
            cart_id="cart_test",
            address_id="addr_test",
            payment_method="UPI",
            payment_option_kind="qr",
            is_user_confirmed=True,
        )


# ==============================================================================
# Parameterized Adversarial Test Suite: Fail-Closed Guard (Explorer M1 Fix 3)
# ==============================================================================

FAIL_CLOSED_GRAMMATICAL_TEST_CASES = [
    # 1. Past tense passive: "was placed"
    pytest.param(
        "Your order was placed! It will arrive in 15 minutes.",
        "ITEM_OUT_OF_STOCK",
        "Amul Taaza Milk 500ml is out of stock",
        id="past_passive_was_placed_item_out_of_stock",
    ),
    # 2. Present perfect active (first person plural): "We have confirmed"
    pytest.param(
        "We have confirmed your order! Sit back and relax.",
        "PAYMENT_GATEWAY_ERROR",
        "Payment gateway unreachable",
        id="active_we_confirmed_payment_gateway_error",
    ),
    # 3. First person singular active: "I have placed an order"
    pytest.param(
        "I have placed an order for you with Swiggy Instamart.",
        "INVALID_CART",
        "Cart session expired or invalid",
        id="active_i_placed_order_invalid_cart",
    ),
    # 4. Predicate adjective: "was successful"
    pytest.param(
        "Your order was successful! Track it on Swiggy.",
        "ADDRESS_UNSERVICEABLE",
        "Address outside dark store delivery radius",
        id="pred_adj_was_successful_address_unserviceable",
    ),
    # 5. Verb variation: "succeeded"
    pytest.param(
        "Your order has succeeded! It's on its way.",
        "HIGH_DEMAND",
        "High demand surge in your zone",
        id="verb_succeeded_high_demand",
    ),
    # 6. Exclamatory short phrase: "Order completed!"
    pytest.param(
        "Order completed! Your delivery partner is assigned.",
        "STORE_CLOSED",
        "Dark store closed for the night",
        id="short_order_completed_store_closed",
    ),
    # 7. Booking phrasing: "has been booked"
    pytest.param(
        "Your order has been booked! Expected delivery in 12 mins.",
        "PRICE_CHANGED",
        "Cart item prices have changed",
        id="passive_has_been_booked_price_changed",
    ),
    # 8. Colloquial idiom: "went through"
    pytest.param(
        "Your order went through and will arrive soon.",
        "PAYMENT_FAILED",
        "UPI transaction declined by bank",
        id="idiom_went_through_payment_failed",
    ),
    # 9. Delivery assertion: "Delivery is on its way"
    pytest.param(
        "Delivery is on its way! Fresh groceries coming up.",
        "SLOT_UNAVAILABLE",
        "No delivery slots currently available",
        id="delivery_on_way_slot_unavailable",
    ),
    # 10. Direct grocery noun assertion: "groceries are on their way"
    pytest.param(
        "All set! Your groceries are on their way to your home.",
        "ITEM_OUT_OF_STOCK",
        "Britannia Brown Bread is out of stock",
        id="groceries_on_way_item_out_of_stock",
    ),
    # 11. Third party acceptance: "accepted by Swiggy"
    pytest.param(
        "Order accepted by Swiggy! Delivery in 10 minutes.",
        "MIN_ORDER_VALUE_NOT_MET",
        "Minimum order value of Rs 199 not met",
        id="third_party_accepted_min_order_value",
    ),
    # 12. First person direct: "I have ordered your items"
    pytest.param(
        "I have ordered your items. They will be delivered shortly.",
        "GATEWAY_TIMEOUT",
        "Provider connection timed out",
        id="active_i_ordered_items_gateway_timeout",
    ),
    # 13. Items passive: "items have been ordered"
    pytest.param(
        "Your items have been ordered successfully!",
        "PAYMENT_GATEWAY_ERROR",
        "Bank payment gateway error",
        id="passive_items_ordered_payment_gateway_error",
    ),
    # 14. First person past: "I completed your order"
    pytest.param(
        "I completed your order with Swiggy Instamart.",
        "INVALID_CART",
        "Cart is empty or modified",
        id="active_i_completed_order_invalid_cart",
    ),
    # 15. State predicate: "order is complete"
    pytest.param(
        "Your order is complete! Thank you for ordering.",
        "ADDRESS_UNSERVICEABLE",
        "Location not serviceable by partner pod",
        id="pred_order_is_complete_address_unserviceable",
    ),
    # 16. Past submission: "submitted your order"
    pytest.param(
        "I submitted your order to Swiggy. Arriving in 15 mins.",
        "HIGH_DEMAND",
        "Store temporarily busy",
        id="active_submitted_order_high_demand",
    ),
    # 17. Processed phrasing: "Order processed successfully"
    pytest.param(
        "Order processed successfully! Check your app for live tracking.",
        "STORE_CLOSED",
        "Store currently closed",
        id="passive_order_processed_store_closed",
    ),
    # 18. Compound partial error + success claim
    pytest.param(
        "There was an issue with one item, but your order was placed!",
        "ITEM_OUT_OF_STOCK",
        "Tomatoes 500g out of stock",
        id="compound_error_and_placed_item_out_of_stock",
    ),
    # 19. Idiomatic present perfect: "order has gone through"
    pytest.param(
        "Great news! Your order has gone through without issues.",
        "PAYMENT_FAILED",
        "Card payment failed",
        id="idiom_order_has_gone_through_payment_failed",
    ),
    # 20. Package/booking phrasing: "items have been booked"
    pytest.param(
        "Your items have been booked and are being packed.",
        "PROVIDER_ERROR",
        "Internal provider error 500",
        id="passive_items_booked_provider_error",
    ),
    # 21. Bare exclamation: "Order successful!"
    pytest.param(
        "Order successful! Your groceries are getting packed.",
        "ITEM_OUT_OF_STOCK",
        "Milk out of stock",
        id="bare_order_successful_out_of_stock",
    ),
    # 22. Conversational completion: "All done! Your groceries are ordered."
    pytest.param(
        "All done! Your groceries are ordered.",
        "INVALID_CART",
        "Invalid checkout payload",
        id="colloquial_groceries_ordered_invalid_cart",
    ),
    # 23. Compound polite + delivered: "Sorry, your order has been delivered!"
    pytest.param(
        "Sorry, your order has been delivered!",
        "ITEM_OUT_OF_STOCK",
        "Amul Milk out of stock",
        id="compound_polite_order_delivered_item_out_of_stock",
    ),
    # 24. Compound polite + active dispatched: "Unfortunately, we dispatched your order!"
    pytest.param(
        "Unfortunately, we dispatched your order!",
        "PAYMENT_GATEWAY_ERROR",
        "Payment gateway failure",
        id="compound_polite_active_dispatched_payment_gateway_error",
    ),
    # 25. Compound polite + delivered groceries: "Sorry, we delivered your groceries!"
    pytest.param(
        "Sorry, we delivered your groceries!",
        "INVALID_CART",
        "Cart invalid",
        id="compound_polite_delivered_groceries_invalid_cart",
    ),
    # 26. Compound polite + fulfilled: "Sorry, we fulfilled your order!"
    pytest.param(
        "Sorry, we fulfilled your order!",
        "HIGH_DEMAND",
        "High demand",
        id="compound_polite_fulfilled_order_high_demand",
    ),
    # 27. Compound polite + is fulfilled: "Sorry, your order is fulfilled!"
    pytest.param(
        "Sorry, your order is fulfilled!",
        "ADDRESS_UNSERVICEABLE",
        "Address unserviceable",
        id="compound_polite_order_is_fulfilled_address_unserviceable",
    ),
    # 28. Compound error + delivered: "There was an error, but your order has been delivered!"
    pytest.param(
        "There was an error, but your order has been delivered!",
        "PAYMENT_FAILED",
        "Payment declined",
        id="compound_error_order_delivered_payment_failed",
    ),
    # 29. Compound out of stock + dispatched: "Unfortunately an item was out of stock, but we dispatched your order!"
    pytest.param(
        "Unfortunately an item was out of stock, but we dispatched your order!",
        "ITEM_OUT_OF_STOCK",
        "Tomatoes out of stock",
        id="compound_out_of_stock_dispatched_order",
    ),
    # 30. Compound delay + shipped: "Sorry for the delay, we shipped your order!"
    pytest.param(
        "Sorry for the delay, we shipped your order!",
        "STORE_CLOSED",
        "Store closed",
        id="compound_delay_shipped_order_store_closed",
    ),
    # 31. Compound issue + items delivered: "I apologize for the issue, but your items were delivered!"
    pytest.param(
        "I apologize for the issue, but your items were delivered!",
        "PROVIDER_ERROR",
        "Provider error 500",
        id="compound_apologize_items_delivered_provider_error",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("hallucinated_text,error_code,error_message", FAIL_CLOSED_GRAMMATICAL_TEST_CASES)
async def test_deterministic_fail_closed_guard_overrides_all_grammatical_variations(
    agent_engine, hallucinated_text: str, error_code: str, error_message: str
):
    """Fail-closed guard strictly overrides LLM hallucinations across 22 distinct grammatical variations and provider errors."""
    customer_id = f"cust_fail_{error_code.lower()}"
    agent_engine._customer_address[customer_id] = "addr_home"

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
                        "parts": [
                            {"text": hallucinated_text}
                        ]
                    }
                }
            ]
        },
    ]

    mock_checkout_result = {
        "success": False,
        "error": error_code,
        "message": error_message,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=mock_checkout_result)):
        msg = NormalizedIncomingMessage(
            message_id="msg_fail_guard_param",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id=customer_id,
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        # 1. State must strictly be FAILED
        assert response.conversation_state == "FAILED", (
            f"Expected state 'FAILED' but got '{response.conversation_state}' for error '{error_code}'"
        )
        # 2. No order ID should be returned
        assert response.order_id is None, "Order ID must be None on failed checkout"
        # 3. No success claims allowed to reach the customer
        assert "not been placed" in response.text.casefold(), (
            f"Expected 'NOT been placed' notice, got: {response.text}"
        )
        assert "account has not been charged" in response.text.casefold(), (
            f"Expected 'account has not been charged' notice, got: {response.text}"
        )
        # 4. Error code or message must be transparently exposed
        assert error_code in response.text or error_message in response.text, (
            f"Expected error details ({error_code} / {error_message}) in response text: {response.text}"
        )
        # 5. Hallucinated success text must NOT be present verbatim
        assert hallucinated_text not in response.text, (
            f"Hallucinated success text leaked to customer: {hallucinated_text}"
        )


# ==============================================================================
# Classifier Sensitivity & Specificity Unit Tests (_claims_order_success)
# ==============================================================================

GRAMMATICAL_SUCCESS_CLAIMS = [
    # Past passive with "was"
    "Your order was placed!",
    "Your order was successfully placed.",
    "Your order was confirmed.",
    "Your order was booked.",
    "Your basket was checked out successfully.",
    # Present perfect passive with "has been / have been"
    "Your order has been placed.",
    "Your order has been confirmed.",
    "Your order has been booked!",
    "Your order has been received.",
    "Your groceries have been ordered.",
    "Your items have been ordered successfully!",
    "Your purchase has been confirmed.",
    # Active voice (I / We)
    "I have placed an order for you!",
    "I placed the order for your groceries.",
    "I have ordered your items.",
    "I completed your order.",
    "I submitted your order to Swiggy.",
    "I went ahead and placed your order.",
    "We have placed your order.",
    "We have confirmed your order!",
    # Short elliptical / exclamatory phrases
    "Order placed!",
    "Order completed!",
    "Order completed successfully!",
    "Order successful!",
    "Order confirmed!",
    "Order booked successfully!",
    "Order accepted by Swiggy!",
    "Order processed successfully!",
    # Predicate adjectives & idioms
    "Your order was successful!",
    "Your order has succeeded!",
    "Your order is complete!",
    "Your order went through!",
    "Your order has gone through!",
    "Your checkout is complete!",
    # Delivery & dispatch assertions
    "Your delivery is on its way!",
    "Delivery is on its way!",
    "Your groceries are on their way!",
    "Your items are on the way to you!",
    "All set! Your groceries are on their way.",
    "Your delivery partner is on the way.",
    # Compound phrases
    "There was an issue with one item, but your order was placed!",
    "Even though milk was adjusted, your order went through!",
    # Compound adversarial phrases (polite/failure tokens + delivery/dispatch/fulfillment)
    "Sorry, your order has been delivered!",
    "Unfortunately, we dispatched your order!",
    "Sorry, we delivered your groceries!",
    "Sorry, we fulfilled your order!",
    "Sorry, your order is fulfilled!",
    "There was an error, but your order has been delivered!",
    "Unfortunately an item was out of stock, but we dispatched your order!",
    "Sorry for the delay, we shipped your order!",
    "I apologize for the issue, but your items were delivered!",
    "We have shipped your order.",
    "Your items were sent successfully!",
]

BENIGN_NON_SUCCESS_MESSAGES = [
    "I could not complete your order because milk is out of stock.",
    "Your order could not be placed due to an error.",
    "Unfortunately, Swiggy is experiencing high demand right now.",
    "Failed to place your order: address unserviceable.",
    "There was an error processing your cart. Please try again.",
    "Would you like me to place this order for ₹450?",
    "Your cart contains milk and bread. Should I place the order?",
    "Please confirm if you want me to order these groceries.",
    "I found Amul Milk and Britannia Bread. Shall I add them to your cart?",
    "Your cart total is ₹320. Delivering to Baner, Pune.",
    "Your order has NOT been placed and your account has not been charged.",
]


@pytest.mark.parametrize("phrase", GRAMMATICAL_SUCCESS_CLAIMS)
def test_claims_order_success_detects_grammatical_variations(phrase: str):
    """Verify that _claims_order_success returns True for all valid grammatical variations of success claims."""
    from backend.agent.engine import _claims_order_success
    assert _claims_order_success(phrase) is True, f"Failed to detect success claim: {phrase}"


@pytest.mark.parametrize("phrase", BENIGN_NON_SUCCESS_MESSAGES)
def test_claims_order_success_does_not_flag_benign_messages(phrase: str):
    """Verify that _claims_order_success returns False for honest errors, confirmation prompts, and safe notices."""
    from backend.agent.engine import _claims_order_success
    assert _claims_order_success(phrase) is False, f"False positive detection on benign phrase: {phrase}"


# ==============================================================================
# Payment Pending Premature Success Guard Test
# ==============================================================================

@pytest.mark.asyncio
async def test_deterministic_guard_prevents_premature_order_placed_claims_on_payment_pending(agent_engine):
    """When status is PAYMENT_PENDING, agent must NOT declare order already placed or on the way."""
    agent_engine._customer_address["cust_pay_pending_test"] = "addr_home"
    expected_bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_pending"

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
                                        "cart_id": "cart_pending",
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
                        "parts": [
                            {
                                "text": f"Your order has been placed and is on the way! Pay here: {expected_bridge_url}"
                            }
                        ]
                    }
                }
            ]
        },
    ]

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-123",
        "status": "PAYMENT_PENDING",
        "grand_total": 299.0,
        "bridge_url": expected_bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=299.0&tr=paas_test_pending",
        "paas_id": "paas_test_pending",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        msg = NormalizedIncomingMessage(
            message_id="msg_pay_pending",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id="cust_pay_pending_test",
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "AWAITING_PAYMENT"
        # Invariant: When payment is pending, the customer must NOT be told the order is already placed / en route
        assert "on the way" not in response.text.casefold(), f"Premature dispatch claim leaked: {response.text}"
        assert expected_bridge_url in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrase,error_code",
    [
        ("Sorry, your order has been delivered!", "ITEM_OUT_OF_STOCK"),
        ("Unfortunately, we dispatched your order!", "PAYMENT_GATEWAY_ERROR"),
        ("Sorry, we delivered your groceries!", "INVALID_CART"),
        ("Sorry, we fulfilled your order!", "HIGH_DEMAND"),
        ("Sorry, your order is fulfilled!", "ADDRESS_UNSERVICEABLE"),
        ("There was an error, but your order has been delivered!", "PAYMENT_FAILED"),
        ("Unfortunately an item was out of stock, but we dispatched your order!", "ITEM_OUT_OF_STOCK"),
        ("Sorry for the delay, we shipped your order!", "STORE_CLOSED"),
        ("I apologize for the issue, but your items were delivered!", "PROVIDER_ERROR"),
    ],
)
async def test_fail_closed_guard_intercepts_compound_adversarial_phrases(
    agent_engine, phrase: str, error_code: str
):
    """Verify compound adversarial phrases containing polite tokens combined with delivery/dispatch verbs are intercepted unconditionally."""
    customer_id = "cust_adversarial_test"
    agent_engine._customer_address[customer_id] = "addr_home"

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
                                        "cart_id": "cart_adv",
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
                        "parts": [{"text": phrase}]
                    }
                }
            ]
        },
    ]

    with patch.object(agent_engine, "_call_gemini", side_effect=gemini_responses), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value={"success": False, "error": error_code})):
        msg = NormalizedIncomingMessage(
            message_id="msg_adv",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id=customer_id,
            text="Confirm order",
        )
        response = await agent_engine.handle_message(msg)

        assert response.conversation_state == "FAILED"
        assert response.order_id is None
        assert phrase not in response.text
        # Intercepted success verbs must not leak
        for verb in ["delivered", "dispatched", "fulfilled", "shipped"]:
            assert verb not in response.text.casefold()
        # Non-placement disclaimer must be strictly present
        assert "Your order has NOT been placed and your account has not been charged." in response.text
        assert error_code in response.text


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


@pytest.mark.asyncio
async def test_history_pruning_sliding_window(agent_engine):
    """Verify history is capped to 12 entries and older search results are compacted."""
    cid = "cust_prune_test"
    # Populate with 14 turns
    agent_engine._history[cid] = [
        {"role": "user", "parts": [{"functionResponse": {"response": {"content": {"products": [{"name": f"P{i}"} for i in range(10)]}}}}]}
        for i in range(14)
    ]
    agent_engine._prune_history(cid)
    # Check sliding window
    assert len(agent_engine._history[cid]) == 12
    # Check compaction on older turns
    older_entry = agent_engine._history[cid][0]
    older_content = older_entry["parts"][0]["functionResponse"]["response"]["content"]
    assert len(older_content["products"]) <= 2


def test_clean_address_deduplication_and_formatting():
    """Verify raw repetitive address string is formatted cleanly for WhatsApp."""
    from backend.agent.tools import clean_address

    raw_addr = "John Doe: flat number 1204, Green Park, Green Park, Central Avenue, Sector 5, Bangalore, Karnataka 560001, India"
    cleaned = clean_address(raw_addr, "Bangalore")
    assert "John Doe:" not in cleaned
    assert "India" not in cleaned
    assert "560001" not in cleaned
    assert "Karnataka" not in cleaned
    assert "Green Park, Green Park" not in cleaned
    assert "flat number 1204" in cleaned
    assert "Bangalore" in cleaned


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



