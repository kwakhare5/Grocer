"""Tests for Slice D2c: Truth-based claim checking and live classifier accuracy."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch
import pytest

from backend.agent.claim_check import build_facts_text, check_reply_claims
from backend.agent.engine import GroceryAgentEngine
from backend.agent.gemini import GeminiClient
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.config import settings
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem, CommerceCart


# ============================================================================
# Requirement 5: Facts text unit test & supported price passthrough / error receipt
# ============================================================================

def test_facts_text_contains_real_cart_and_tool_prices():
    """Verify build_facts_text includes exact cart items, prices, fees, totals, and tool products."""
    cart = CommerceCart(
        items=[
            CartItem(
                spin_id="SPIN-MILK-500ML",
                product_id="p-milk",
                name="Nandini GoodLife Milk",
                pack_size="500 ml",
                unit_price=30.0,
                quantity=2,
                total_price=60.0,
            ),
            CartItem(
                spin_id="SPIN-OIL-1L",
                product_id="p-oil",
                name="Fortune Sunflower Oil",
                pack_size="1 L",
                unit_price=145.0,
                quantity=1,
                total_price=145.0,
            ),
        ],
        item_total=205.0,
        delivery_fee=30.0,
        packaging_fee=5.0,
        grand_total=240.0,
    )

    tool_results = [
        {
            "success": True,
            "query": "bread",
            "products": [
                {
                    "product_id": "p-bread",
                    "name": "Britannia Whole Wheat Bread",
                    "variants": [
                        {
                            "name": "Britannia Whole Wheat Bread",
                            "pack_size": "400 g",
                            "price": 45.0,
                            "in_stock": True,
                        }
                    ],
                },
                {
                    "product_id": "p-rice",
                    "name": "Daawat Basmati Rice",
                    "variants": [
                        {
                            "name": "Daawat Basmati Rice",
                            "pack_size": "1 kg",
                            "price": 120.0,
                            "in_stock": False,
                        }
                    ],
                },
            ],
        }
    ]

    facts = build_facts_text(cart=cart, tool_results=tool_results)

    # Cart facts asserted
    assert "Current Basket:" in facts
    assert "Nandini GoodLife Milk (500 ml): qty 2, unit price ₹30.0, total ₹60.0" in facts
    assert "Fortune Sunflower Oil (1 L): qty 1, unit price ₹145.0, total ₹145.0" in facts
    assert "Item Subtotal: ₹205.0" in facts
    assert "Delivery Fee: ₹30.0" in facts
    assert "Packaging Fee: ₹5.0" in facts
    assert "Grand Total: ₹240.0" in facts

    # Tool facts asserted
    assert "Products from recent search / tool results:" in facts
    assert "Britannia Whole Wheat Bread (400 g): ₹45.0, in stock" in facts
    assert "Daawat Basmati Rice (1 kg): ₹120.0, out of stock" in facts


@pytest.mark.asyncio
async def test_correct_price_answer_with_verdict_supported_passes_unchanged():
    """A correct price answer with verdict 'supported' passes through to the customer unchanged."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "test-cust-supported-price"
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(items=[
            CartItem(
                spin_id="SPIN-MILK-500ML",
                product_id="p-milk",
                name="Nandini GoodLife Milk",
                pack_size="500 ml",
                unit_price=30.0,
                quantity=1,
                total_price=30.0,
            )
        ])

    correct_price_reply = "Nandini GoodLife Milk 500 ml is ₹30 and in stock."

    async def fake_model_reply(_contents, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": correct_price_reply}]}}]}

    engine._call_llm = fake_model_reply

    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="supported")), \
         patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            customer_id=customer_id,
            message_id="msg-price-inquiry",
            channel=ChannelType.WHATSAPP,
            text="how much is milk?",
        )
        response = await engine.handle_message(msg)

    assert response is not None
    assert response.text == correct_price_reply
    assert response.order_id is None


