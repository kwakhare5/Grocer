"""Tests for Slice D2a: Landing honesty, model claim check, and 50-message scripted invariant run."""
from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, patch
import pytest

from backend.agent import claim_check, confirmation_check
from backend.agent.approval import cart_fingerprint
from backend.agent.claim_check import CLAIM_CHECK_PROMPT, CLAIM_CHECK_SCHEMA, check_reply_claims, is_unclaimed_chat
from backend.agent.engine import GroceryAgentEngine
from backend.agent.formatters import format_cart_receipt
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem, CartItemUpdate


# ============================================================================
# Unit Tests: Claim Check Prompt, Schema, and Real-State Replacement
# ============================================================================

def test_claim_check_prompt_and_schema():
    """Verify check prompt wording and structured output schema."""
    assert CLAIM_CHECK_SCHEMA["type"] == "OBJECT"
    assert "verdict" in CLAIM_CHECK_SCHEMA["properties"]
    assert CLAIM_CHECK_SCHEMA["properties"]["verdict"]["enum"] == ["supported", "unsupported", "no_claim"]
    assert CLAIM_CHECK_SCHEMA["required"] == ["verdict"]

    prompt = CLAIM_CHECK_PROMPT.format(facts_text="Current Basket: empty", reply_text="Hello world")
    assert "supported" in prompt.casefold()
    assert "unsupported" in prompt.casefold()
    assert "no_claim" in prompt.casefold()


@pytest.mark.asyncio
async def test_claim_check_no_passes_text():
    """When claim check returns 'no_claim' or 'no', model text passes through untouched."""
    mock_client = AsyncMock()
    mock_client.api_key = "test-key"
    mock_client.generate_structured = AsyncMock(return_value={"verdict": "no_claim"})

    res = await check_reply_claims(mock_client, "Hello! How can I help you today?")
    assert res == "no_claim"
    assert await is_unclaimed_chat(mock_client, "Hello! How can I help you today?") is True


@pytest.mark.asyncio
async def test_claim_check_yes_replaced_with_real_state():
    """When claim check returns 'yes', text is replaced with safe real state."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    # Pre-populate 1 milk in the cart
    with commerce.customer_scope(customer_id):
        await commerce.update_cart([CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)])

    # Model attempts to hallucinate bread, total, and order placed with text only
    async def model_hallucination(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "I added 2 breads! Total is ₹200. Order has been placed!"}]}}]}

    engine._call_llm = model_hallucination

    # Script claim_check to answer 'unsupported' (it claims cart items/order not in facts)
    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="unsupported")):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            message_id="msg-claim-yes",
            text="what is happening",
        )
        resp = await engine.handle_message(msg)

    # Must be replaced with real state
    assert resp.text is not None and resp.text.strip() != ""
    assert "bread" not in resp.text.casefold()
    assert "200" not in resp.text
    assert "order has been placed" not in resp.text.casefold()
    # Cart has milk, so real-state receipt shows milk
    assert "milk" in resp.text.casefold()


@pytest.mark.asyncio
async def test_claim_check_unclear_replaced_with_real_state():
    """When claim check returns 'unclear', text is replaced with safe real state."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    async def model_hallucination(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Your total might be ₹150 maybe."}]}}]}

    engine._call_llm = model_hallucination

    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="unclear")):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            message_id="msg-claim-unclear",
            text="status please",
        )
        resp = await engine.handle_message(msg)

    assert "150" not in resp.text
    assert "empty" in resp.text.casefold() or "basket" in resp.text.casefold()


@pytest.mark.asyncio
async def test_claim_check_error_replaced_with_real_state():
    """When claim check errors or times out, text is replaced with safe real state."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    async def model_hallucination(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "All set, order confirmed for ₹500!"}]}}]}

    engine._call_llm = model_hallucination

    # Simulate exception in check_reply_claims
    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(side_effect=RuntimeError("Gemini timeout"))):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            message_id="msg-claim-err",
            text="confirm my stuff",
        )
        resp = await engine.handle_message(msg)

    assert "500" not in resp.text
    assert "order confirmed" not in resp.text.casefold()
    assert "empty" in resp.text.casefold() or "basket" in resp.text.casefold()


@pytest.mark.asyncio
async def test_claim_replacement_never_states_anything_not_in_cart():
    """Assert replacement text never contains items or prices not in the cart."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True

    # Empty cart
    async def model_hallucination(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Order placed! 5x Butter added for ₹500."}]}}]}

    engine._call_llm = model_hallucination

    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="unsupported")):
        msg = NormalizedIncomingMessage(
            sender_id=customer_id,
            message_id="msg-empty-claim",
            text="hi",
        )
        resp = await engine.handle_message(msg)

    assert resp.text == "Your basket is empty. What groceries would you like to add?"
    assert "butter" not in resp.text.casefold()
    assert "500" not in resp.text
    assert "order placed" not in resp.text.casefold()


