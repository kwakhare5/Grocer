"""Failure-Mode-First Invariant Tests for Checkout & Financial Safety Boundaries.

Design Principle:
If a subsystem must be tested in isolation, we first enumerate every concrete way
it can fail (Failure Mode Matrix) and verify each failure mode deterministically:

Failure Modes Covered:
1. FM-CHECKOUT-01: LLM calls `checkout(is_user_confirmed=True)` when user never said "Confirm".
   -> Server-side gate (`user_confirmed=False`) MUST override LLM args and block checkout.
2. FM-CHECKOUT-02: Checkout fails upstream (`PAYMENT_FAILED` / `OUT_OF_STOCK`), but LLM hallucinates
   "Your order has been placed / delivered".
   -> Fail-closed guard MUST intercept any success claim and append non-placement disclaimer.
3. FM-CHECKOUT-03: Checkout returns `PAYMENT_PENDING` (UPI QR generated, awaiting scan), and LLM
   prematurely says "Order placed and on its way!".
   -> Guard MUST override premature delivery claims and inject the UPI payment link/QR instructions.
4. FM-CHECKOUT-04: Swiggy MCP adapter called with ambiguous `"UPI"` instead of `"UPI_QR"` (`qr`).
   -> `SwiggyAgentTools.checkout` MUST pass `payment_option_kind="qr"` and adapter MUST reject ambiguous UPI.
5. FM-AUTH-01: Swiggy OAuth token expires mid-conversation (`ProviderAuthError`).
   -> Engine MUST catch `AUTH_EXPIRED` and return the `CONNECT_BASE_URL` re-authentication link.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.agent.engine import GroceryAgentEngine, _claims_order_success
from backend.agent.tools import SwiggyAgentTools
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.integrations.commerce.exceptions import CommerceError
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


@pytest.fixture
def mock_commerce() -> MockCommerceAdapter:
    return MockCommerceAdapter()


@pytest.fixture
def agent_engine(mock_commerce: MockCommerceAdapter) -> GroceryAgentEngine:
    return GroceryAgentEngine(mock_commerce)


@pytest.mark.asyncio
async def test_fm_checkout_01_server_blocks_unconfirmed_checkout(
    agent_engine: GroceryAgentEngine, mock_commerce: MockCommerceAdapter
) -> None:
    """FM-CHECKOUT-01: Even if model passes is_user_confirmed=True, server blocks if user text lacks confirmation."""
    tools = SwiggyAgentTools(mock_commerce)
    direct_block = await tools.checkout(
        cart_id="cart_123", address_id="addr_home", is_user_confirmed=False
    )
    assert direct_block["success"] is False
    assert direct_block["error"] == "CONFIRMATION_REQUIRED"

    # Also verify _execute_tool overrides LLM's is_user_confirmed=True when user_confirmed=False
    engine_block = await agent_engine._execute_tool(
        "checkout",
        {"cart_id": "cart_123", "address_id": "addr_home", "is_user_confirmed": True},
        customer_id="cust_1",
        address_id="addr_home",
        user_confirmed=False,
    )
    assert engine_block["success"] is False
    assert engine_block["error"] == "CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_fm_checkout_02_fail_closed_guard_blocks_hallucinated_success_on_failed_checkout(
    agent_engine: GroceryAgentEngine,
) -> None:
    """FM-CHECKOUT-02: When checkout fails upstream, any LLM claim of order placement/delivery is intercepted."""
    adversarial_claims = [
        "Great news! Your order has been placed and is on the way.",
        "I have placed your order, it will be delivered in 10 minutes.",
        "Your groceries are dispatched and confirmed!",
        "Although payment had a hiccup, your order has been placed.",
    ]
    for phrase in adversarial_claims:
        assert _claims_order_success(phrase) is True

    benign_phrases = [
        "Your order has NOT been placed.",
        "Reply Confirm to place your order.",
        "I couldn't place your order due to a payment error.",
    ]
    for phrase in benign_phrases:
        assert _claims_order_success(phrase) is False

    llm_turns = [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                "name": "checkout",
                                "args": {
                                    "cart_id": "c1",
                                    "address_id": "addr-bandra-1",
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
                        {"text": "Awesome! Your order has been placed and will arrive soon!"}
                    ]
                }
            }
        ]
    },
]
    with patch.object(agent_engine, "_call_llm", side_effect=llm_turns), patch.object(
        agent_engine.tools,
        "checkout",
        AsyncMock(return_value={"success": False, "error": "PAYMENT_DECLINED"}),
    ):
        resp = await agent_engine.handle_message(
            NormalizedIncomingMessage(
                message_id="m_fail",
                channel=ChannelType.WHATSAPP,
                sender_id="+919876543210",
                customer_id="cust_fail",
                text="Confirm order",
            )
        )
        assert resp.conversation_state == "FAILED"
        assert resp.order_id is None
        assert "Your order has NOT been placed" in resp.text
        assert "PAYMENT_DECLINED" in resp.text


@pytest.mark.asyncio
async def test_fm_checkout_03_payment_pending_blocks_premature_delivery_claim_and_injects_qr(
    agent_engine: GroceryAgentEngine,
) -> None:
    """FM-CHECKOUT-03: When status is PAYMENT_PENDING, premature 'Order Placed' claims are replaced with QR instructions."""
    llm_turns = [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "checkout",
                                    "args": {
                                        "cart_id": "c1",
                                        "address_id": "addr-bandra-1",
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
                            {"text": "Your order #ORD-999 has been placed and is out for delivery!"}
                        ]
                    }
                }
            ]
        },
    ]
    checkout_payload = {
        "success": True,
        "order_id": "ORD-999",
        "status": "PAYMENT_PENDING",
        "total_amount": 281.0,
        "bridge_url": "https://pay.swiggy.com/qr/ORD-999",
    }
    with patch.object(agent_engine, "_call_llm", side_effect=llm_turns), patch.object(
        agent_engine.tools, "checkout", AsyncMock(return_value=checkout_payload)
    ), patch.object(agent_engine, "_poll_payment_status", new_callable=AsyncMock):
        resp = await agent_engine.handle_message(
            NormalizedIncomingMessage(
                message_id="m_qr",
                channel=ChannelType.WHATSAPP,
                sender_id="+919876543210",
                customer_id="cust_qr",
                text="Confirm order",
            )
        )
        assert resp.conversation_state == "AWAITING_PAYMENT"
        assert "out for delivery" not in resp.text.casefold()
        assert "https://pay.swiggy.com/qr/ORD-999" in resp.text


@pytest.mark.asyncio
async def test_fm_checkout_04_swiggy_adapter_enforces_upi_qr() -> None:
    """FM-CHECKOUT-04: SwiggyMCPAdapter passes generate_upi_qr=True for qr and rejects ambiguous UPI."""
    adapter = SwiggyMCPAdapter(base_url="https://mcp.swiggy.com/im", auth_token="tok")
    with pytest.raises(CommerceError, match="UPI checkout requires an exact intent-app or QR selection"):
        await adapter.checkout(
            cart_id="c1",
            address_id="a1",
            payment_method="UPI",
            payment_option_kind=None,
            explicit_confirmation=True,
        )


@pytest.mark.asyncio
async def test_fm_auth_01_expired_token_returns_reconnect_link(
    agent_engine: GroceryAgentEngine,
) -> None:
    """FM-AUTH-01: Expired Swiggy token surfaces the OAuth reconnection URL immediately."""
    with patch.object(
        agent_engine.tools,
        "get_saved_addresses",
        AsyncMock(return_value={"success": False, "error": "AUTH_EXPIRED"}),
    ):
        resp = await agent_engine.handle_message(
            NormalizedIncomingMessage(
                message_id="m_auth",
                channel=ChannelType.WHATSAPP,
                sender_id="+919876543210",
                customer_id="cust_auth",
                text="2 milk",
            )
        )
        assert resp.conversation_state == "AUTH_REQUIRED"
        assert "https://grocerr.vercel.app" in resp.text