@pytest.mark.asyncio
async def test_claim_check_error_and_timeout_give_receipt():
    """When claim check errors or times out, the turn safely falls back to a real cart receipt."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "test-cust-claim-err"
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(items=[
            CartItem(
                spin_id="SPIN-MILK-500ML",
                product_id="p-milk",
                name="Nandini GoodLife Milk",
                pack_size="500 ml",
                unit_price=30.0,
                quantity=1,
                total_price=30.0,
            )
        ])

    async def fake_model_reply(_contents, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Your total is ₹9999 and order is confirmed!"}]}}]}

    engine._call_llm = fake_model_reply

    # Case A: Exception raised in check_reply_claims
    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(side_effect=TimeoutError("Claim check timed out"))), \
         patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            customer_id=customer_id,
            message_id="msg-timeout",
            channel=ChannelType.WHATSAPP,
            text="check status",
        )
        response_timeout = await engine.handle_message(msg)

    assert response_timeout is not None
    assert "🛒" in response_timeout.text
    assert "Milk" in response_timeout.text
    assert "9999" not in response_timeout.text

    # Case B: Returned 'unclear'
    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="unclear")), \
         patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            customer_id=customer_id,
            message_id="msg-unclear",
            channel=ChannelType.WHATSAPP,
            text="check status",
        )
        response_unclear = await engine.handle_message(msg)

    assert response_unclear is not None
    assert "🛒" in response_unclear.text
    assert "Milk" in response_unclear.text
    assert "9999" not in response_unclear.text


# ============================================================================
# Requirement 6: Live Accuracy Test against Fixed Facts Text
# ============================================================================

FIXED_FACTS_TEXT = """Current Basket:
- Nandini GoodLife Milk (500 ml): qty 2, unit price ₹30, total ₹60
- Fortune Sunflower Oil (1 L): qty 1, unit price ₹145, total ₹145
- Item Subtotal: ₹205
- Delivery Fee: ₹30
- Packaging Fee: ₹5
- Grand Total: ₹240
Products from recent search / tool results:
- Britannia Whole Wheat Bread (400 g): ₹45, in stock
- Farm Fresh Eggs (6 pack): ₹65, in stock
- Daawat Basmati Rice (1 kg): ₹120, out of stock
"""

CASES = [
    # 10 True replies (supported or no_claim)
    ("Your basket has 2 packets of Nandini GoodLife Milk and 1 bottle of Fortune Sunflower Oil.", "supported"),
    ("The grand total including delivery and packaging is ₹240.", "supported"),
    ("The delivery fee is ₹30 and packaging fee is ₹5.", "supported"),
    ("Fortune Sunflower Oil is ₹145 for 1 L.", "supported"),
    ("Nandini GoodLife Milk is ₹30 per 500 ml packet.", "supported"),
    ("Britannia Whole Wheat Bread 400g is available for ₹45.", "supported"),
    ("Farm Fresh Eggs 6 pack is currently in stock for ₹65.", "supported"),
    ("Daawat Basmati Rice 1 kg is currently out of stock.", "supported"),
    ("Hello! How can I help with your grocery shopping today?", "no_claim"),
    ("Would you like to deliver to your saved address?", "no_claim"),

    # 10 False replies (unsupported)
    ("Nandini GoodLife Milk is ₹15 per packet.", "unsupported"),  # wrong price
    ("I have added 1 kg of Alphonso Mangoes to your basket.", "unsupported"),  # uncarted item
    ("Your order has been placed successfully and will arrive in 15 minutes!", "unsupported"),  # fake order placed
    ("Your total comes to ₹999.", "unsupported"),  # wrong total
    ("Daawat Basmati Rice is in stock and ready to add.", "unsupported"),  # wrong stock claim
    ("Your basket has Belgian chocolate ice cream.", "unsupported"),  # uncarted item
    ("Fortune Sunflower Oil costs ₹250 per bottle.", "unsupported"),  # wrong price
    ("Order confirmed! Your groceries are on their way.", "unsupported"),  # fake order placed
    ("The grand total for your order is ₹150.", "unsupported"),  # wrong total
    ("Britannia Whole Wheat Bread is out of stock today.", "unsupported"),  # wrong stock claim
]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_classifier_accuracy():
    """Live accuracy test evaluating 10 true and 10 false replies against fixed facts.

    Marked live. Skipped unless a valid GEMINI_API_KEY is present.
    Never prints API key. Does not fail suite on accuracy.
    """
    key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
    if not key or key in {"mock-key", "local-test", "test-key"}:
        pytest.skip("GEMINI_API_KEY not set or is dummy test key")

    client = GeminiClient(api_key=key)
    try:
        results = []
        correct = 0
        for idx, (reply, expected) in enumerate(CASES, 1):
            try:
                got = await check_reply_claims(client, reply, facts_text=FIXED_FACTS_TEXT)
            except Exception as exc:
                got = f"error: {exc}"

            is_match = (got == expected)
            if is_match:
                correct += 1
            results.append((idx, reply, expected, got, is_match))
            await asyncio.sleep(0.5)

        accuracy_pct = (correct / len(CASES)) * 100.0

        # Print formatted report table safely
        print("\n" + "=" * 90)
        print("LIVE CLASSIFIER ACCURACY REPORT")
        print("=" * 90)
        print(f"{'#':<3} | {'Expected':<12} | {'Got':<12} | {'Match':<5} | {'Reply'}")
        print("-" * 90)
        for idx, reply, expected, got, is_match in results:
            match_str = "YES" if is_match else "NO"
            safe_reply = reply.replace("₹", "Rs ")
            print(f"{idx:<3} | {expected:<12} | {got:<12} | {match_str:<5} | {safe_reply}")
        print("-" * 90)
        print(f"Total Accuracy: {correct}/{len(CASES)} ({accuracy_pct:.1f}%)")
        print("=" * 90 + "\n")

    finally:
        await client.close()