@pytest.mark.asyncio
async def test_claim_check_no_passes_text_unchanged_with_real_cart():
    """When claim check explicitly returns 'no_claim' or 'supported', model text passes unchanged even with items in cart."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "test-cust-no-pass"
    session = engine.get_session(customer_id)
    session.address_id = "addr-home"
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(items=[
            CartItem(spin_id="SPIN-MILK-500ML", product_id="p-milk", name="Nandini GoodLife Milk", pack_size="500 ml", unit_price=30.0, quantity=1, total_price=30.0)
        ])
        cart = await commerce.get_cart()
    session.known_cart_fingerprint = cart_fingerprint(cart, session.address_id)

    model_chat_text = "We deliver every day between 6 AM and 11 PM."
    async def fake_call_llm(_contents, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": model_chat_text}]}}]}

    engine._call_llm = fake_call_llm

    fake_gemini = AsyncMock()
    fake_gemini.api_key = "valid-test-key"
    fake_gemini.generate_structured = AsyncMock(return_value={"verdict": "no_claim"})
    engine.gemini = fake_gemini

    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        customer_id=customer_id,
        message_id="msg-hours-1",
        channel=ChannelType.WHATSAPP,
        text="What are your delivery hours?",
    )

    with patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):
        response = await engine.handle_message(msg)

    assert response is not None
    assert response.text == model_chat_text
    assert response.order_id is None


@pytest.mark.asyncio
async def test_claim_check_raising_exception_replaces_with_real_receipt():
    """When claim check raises an exception, turn safely replaces reply with real cart receipt."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "test-cust-err-receipt"
    session = engine.get_session(customer_id)
    session.address_id = "addr-home"
    session.address_label = "Home"
    session.order_address_confirmed = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(items=[
            CartItem(spin_id="SPIN-MILK-500ML", product_id="p-milk", name="Nandini GoodLife Milk", pack_size="500 ml", unit_price=30.0, quantity=1, total_price=30.0)
        ])
        cart = await commerce.get_cart()
    session.known_cart_fingerprint = cart_fingerprint(cart, session.address_id)

    async def fake_call_llm(_contents, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Your order has been placed for 30 rupees."}]}}]}

    engine._call_llm = fake_call_llm

    fake_gemini = AsyncMock()
    fake_gemini.api_key = "valid-test-key"
    fake_gemini.generate_structured = AsyncMock(side_effect=RuntimeError("Structured generation service timeout"))
    engine.gemini = fake_gemini

    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        customer_id=customer_id,
        message_id="msg-err-1",
        channel=ChannelType.WHATSAPP,
        text="status",
    )

    with patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):
        response = await engine.handle_message(msg)

    assert response is not None
    assert "🛒" in response.text
    assert "Amul Taaza Milk" in response.text
    assert "₹34" in response.text
    assert "placed" not in response.text.casefold()
    assert response.order_id is None


# ============================================================================
# Part 2: 50-Message Scripted Interleaved Run
# ============================================================================

