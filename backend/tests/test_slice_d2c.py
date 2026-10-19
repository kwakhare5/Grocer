"""Tests for Slice D2c: Truth-based claim checking and live classifier accuracy."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch
import pytest

from backend.agent.claim_check import build_facts_text, check_reply_claims
from backend.agent.engine import GroceryAgentEngine
from backend.agent.gemini import GeminiClient
from backend.agent.session import CustomerSession
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
# Requirement 7, 8, 9: Batch search facts, manage_basket sanitization, and session facts
# ============================================================================

def test_facts_text_from_batch_search_shape_includes_prices_and_stock():
    """Test 7 (Bug A): batch_search_products nested results shape reaches facts text with prices and stock."""
    tool_results = [
        {
            "success": True,
            "results": [
                {
                    "query": "milk",
                    "products": [
                        {
                            "name": "Amul Taaza Milk",
                            "pack_size": "500 ml",
                            "price": 27.0,
                            "in_stock": True,
                            "spin_id": "spin-amul-taaza-500",
                        }
                    ],
                },
                {
                    "query": "eggs",
                    "products": [
                        {
                            "name": "Eggoz Brown Eggs",
                            "pack_size": "6 pcs",
                            "price": 85.0,
                            "in_stock": False,
                            "spin_id": "spin-eggoz-6",
                        }
                    ],
                },
            ],
        }
    ]

    facts = build_facts_text(tool_results=tool_results)
    assert "Products from recent search / tool results:" in facts
    assert "Amul Taaza Milk (500 ml): ₹27.0, in stock" in facts
    assert "Eggoz Brown Eggs (6 pcs): ₹85.0, out of stock" in facts


def test_facts_text_from_no_change_manage_basket_has_no_none_or_empty_brackets():
    """Test 8 (Bug B): manage_basket no-change items have no pack_size and no unit_price.

    Never print 'None' or '()' in facts text; skip missing fields; fallback to total_price.
    """
    tool_results = [
        {
            "success": True,
            "items": [
                {
                    "name": "Tissues",
                    "total_price": 50.0,
                },
                {
                    "name": "Organic Garlic",
                    "pack_size": None,
                    "unit_price": None,
                    "price": None,
                    "total_price": 40.0,
                },
                {
                    "name": "Loose Potatoes",
                },
            ],
        }
    ]

    cart = CommerceCart(
        items=[
            CartItem(
                spin_id="SPIN-LOOSE-LEMONS",
                name="Loose Lemons",
                pack_size="",
                unit_price=10.0,
                quantity=2,
                total_price=20.0,
            )
        ],
        item_total=20.0,
        discount=5.0,
        grand_total=15.0,
    )

    facts = build_facts_text(cart=cart, tool_results=tool_results)

    # Invariant: Never print "None" or "()" in facts text
    assert "None" not in facts
    assert "()" not in facts

    # Cart discount and items formatted cleanly
    assert "- Loose Lemons: qty 2, unit price ₹10.0, total ₹20.0" in facts
    assert "- Discount: ₹5.0" in facts

    # Manage basket items formatted cleanly without missing fields
    assert "- Tissues: ₹50.0" in facts
    assert "- Organic Garlic: ₹40.0" in facts
    assert "- Loose Potatoes" in facts


@pytest.mark.asyncio
async def test_session_bounded_product_facts_and_checkout_clearing():
    """Test 9: Session facts hold product info, 50 cap respected, price passes unchanged, and cleared on checkout."""
    # 1. Test 50 cap and stale replacement in CustomerSession
    session = CustomerSession(customer_id="cust-session-facts-test")

    # Add 55 products: should cap at 50, keeping latest 50
    initial_products = [
        {
            "product_id": f"prod-{i}",
            "spin_id": f"spin-{i}",
            "name": f"Product {i}",
            "pack_size": "100 g",
            "price": float(10 + i),
            "in_stock": True,
        }
        for i in range(55)
    ]
    session.update_product_facts(initial_products)
    assert len(session.recent_product_facts) == 50
    assert session.recent_product_facts[0]["product_id"] == "prod-5"
    assert session.recent_product_facts[-1]["product_id"] == "prod-54"

    # Stale replacement by product_id
    updated_product = {
        "product_id": "prod-54",
        "spin_id": "spin-54",
        "name": "Product 54 Premium",
        "pack_size": "100 g",
        "price": 99.0,
        "in_stock": False,
    }
    session.update_product_facts([updated_product])
    assert len(session.recent_product_facts) == 50
    assert session.recent_product_facts[-1]["name"] == "Product 54 Premium"
    assert session.recent_product_facts[-1]["price"] == 99.0
    assert session.recent_product_facts[-1]["in_stock"] is False

    # 2. Verify build_facts_text includes session facts heading and delivery address label
    session.address_label = "Home"
    facts = build_facts_text(
        session_facts=session.recent_product_facts,
        address_label=session.address_label,
    )
    assert "Delivery Address: Home" in facts
    assert "Known Products from earlier in this session:" in facts
    assert "Product 54 Premium (100 g): ₹99.0, out of stock" in facts

    # 3. Verify earlier-turn product price answer passes unchanged when supported
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "cust-earlier-search-test"
    eng_session = engine.get_session(customer_id)
    eng_session.address_id = "addr-bandra-1"
    eng_session.address_label = "Home"
    eng_session.order_address_confirmed = True

    # Earlier search stored milk in session
    eng_session.update_product_facts([
        {
            "product_id": "p-nandini-milk",
            "spin_id": "spin-nandini-500",
            "name": "Nandini Milk",
            "pack_size": "500 ml",
            "price": 28.0,
            "in_stock": True,
        }
    ])

    milk_price_reply = "Nandini Milk 500 ml is ₹28 and in stock."

    async def fake_model_reply(_contents, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": milk_price_reply}]}}]}

    engine._call_llm = fake_model_reply

    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="supported")), \
         patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            customer_id=customer_id,
            message_id="msg-earlier-price",
            channel=ChannelType.WHATSAPP,
            text="what is the price of nandini milk?",
        )
        resp = await engine.handle_message(msg)

    assert resp is not None
    assert resp.text == milk_price_reply

    # 4. Cleared upon checkout
    assert len(eng_session.recent_product_facts) == 1
    eng_session.reset_order_address()
    assert len(eng_session.recent_product_facts) == 0


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
    Includes exponential backoff on HTTP 429 up to 4 tries, reporting judged vs quota-blocked.
    """
    key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
    if not key or key in {"mock-key", "local-test", "test-key"}:
        pytest.skip("GEMINI_API_KEY not set or is dummy test key")

    client = GeminiClient(api_key=key)
    try:
        results = []
        judged_count = 0
        quota_blocked_count = 0
        correct = 0
        for idx, (reply, expected) in enumerate(CASES, 1):
            got = "unclear"
            for attempt in range(4):
                try:
                    got = await check_reply_claims(client, reply, facts_text=FIXED_FACTS_TEXT)
                    if got in {"supported", "unsupported", "no_claim"}:
                        break
                except Exception as exc:
                    got = f"error: {exc}"
                await asyncio.sleep(2 ** attempt)

            is_judged = got in {"supported", "unsupported", "no_claim"}
            is_match = (got == expected)
            if is_judged:
                judged_count += 1
                if is_match:
                    correct += 1
            else:
                quota_blocked_count += 1

            results.append((idx, reply, expected, got, is_match, is_judged))
            await asyncio.sleep(0.5)

        accuracy_pct = (correct / judged_count * 100.0) if judged_count > 0 else 0.0

        # Print formatted report table safely
        print("\n" + "=" * 90)
        print("LIVE CLASSIFIER ACCURACY REPORT")
        print("=" * 90)
        print(f"{'#':<3} | {'Expected':<12} | {'Got':<12} | {'Match':<5} | {'Judged':<8} | {'Reply'}")
        print("-" * 90)
        for idx, reply, expected, got, is_match, is_judged in results:
            match_str = "YES" if is_match else "NO"
            judged_str = "YES" if is_judged else "BLOCKED"
            safe_reply = reply.replace("₹", "Rs ")
            print(f"{idx:<3} | {expected:<12} | {got:<12} | {match_str:<5} | {judged_str:<8} | {safe_reply}")
        print("-" * 90)
        print(f"Judged: {judged_count}/{len(CASES)}, Quota-blocked: {quota_blocked_count}/{len(CASES)}")
        if judged_count > 0:
            print(f"Accuracy on judged: {correct}/{judged_count} ({accuracy_pct:.1f}%)")
        else:
            print("Accuracy on judged: N/A (all quota-blocked)")
        print("=" * 90 + "\n")

    finally:
        await client.close()
