"""Empirical challenger stress test suite for PAYMENT_PENDING handling and UPI payment link injection.
Authored by Challenger M1-It2-2.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from backend.agent.engine import GroceryAgentEngine, _claims_order_success
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter

# 32 grammatical success variations
SUCCESS_CLAIMS = [
    "Your order was placed!",
    "Your order was successfully placed.",
    "Your order was confirmed.",
    "Your order was booked.",
    "Your basket was checked out successfully.",
    "Your order has been placed.",
    "Your order has been confirmed.",
    "Your order has been booked!",
    "Your order has been received.",
    "Your groceries have been ordered.",
    "Your items have been ordered successfully!",
    "Your purchase has been confirmed.",
    "I have placed an order for you!",
    "I placed the order for your groceries.",
    "I have ordered your items.",
    "I completed your order.",
    "I submitted your order to Swiggy.",
    "I went ahead and placed your order.",
    "We have placed your order.",
    "We have confirmed your order!",
    "Order placed!",
    "Order completed!",
    "Order completed successfully!",
    "Order successful!",
    "Order confirmed!",
    "Order booked successfully!",
    "Order accepted by Swiggy!",
    "Order processed successfully!",
    "Your order was successful!",
    "Your order has succeeded!",
    "Your order is complete!",
    "Your order went through!",
    "Your order has gone through!",
    "Your checkout is complete!",
    "Your delivery is on its way!",
    "Delivery is on its way!",
    "Your groceries are on their way!",
    "Your items are on the way to you!",
    "All set! Your groceries are on their way.",
    "Your delivery partner is on the way.",
    "There was an issue with one item, but your order was placed!",
    "Even though milk was adjusted, your order went through!",
]

SUBTLE_ADVERSARIAL_CLAIMS = [
    "## Order Summary\n\nGreat news! **Your order was confirmed.**\nTotal: ₹499\nDelivery in 10 mins.",
    "🎉 Hooray! Your basket was checked out successfully! Please pay: {link}",
    "Your payment went through! Complete here: {link}",
    "Swiggy is preparing your order now.",
    "Your groceries are en route! Click {link} to finish up.",
    "I have completed your order. Link: {link}",
    "Your delivery is on its way! Link: {link}",
    "Order dispatched! Please tap {link} to confirm payment.",
    "Your purchase is complete. Tap {link}",
    "Your order has been submitted. Pay here: {link}",
]

HONEST_MESSAGES = [
    "Your cart has 3 items ready for payment. Total is ₹450.",
    "Everything is set up for your Pune address. Grand total is ₹506.",
    "I have prepared your grocery basket.",
    "Delivering to Baner, Pune. Please proceed with payment.",
]


@pytest.fixture
def mock_commerce():
    return MockCommerceAdapter()


@pytest.fixture
def agent_engine(mock_commerce):
    return GroceryAgentEngine(mock_commerce)


def _make_msg(cust_id: str = "cust_test") -> NormalizedIncomingMessage:
    return NormalizedIncomingMessage(
        message_id="msg_test",
        channel=ChannelType.WHATSAPP,
        sender_id="+919876543210",
        customer_id=cust_id,
        text="Confirm order",
    )


def _make_gemini_responses(llm_text: str):
    return [
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
                        "parts": [{"text": llm_text}],
                    }
                }
            ]
        },
    ]


# ============================================================================
# TEST SET 1: Premature success claims WITHOUT pay link in LLM text
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("claim", SUCCESS_CLAIMS)
async def test_premature_claim_without_link_is_overridden_and_link_injected(agent_engine, claim):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_1"
    agent_engine._customer_address["cust_test"] = "addr_home"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-001",
        "status": "PAYMENT_PENDING",
        "grand_total": 350.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=350.0&tr=paas_test_1",
        "paas_id": "paas_test_1",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(claim)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        # Overridden text must NOT claim order success
        assert not _claims_order_success(resp.text), f"Success claim leaked: {resp.text}"
        # Overridden text must clarify payment is required
        assert "complete payment to place your order" in resp.text.casefold()
        # Payment link must be present exactly once
        assert bridge_url in resp.text
        assert resp.text.count(bridge_url) == 1
        assert resp.payment_bridge_url == bridge_url
        assert resp.order_id == "OD-PENDING-001"
        assert resp.order_total == 350.0


# ============================================================================
# TEST SET 2: Premature success claims WITH pay link in LLM text (deduplication)
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("claim", SUCCESS_CLAIMS)
async def test_premature_claim_with_link_is_overridden_without_duplication(agent_engine, claim):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_2"
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = f"{claim} Please click {bridge_url} to pay."

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-002",
        "status": "PAYMENT_PENDING",
        "grand_total": 420.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=420.0&tr=paas_test_2",
        "paas_id": "paas_test_2",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        # Overridden text must NOT claim order success
        assert not _claims_order_success(resp.text), f"Success claim leaked: {resp.text}"
        # Overridden text must clarify payment is required
        assert "complete payment to place your order" in resp.text.casefold()
        # Payment link must be present exactly once (no duplication from original + override)
        assert bridge_url in resp.text
        assert resp.text.count(bridge_url) == 1


# ============================================================================
# TEST SET 2B: Subtle adversarial markdown & compound claims WITH pay link
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("template", SUBTLE_ADVERSARIAL_CLAIMS)
async def test_subtle_adversarial_claims_overridden_cleanly(agent_engine, template):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_subtle"
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = template.format(link=bridge_url)

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-SUBTLE",
        "status": "PAYMENT_PENDING",
        "grand_total": 499.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=499.0&tr=paas_subtle",
        "paas_id": "paas_subtle",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert not _claims_order_success(resp.text), f"Subtle success claim leaked: {resp.text}"
        assert bridge_url in resp.text
        assert resp.text.count(bridge_url) == 1
        assert "complete payment to place your order" in resp.text.casefold()


# ============================================================================
# TEST SET 3: Honest messages without link (link injection)
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("honest_text", HONEST_MESSAGES)
async def test_honest_message_without_link_gets_link_injected_once(agent_engine, honest_text):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_3"
    agent_engine._customer_address["cust_test"] = "addr_home"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-003",
        "status": "PAYMENT_PENDING",
        "grand_total": 500.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=500.0&tr=paas_test_3",
        "paas_id": "paas_test_3",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(honest_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        # Honest text is preserved
        assert honest_text in resp.text
        # Link is injected cleanly
        assert bridge_url in resp.text
        assert resp.text.count(bridge_url) == 1
        assert "👉 Complete payment to place your order:" in resp.text


# ============================================================================
# TEST SET 4: Honest messages WITH bridge_url already present (no duplicate)
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("honest_text", HONEST_MESSAGES)
async def test_honest_message_with_bridge_url_does_not_duplicate(agent_engine, honest_text):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_4"
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = f"{honest_text}\nPay here: {bridge_url}"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-004",
        "status": "PAYMENT_PENDING",
        "grand_total": 500.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=500.0&tr=paas_test_4",
        "paas_id": "paas_test_4",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        # Link must appear exactly once
        assert resp.text.count(bridge_url) == 1
        # Should not append "👉 Complete payment to place your order:"
        assert "👉 Complete payment to place your order:" not in resp.text


# ============================================================================
# TEST SET 4B: Markdown link format [Pay Here](url) does not duplicate
# ============================================================================
@pytest.mark.asyncio
async def test_markdown_link_does_not_duplicate(agent_engine):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_md"
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = f"Please proceed to payment: [Pay Now]({bridge_url})."

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-MD",
        "status": "PAYMENT_PENDING",
        "grand_total": 300.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=300.0&tr=paas_test_md",
        "paas_id": "paas_test_md",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert resp.text.count(bridge_url) == 1
        assert "👉 Complete payment to place your order:" not in resp.text


# ============================================================================
# TEST SET 5: Honest message WITH upi_intent_url already present (no duplicate)
# ============================================================================
@pytest.mark.asyncio
async def test_honest_message_with_upi_url_does_not_duplicate_bridge_url(agent_engine):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_5"
    upi_url = "upi://pay?pa=swiggy@icici&am=500.0&tr=paas_test_5"
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = f"Your basket is ready. Pay via UPI: {upi_url}"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-005",
        "status": "PAYMENT_PENDING",
        "grand_total": 500.0,
        "bridge_url": bridge_url,
        "upi_intent_url": upi_url,
        "paas_id": "paas_test_5",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert resp.text.count(upi_url) == 1
        # Does not redundantly append bridge_url
        assert bridge_url not in resp.text


# ============================================================================
# TEST SET 6: Empty or whitespace LLM text
# ============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("empty_input", ["", "   ", "\n\t  \n"])
async def test_empty_or_whitespace_llm_text_gets_fallback_with_link(agent_engine, empty_input):
    bridge_url = "https://instamart.swiggy.com/pay/bridge/paas_test_6"
    agent_engine._customer_address["cust_test"] = "addr_home"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-006",
        "status": "PAYMENT_PENDING",
        "grand_total": 150.0,
        "bridge_url": bridge_url,
        "upi_intent_url": "upi://pay?pa=swiggy@icici&am=150.0&tr=paas_test_6",
        "paas_id": "paas_test_6",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(empty_input)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert bridge_url in resp.text
        assert resp.text.count(bridge_url) == 1
        assert "Your order is ready! Please complete payment to place your order:" in resp.text


# ============================================================================
# TEST SET 7: Missing payment links (bridge_url is None and upi_url is None)
# ============================================================================
@pytest.mark.asyncio
async def test_missing_payment_links_with_premature_claim(agent_engine):
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = "Your order has been placed and is on the way!"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-007",
        "status": "PAYMENT_PENDING",
        "grand_total": 200.0,
        "bridge_url": None,
        "upi_intent_url": None,
        "paas_id": None,
        "is_qr_flow": False,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert not _claims_order_success(resp.text)
        assert "complete payment in your Swiggy app" in resp.text
        assert "None" not in resp.text


@pytest.mark.asyncio
async def test_missing_payment_links_with_honest_text(agent_engine):
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = "Your basket is ready. Grand total is ₹200."

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-008",
        "status": "PAYMENT_PENDING",
        "grand_total": 200.0,
        "bridge_url": None,
        "upi_intent_url": None,
        "paas_id": None,
        "is_qr_flow": False,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert "Your basket is ready" in resp.text
        assert "complete payment in your Swiggy app" in resp.text
        assert "None" not in resp.text


# ============================================================================
# TEST SET 8: Only upi_intent_url present (bridge_url is None)
# ============================================================================
@pytest.mark.asyncio
async def test_only_upi_url_present_injected_properly(agent_engine):
    upi_url = "upi://pay?pa=swiggy@icici&am=250.0&tr=paas_test_9"
    agent_engine._customer_address["cust_test"] = "addr_home"
    llm_text = "Your order was placed successfully!"

    checkout_pending = {
        "success": True,
        "order_id": "OD-PENDING-009",
        "status": "PAYMENT_PENDING",
        "grand_total": 250.0,
        "bridge_url": None,
        "upi_intent_url": upi_url,
        "paas_id": "paas_test_9",
        "is_qr_flow": True,
    }

    with patch.object(agent_engine, "_call_gemini", side_effect=_make_gemini_responses(llm_text)), \
         patch.object(agent_engine.tools, "checkout", AsyncMock(return_value=checkout_pending)):
        resp = await agent_engine.handle_message(_make_msg())

        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert not _claims_order_success(resp.text)
        assert upi_url in resp.text
        assert resp.text.count(upi_url) == 1
        assert "complete payment to place your order" in resp.text.casefold()
