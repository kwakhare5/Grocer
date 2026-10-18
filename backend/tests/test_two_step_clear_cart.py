"""Regression tests for two-step clear cart (Slice 5, step 3)."""
from __future__ import annotations

import time
import pytest

from backend.agent.engine import GroceryAgentEngine
from backend.agent.tool_executor import execute_engine_tool
from backend.channels.models import NormalizedIncomingMessage
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItemUpdate


@pytest.mark.asyncio
async def test_clear_cart_tool_leaves_items_untouched_and_records_pending_clear():
    """Calling the clear_cart tool leaves the cart's items untouched and records a pending clear with a token."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    address_id = "addr-bandra-1"

    engine._customer_address[customer_id] = address_id
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=2)],
            address_id=address_id,
        )

        # Call the clear_cart tool via engine dispatcher within customer scope
        result = await execute_engine_tool(
            name="clear_cart",
            args={},
            engine=engine,
            customer_id=customer_id,
            address_id=address_id,
        )

        # 1. Returned error indicates confirmation is required
        assert result.get("success") is False
        assert result.get("error") == "CLEAR_CONFIRMATION_REQUIRED"

        # 2. Cart's items must remain untouched
        cart = await commerce.get_cart()
        assert cart is not None
        assert len(cart.items) == 1
        assert cart.items[0].quantity == 2

    # 3. Session records a pending clear with a valid token
    session = engine.get_session(customer_id)
    assert session.pending_cart_clear is not None
    assert bool(session.pending_cart_clear.token)
    assert session.pending_cart_clear.expires_at > time.time()


@pytest.mark.asyncio
async def test_clear_cart_confirm_tap_validation_and_execution():
    """A clear_cart_confirm tap with a valid token clears the cart; an expired, unknown or cart-mismatched token does not."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    address_id = "addr-bandra-1"

    engine._customer_address[customer_id] = address_id
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id=address_id,
        )
        initial_cart = await commerce.get_cart()

    session = engine.get_session(customer_id)

    # 1. Unknown token does not clear
    from backend.agent.session_manager import record_pending_cart_clear
    assert record_pending_cart_clear(session, initial_cart, address_id)
    msg_unknown = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-unknown",
        text="",
        interactive_id="clear_cart_confirm:unknown_token_value",
        timestamp=int(time.time()),
    )
    resp_unknown = await engine.handle_message(msg_unknown)
    with commerce.customer_scope(customer_id):
        cart_after_unknown = await commerce.get_cart()
    assert len(cart_after_unknown.items) == 1, "Cart must not be cleared with unknown token"
    assert "expired" in resp_unknown.text.lower() or "changed" in resp_unknown.text.lower()

    # 2. Expired token does not clear
    assert record_pending_cart_clear(session, initial_cart, address_id)
    valid_token = session.pending_cart_clear.token
    session.pending_cart_clear = session.pending_cart_clear.__class__(
        fingerprint=session.pending_cart_clear.fingerprint,
        expires_at=time.time() - 30,
        token=valid_token,
    )
    msg_expired = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-expired",
        text="",
        interactive_id=f"clear_cart_confirm:{valid_token}",
        timestamp=int(time.time()),
    )
    resp_expired = await engine.handle_message(msg_expired)
    with commerce.customer_scope(customer_id):
        cart_after_expired = await commerce.get_cart()
    assert len(cart_after_expired.items) == 1, "Cart must not be cleared with expired token"
    assert "expired" in resp_expired.text.lower() or "changed" in resp_expired.text.lower()

    # 3. Cart-mismatched token does not clear
    assert record_pending_cart_clear(session, initial_cart, address_id)
    old_token = session.pending_cart_clear.token
    # Modify the cart so the fingerprint changes
    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-BREAD-400G", sku_id="SPIN-BREAD-400G", quantity=1)],
            address_id=address_id,
        )
        changed_cart = await commerce.get_cart()
    assert len(changed_cart.items) == 1
    assert changed_cart.items[0].spin_id == "SPIN-BREAD-400G"

    msg_mismatch = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-mismatch",
        text="",
        interactive_id=f"clear_cart_confirm:{old_token}",
        timestamp=int(time.time()),
    )
    resp_mismatch = await engine.handle_message(msg_mismatch)
    with commerce.customer_scope(customer_id):
        cart_after_mismatch = await commerce.get_cart()
    assert len(cart_after_mismatch.items) == 1, "Cart must not be cleared when cart fingerprint mismatches"
    assert "expired" in resp_mismatch.text.lower() or "changed" in resp_mismatch.text.lower()

    # 4. Valid unexpired token bound to current cart clears the cart
    assert record_pending_cart_clear(session, changed_cart, address_id)
    fresh_token = session.pending_cart_clear.token
    msg_valid = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-valid",
        text="",
        interactive_id=f"clear_cart_confirm:{fresh_token}",
        timestamp=int(time.time()),
    )
    resp_valid = await engine.handle_message(msg_valid)
    with commerce.customer_scope(customer_id):
        cart_after_valid = await commerce.get_cart()
    assert len(cart_after_valid.items) == 0, "Cart must be completely cleared with valid token"
    assert "cleared" in resp_valid.text.lower() or "empty" in resp_valid.text.lower()


@pytest.mark.asyncio
async def test_typed_reset_leaves_cart_non_empty_and_produces_clear_cart_ask():
    """A typed reset phrase leaves the cart non-empty and produces the 'Clear cart?' ask."""
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    customer_id = "919876543210"
    address_id = "addr-bandra-1"

    engine._customer_address[customer_id] = address_id
    engine._customer_address_label[customer_id] = "Home"
    engine._order_address_confirmed[customer_id] = True

    with commerce.customer_scope(customer_id):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=1)],
            address_id=address_id,
        )

    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-typed-reset",
        text="clear my cart",
        timestamp=int(time.time()),
    )
    resp = await engine.handle_message(msg)

    # 1. Cart must remain non-empty
    with commerce.customer_scope(customer_id):
        cart = await commerce.get_cart()
    assert cart is not None
    assert len(cart.items) == 1, "Typed reset must not clear the cart"

    # 2. Response produces the "Clear cart?" ask with confirmation buttons
    assert resp.text is not None
    assert "clear cart?" in resp.text.lower()
    assert resp.interactive_actions is not None
    action_ids = [a.id for a in resp.interactive_actions]
    assert any(aid.startswith("clear_cart_confirm:") for aid in action_ids)
    assert any(aid == "modify_cart" for aid in action_ids)