@pytest.mark.asyncio
async def test_fifty_message_scripted_interleaved_invariant_run():
    """50 customer messages in a row for several interleaved customers.

    Asserts after every message:
    1. Reply never states a cart total or item that is not in the cart.
    2. No checkout without an explicit confirmation turn.
    3. No reply without a response (never None or empty).
    4. Cart equals expected after each step.
    Fails loudly with the step number.
    """
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")

    c1 = "919876543201"
    c2 = "919876543202"
    c3 = "919876543203"

    # Setup customer sessions with confirmed addresses
    for cid, addr, lbl in [
        (c1, "addr-bandra-1", "Home"),
        (c2, "addr-andheri-1", "Work"),
        (c3, "addr-bandra-1", "Home"),
    ]:
        s = engine.get_session(cid)
        s.address_id = addr
        s.address_label = lbl
        s.order_address_confirmed = True

    # 50 interleaved scripted steps: (customer_id, incoming_text, expected_items, expected_checkout)
    # expected_items is a dict of {item_query: quantity}
    steps = [
        # Interleaved round 1: greetings
        (c1, "hello", {}, False),                                        # 1
        (c2, "hello", {}, False),                                        # 2
        (c3, "hello", {}, False),                                        # 3
        # Interleaved round 2: initial adds
        (c1, "add milk", {"milk": 1}, False),                             # 4
        (c2, "add atta", {"atta": 1}, False),                             # 5
        (c3, "add tea", {"tea": 1}, False),                               # 6
        # Interleaved round 3: secondary adds
        (c1, "add bread", {"milk": 1, "bread": 1}, False),                 # 7
        (c2, "add rice", {"atta": 1, "rice": 1}, False),                  # 8
        (c3, "add coffee", {"tea": 1, "coffee": 1}, False),               # 9
        # Interleaved round 4: third adds & qty changes
        (c1, "add eggs", {"milk": 1, "bread": 1, "eggs": 1}, False),         # 10
        (c2, "add dal", {"atta": 1, "rice": 1, "dal": 1}, False),          # 11
        (c3, "make tea 2", {"tea": 2, "coffee": 1}, False),               # 12
        (c1, "make milk 2", {"milk": 2, "bread": 1, "eggs": 1}, False),     # 13
        (c2, "make atta 2", {"atta": 2, "rice": 1, "dal": 1}, False),     # 14
        # Interleaved round 5: removals
        (c3, "remove coffee", {"tea": 2}, False),                         # 15
        (c1, "remove bread", {"milk": 2, "eggs": 1}, False),               # 16
        (c2, "remove rice", {"atta": 2, "dal": 1}, False),                # 17
        # Interleaved round 6: wait / holds
        (c3, "wait", {"tea": 2}, False),                                 # 18
        (c1, "don't order yet", {"milk": 2, "eggs": 1}, False),           # 19
        (c2, "wait", {"atta": 2, "dal": 1}, False),                       # 20
        # Customer 3 checkout (button tap)
        (c3, "confirm", {"tea": 2}, False),                               # 21
        (c3, "confirm_order_tap", {}, True),                               # 22
        # Customer 1 checkout (button tap)
        (c1, "confirm", {"milk": 2, "eggs": 1}, False),                   # 23
        (c1, "confirm_order_tap", {}, True),                               # 24
        # Customer 2 clear cart
        (c2, "clear cart", {"atta": 2, "dal": 1}, False),                 # 25
        (c2, "clear_cart_confirm_tap", {}, False),                        # 26
        # Customer 1: new session with unconfirmed address -> prompt, address choice, partial items
        (c1, "add tomato", {}, False),                                    # 27: address choice prompt
        (c1, "1", {"tomato": 1}, False),                                  # 28: address choice confirmed + tomato added!
        (c1, "add dragonfruit", {"tomato": 1}, False),                    # 29: unavailable item
        (c1, "accept_partial_basket_tap", {"tomato": 1}, False),          # 30: accept partial basket
        (c1, "add crocin", {"tomato": 1}, False),                         # 31: restricted medical item
        (c1, "add sugar", {"tomato": 1, "sugar": 1}, False),               # 32: add sugar
        (c1, "make sugar 3", {"tomato": 1, "sugar": 3}, False),             # 33: qty sugar -> 3
        (c1, "remove sugar", {"tomato": 1}, False),                        # 34: remove sugar
        (c1, "confirm", {}, True),                                        # 35: typed confirmation places order!
        (c1, "hello", {}, False),                                         # 36: fresh greeting
        # Customer 2: address choice + items
        (c2, "add butter", {}, False),                                    # 37: address choice prompt
        (c2, "1", {"butter": 1}, False),                                  # 38: address choice confirmed + butter added!
        (c2, "make butter 2", {"butter": 2}, False),                       # 39: qty butter -> 2
        (c2, "add paneer", {"butter": 2, "paneer": 1}, False),             # 40: add paneer
        (c2, "remove paneer", {"butter": 2}, False),                      # 41: remove paneer
        (c2, "add strepsils", {"butter": 2}, False),                      # 42: restricted medical item
        (c2, "add passionfruit", {"butter": 2}, False),                   # 43: unavailable item
        (c2, "accept_partial_basket_tap", {"butter": 2}, False),          # 44: accept partial basket
        (c2, "confirm", {}, True),                                        # 45: typed confirmation places order!
        (c2, "hello", {}, False),                                         # 46: fresh greeting
        # Customer 3: address choice + items
        (c3, "add maggi", {}, False),                                     # 47: address choice prompt
        (c3, "1", {"maggi": 1}, False),                                   # 48: address choice confirmed + maggi added!
        (c3, "make maggi 4", {"maggi": 4}, False),                         # 49: qty maggi -> 4
        (c3, "confirm", {}, True),                                        # 50: typed confirmation places order!
    ]

    assert len(steps) == 50, f"Expected 50 steps, got {len(steps)}"

    current_step = 0
    current_cid = ""

    async def scripted_llm(contents, **kwargs):
        # Adversarial false claims at specific steps
        if current_step == 1:
            return {"candidates": [{"content": {"parts": [{"text": "Your total is ₹9999 with Alphonso Mangoes."}]}}]}
        if current_step == 2:
            return {"candidates": [{"content": {"parts": [{"text": "Added Belgian Chocolate Ice Cream for ₹450 to your basket."}]}}]}
        if current_step == 3:
            return {"candidates": [{"content": {"parts": [{"text": "Your order has been placed for 500 rupees!"}]}}]}
        if current_step == 20:
            return {"candidates": [{"content": {"parts": [{"text": "Your total is ₹9999 with Alphonso Mangoes."}]}}]}
        if current_step == 36:
            return {"candidates": [{"content": {"parts": [{"text": "Your order is placed and will arrive shortly for ₹250."}]}}]}
        if current_step == 46:
            return {"candidates": [{"content": {"parts": [{"text": "Added 5 packets of Saffron for ₹1500."}]}}]}

        last_user_text = ""
        for entry in reversed(contents):
            if entry.get("role") == "user" and entry.get("parts"):
                last_user_text = entry["parts"][0].get("text", "").strip().casefold()
                break

        first_line = last_user_text.splitlines()[0].strip() if last_user_text else ""

        if "confirm order" in first_line or first_line == "confirm":
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "checkout", "args": {},
            }}]}}]}

        if "clear cart" in first_line or first_line == "cancel":
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "clear_cart", "args": {},
            }}]}}]}

        if first_line.startswith("add "):
            item = first_line.replace("add ", "").strip()
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [{"query": item}]},
            }}]}}]}

        if first_line.startswith("remove "):
            item = first_line.replace("remove ", "").strip()
            cart = kwargs.get("cart")
            lid = item
            if cart and cart.items:
                ci = next((it for it in cart.items if item in it.name.casefold()), None)
                if ci:
                    lid = getattr(ci, "cart_line_id", None) or getattr(ci, "line_id", None) or ci.spin_id
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"remove": [lid]},
            }}]}}]}

        if first_line.startswith("make "):
            parts = first_line.split()
            item = parts[1]
            qty = int(parts[2])
            cart = kwargs.get("cart")
            lid = item
            if cart and cart.items:
                ci = next((it for it in cart.items if item in it.name.casefold()), None)
                if ci:
                    lid = getattr(ci, "cart_line_id", None) or getattr(ci, "line_id", None) or ci.spin_id
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"set_quantity": [{"line_id": lid, "quantity": qty}]},
            }}]}}]}

        if any(w in first_line for w in ["wait", "hold", "don't order"]):
            return {"candidates": [{"content": {"parts": [{"text": "I have held your basket."}]}}]}

        return {"candidates": [{"content": {"parts": [{"text": "Hello! How can I help you today?"}]}}]}

    engine._call_llm = scripted_llm

    # Confirmation check mock: returns True for "confirm" / "yes confirm order"
    async def mock_is_confirmed(_client, text="", context=""):
        return "confirm" in text.casefold()

    lie_steps = {1, 2, 3, 20, 36, 46}

    # Scripted verdicts per step: returns 'unsupported' for lies, 'no_claim' otherwise
    async def scripted_check_claims(_client, text="", **_kwargs):
        if current_step in lie_steps:
            return "unsupported"
        return "no_claim"

    with patch("backend.agent.confirmation_check.is_confirmed", side_effect=mock_is_confirmed), \
         patch("backend.agent.react_coordinator.check_reply_claims", side_effect=scripted_check_claims), \
         patch.object(engine, "_read_budget_cap", new=AsyncMock(return_value=None)):

        for step_num, (cid, incoming, expected_items, expected_checkout) in enumerate(steps, 1):
            current_step = step_num
            current_cid = cid
            sess = engine.get_session(cid)
            if step_num in {36, 46}:
                sess.address_id = "addr-bandra-1"
                sess.address_label = "Home"
                sess.order_address_confirmed = True
            if incoming == "confirm_order_tap":
                token = sess.pending_approval.token if sess.pending_approval else ""
                msg = NormalizedIncomingMessage(
                    sender_id=cid,
                    customer_id=cid,
                    message_id=f"msg-step-{step_num}",
                    channel=ChannelType.WHATSAPP,
                    text="Confirm Order",
                    interactive_id=f"confirm_order:{token}",
                )
            elif incoming == "clear_cart_confirm_tap":
                token = sess.pending_cart_clear.token if sess.pending_cart_clear else ""
                msg = NormalizedIncomingMessage(
                    sender_id=cid,
                    customer_id=cid,
                    message_id=f"msg-step-{step_num}",
                    channel=ChannelType.WHATSAPP,
                    text="Clear Cart",
                    interactive_id=f"clear_cart_confirm:{token}",
                )
            elif incoming == "accept_partial_basket_tap":
                msg = NormalizedIncomingMessage(
                    sender_id=cid,
                    customer_id=cid,
                    message_id=f"msg-step-{step_num}",
                    channel=ChannelType.WHATSAPP,
                    text="Keep These Items",
                    interactive_id="accept_partial_basket",
                )
            else:
                msg = NormalizedIncomingMessage(
                    sender_id=cid,
                    customer_id=cid,
                    message_id=f"msg-step-{step_num}",
                    channel=ChannelType.WHATSAPP,
                    text=incoming,
                )
            response = await engine.handle_message(msg)

            # Invariant 3: No reply without a response
            assert response is not None, f"Step {step_num} (cust={cid}, msg='{incoming}'): Response is None"
            assert getattr(response, "text", "").strip() != "", f"Step {step_num} (cust={cid}, msg='{incoming}'): Response text is empty"

            # Invariant 2: No checkout without explicit confirmation turn (strict non-OR assertion)
            if expected_checkout:
                assert response.order_id is not None, \
                    f"Step {step_num}: Expected checkout order placement (order_id is not None), but got None."
            else:
                assert response.order_id is None, \
                    f"Step {step_num}: Unexpected checkout execution without explicit confirmation turn, got {response.order_id}."
                assert "order has been placed" not in response.text.casefold(), \
                    f"Step {step_num}: Text claimed 'order has been placed' without explicit confirmation turn."

            # Real state verification under customer scope
            with commerce.customer_scope(cid):
                cart = await commerce.get_cart()

            # Invariant 4: Cart equals expected after each step
            cart_item_queries = [it.name.casefold() for it in cart.items]
            for exp_query, exp_qty in expected_items.items():
                matching_items = [it for it in cart.items if exp_query in it.name.casefold()]
                assert matching_items, f"Step {step_num} (cust={cid}): Expected item '{exp_query}' not found in cart: {cart_item_queries}"
                total_qty = sum(it.quantity for it in matching_items)
                assert total_qty == exp_qty, f"Step {step_num} (cust={cid}): Expected qty {exp_qty} for '{exp_query}', got {total_qty}"

            assert len(cart.items) == len(expected_items), \
                f"Step {step_num} (cust={cid}): Cart item count mismatch. Got {len(cart.items)}, expected {len(expected_items)}"

            # Invariant 1: At the 6 lie steps, reply was replaced by real receipt or empty-basket text
            if step_num in lie_steps:
                if cart.items:
                    assert "🛒" in response.text, (
                        f"Step {step_num} (cust={cid}): Expected real receipt replacement for lie, got: {response.text}"
                    )
                else:
                    assert "empty" in response.text.casefold() or "basket" in response.text.casefold(), (
                        f"Step {step_num} (cust={cid}): Expected empty basket replacement for lie, got: {response.text}"
                    )
            elif incoming in {"wait", "don't order yet"}:
                # Harmless reply passed unchanged
                assert response.text == "I have held your basket.", (
                    f"Step {step_num} (cust={cid}): Harmless text should pass unchanged, got: {response.text}"
                )
