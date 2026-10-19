"""Slice G Tests: Item Drop Guard with Mock Guard Client.

Verifies:
1. Dropped item named and no Confirm button.
2. All items accounted for gives no change (confirmable basket).
3. Guard failure continues with a log and shows full basket.
4. No extra guard call on non-shopping messages.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
import pytest

from backend.agent.engine import GroceryAgentEngine
from backend.channels.models import NormalizedIncomingMessage
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter


class MockGeminiClient:
    """Mock Gemini client for item drop guard testing."""

    def __init__(self, guard_response: Optional[dict[str, Any]] = None, should_fail: bool = False):
        self.api_key = "mock-key"
        self.guard_response = guard_response or {}
        self.should_fail = should_fail
        self.guard_call_count = 0
        self.fail_count = 0

    async def generate_structured_with_reason(self, model: str, prompt: str, response_schema: dict[str, Any]):
        props = response_schema.get("properties", {}) if isinstance(response_schema, dict) else {}
        if "missing_items" in props:
            self.guard_call_count += 1
            if self.should_fail:
                self.fail_count += 1
                raise RuntimeError("Mock guard API timeout")
            return self.guard_response, None
        if "verdict" in props:
            return {"verdict": "no_claim"}, None
        return {"action": "pick", "candidate_id": "1", "reason": "mock pick"}, None

    async def generate_structured(self, model: str, prompt: str, response_schema: dict[str, Any]):
        res, _ = await self.generate_structured_with_reason(model, prompt, response_schema)
        return res

    async def generate_content(self, *args, **kwargs):
        return None

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_mock_item_drop_guard_dropped_item_named_and_no_confirm():
    """Verify that a dropped item is named to the customer and no Confirm button is emitted."""
    commerce = MockCommerceAdapter()
    gemini = MockGeminiClient(guard_response={"missing_items": ["bread"]})
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    engine.gemini = gemini
    engine.tools.gemini_client = gemini

    # Model adds only milk, dropping bread
    async def model_boundary(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": "milk"}]},
        }}]}}]}

    engine._call_llm = model_boundary

    customer_id = "test-cust-g1"
    session = engine.get_session(customer_id)
    session.set_address("addr-bandra-1", "Home", confirmed=True)

    msg = NormalizedIncomingMessage(
        message_id="wamid.g1",
        sender_id=customer_id,
        channel="whatsapp",
        text="Add milk and bread",
        customer_id=customer_id,
    )
    reply = await engine.handle_message(msg)
    assert gemini.guard_call_count == 1
    assert "bread" in reply.text.casefold()
    assert not any(action.id == "confirm_order" for action in reply.interactive_actions)
    assert reply.conversation_state == "NEEDS_DECISION"
    await engine.close()


@pytest.mark.asyncio
async def test_mock_item_drop_guard_all_items_accounted_gives_no_change():
    """Verify that when all items are accounted for, no dropped notice is emitted and normal confirm appears."""
    commerce = MockCommerceAdapter()
    gemini = MockGeminiClient(guard_response={"missing_items": []})
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    engine.gemini = gemini
    engine.tools.gemini_client = gemini

    # Model adds milk
    async def model_boundary(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": "milk"}]},
        }}]}}]}

    engine._call_llm = model_boundary

    customer_id = "test-cust-g2"
    session = engine.get_session(customer_id)
    session.set_address("addr-bandra-1", "Home", confirmed=True)

    msg = NormalizedIncomingMessage(
        message_id="wamid.g2",
        sender_id=customer_id,
        channel="whatsapp",
        text="Add milk",
        customer_id=customer_id,
    )
    reply = await engine.handle_message(msg)
    assert gemini.guard_call_count == 1
    assert any(action.id == "confirm_order" or action.id.startswith("confirm_order:") for action in reply.interactive_actions)
    assert reply.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    await engine.close()


@pytest.mark.asyncio
async def test_mock_item_drop_guard_failure_continues_with_log(caplog):
    """Verify that when the guard fails after retry, a warning is logged and turn continues normally."""
    commerce = MockCommerceAdapter()
    gemini = MockGeminiClient(should_fail=True)
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    engine.gemini = gemini
    engine.tools.gemini_client = gemini

    async def model_boundary(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": "milk"}]},
        }}]}}]}

    engine._call_llm = model_boundary

    customer_id = "test-cust-g3"
    session = engine.get_session(customer_id)
    session.set_address("addr-bandra-1", "Home", confirmed=True)

    msg = NormalizedIncomingMessage(
        message_id="wamid.g3",
        sender_id=customer_id,
        channel="whatsapp",
        text="Add milk",
        customer_id=customer_id,
    )
    with caplog.at_level(logging.WARNING):
        reply = await engine.handle_message(msg)

    # Retry happened: initial call + 1 retry = 2 calls
    assert gemini.fail_count == 2
    # Warning logged
    assert any("Item drop guard call failed on retry" in record.message for record in caplog.records)
    # Turn completed normally
    assert any(action.id == "confirm_order" or action.id.startswith("confirm_order:") for action in reply.interactive_actions)
    assert reply.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    await engine.close()


@pytest.mark.asyncio
async def test_mock_item_drop_guard_no_extra_call_on_non_shopping_messages():
    """Verify that non-shopping messages with no basket step make zero calls to the guard."""
    commerce = MockCommerceAdapter()
    gemini = MockGeminiClient(guard_response={"missing_items": []})
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    engine.gemini = gemini
    engine.tools.gemini_client = gemini

    # Model replies with text (non-shopping)
    async def model_boundary(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Hello! How can I help you today?"}]}}]}

    engine._call_llm = model_boundary

    customer_id = "test-cust-g4"
    session = engine.get_session(customer_id)
    session.set_address("addr-bandra-1", "Home", confirmed=True)

    msg = NormalizedIncomingMessage(
        message_id="wamid.g4",
        sender_id=customer_id,
        channel="whatsapp",
        text="Hi",
        customer_id=customer_id,
    )
    reply = await engine.handle_message(msg)
    # Zero guard calls on non-shopping turn
    assert gemini.guard_call_count == 0
    assert "hello" in reply.text.casefold()
    await engine.close()


@pytest.mark.asyncio
async def test_pick_reason_appears_in_customer_reply():
    """Verify that the product pick reason is displayed one line per picked item with name, size, price."""
    commerce = MockCommerceAdapter()
    reason_text = "cheapest 1L toned milk"

    class PickWithReasonClient(MockGeminiClient):
        async def generate_structured_with_reason(self, model: str, prompt: str, response_schema: dict[str, Any]):
            props = response_schema.get("properties", {}) if isinstance(response_schema, dict) else {}
            if "missing_items" in props:
                return {"missing_items": []}, None
            if "verdict" in props:
                return {"verdict": "no_claim"}, None
            return {"action": "pick", "candidate_id": "1", "reason": reason_text}, None

    gemini = PickWithReasonClient()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    engine.gemini = gemini
    engine.tools.gemini_client = gemini

    async def model_boundary(_history, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "manage_basket", "args": {"add": [{"query": "milk"}]},
        }}]}}]}

    engine._call_llm = model_boundary

    customer_id = "test-cust-reason"
    session = engine.get_session(customer_id)
    session.set_address("addr-bandra-1", "Home", confirmed=True)

    msg = NormalizedIncomingMessage(
        message_id="wamid.reason-test",
        sender_id=customer_id,
        channel="whatsapp",
        text="Add milk",
        customer_id=customer_id,
    )
    reply = await engine.handle_message(msg)
    assert reason_text in reply.text, repr(reply.text)
    # Check that item line contains name, size, price, and reason on one line
    matching_lines = [line for line in reply.text.splitlines() if reason_text in line]
    assert len(matching_lines) == 1, repr(reply.text)
    item_line = matching_lines[0]
    assert "milk" in item_line.casefold()
    assert "1 l" in item_line.casefold() or "1l" in item_line.casefold()
    assert "₹" in item_line
    assert item_line.strip().startswith("•")
    assert reply.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    await engine.close()
