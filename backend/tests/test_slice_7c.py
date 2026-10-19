"""Tests for Slice 7c: step cap 8, 60s turn cap, resume from saved request, and dead loop code cleanup."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from backend.agent import react_coordinator
from backend.agent.engine import GroceryAgentEngine
from backend.channels.models import NormalizedIncomingMessage
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter


def _setup_test_engine(customer_id: str = "919876543210"):
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="mock-key")
    session = engine.get_session(customer_id)
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"
    session.order_address_confirmed = True
    engine._read_budget_cap = AsyncMock(return_value=None)

    async def mock_variant_picker(*args, **kwargs):
        return {"action": "pick", "candidate_id": "1", "reason": "mock: test_slice_7c pick"}, None

    engine.gemini.generate_structured_with_reason = mock_variant_picker
    return engine, session, commerce


@pytest.mark.asyncio
async def test_eight_tool_steps_complete_and_step_nine_triggers_step_limit():
    engine, session, _ = _setup_test_engine()
    customer_id = "919876543210"

    # Part A: Exactly 8 tool steps complete successfully
    call_count_a = 0

    async def model_reply_8_steps(_history, **_kwargs):
        nonlocal call_count_a
        call_count_a += 1
        if call_count_a < 8:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "search_products", "args": {"query": f"item-{call_count_a}"},
            }}]}}]}
        elif call_count_a == 8:
            return {"candidates": [{"content": {"parts": [{"functionCall": {
                "name": "manage_basket", "args": {"add": [{"query": "milk"}]},
            }}]}}]}
        return None

    engine._call_llm = model_reply_8_steps
    msg_a = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-8-steps",
        text="Add 8 items",
    )
    resp_a = await engine.handle_message(msg_a)

    assert call_count_a == 8
    assert resp_a.conversation_state == "AWAITING_CHECKOUT_CONFIRMATION"
    assert "maximum processing steps" not in resp_a.text.casefold()
    assert session.pending_request_text is None

    # Part B: Step 9 triggers the step-limit reply and saves pending_request_text
    call_count_b = 0

    async def model_reply_endless_search(_history, **_kwargs):
        nonlocal call_count_b
        call_count_b += 1
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "search_products", "args": {"query": f"item-{call_count_b}"},
        }}]}}]}

    engine._call_llm = model_reply_endless_search
    msg_b = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-9-steps",
        text="Search 9 times",
    )
    resp_b = await engine.handle_message(msg_b)

    assert call_count_b == 8  # Only 8 tool calls executed before step 9 hit the limit
    assert resp_b.conversation_state == "NEEDS_DECISION"
    assert "maximum processing steps" in resp_b.text.casefold()
    assert session.pending_request_text == "Search 9 times"


@pytest.mark.asyncio
async def test_time_cap_exceeded_triggers_step_limit_and_saves_request(monkeypatch):
    engine, session, _ = _setup_test_engine()
    customer_id = "919876543210"

    current_simulated_time = 100.0

    def mock_now():
        return current_simulated_time

    monkeypatch.setattr(react_coordinator, "_now", mock_now)

    call_count = 0

    async def model_reply_with_time_jump(_history, **_kwargs):
        nonlocal call_count, current_simulated_time
        call_count += 1
        # After step 1 completes, jump past the 60s TURN_TIME_LIMIT_SECONDS
        current_simulated_time += 65.0
        return {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "search_products", "args": {"query": "slow item"},
        }}]}}]}

    engine._call_llm = model_reply_with_time_jump
    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-time-cap",
        text="Slow search",
    )
    resp = await engine.handle_message(msg)

    assert call_count == 1  # Only 1 step ran before time limit fired on the next step
    assert resp.conversation_state == "NEEDS_DECISION"
    assert "maximum processing steps" in resp.text.casefold()
    assert session.pending_request_text == "Slow search"


@pytest.mark.asyncio
async def test_resume_from_saved_request_note_and_cleared_on_success():
    engine, session, _ = _setup_test_engine()
    customer_id = "919876543210"

    session.pending_request_text = "Add 2 packets of milk and brown bread"
    captured_contents = None

    async def model_resumes(contents, **_kwargs):
        nonlocal captured_contents
        captured_contents = contents
        return {"candidates": [{"content": {"parts": [{"text": "Resumed and added milk and bread!"}]}}]}

    engine._call_llm = model_resumes
    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-continue",
        text="continue",
    )
    with patch("backend.agent.react_coordinator.check_reply_claims", new=AsyncMock(return_value="no_claim")):
        resp = await engine.handle_message(msg)

    assert resp.conversation_state == "READY"
    assert "Resumed and added" in resp.text
    # Note was passed in model input
    expected_note = (
        "Saved unfinished request from earlier: Add 2 packets of milk and brown bread. "
        "If the customer's new message asks to continue or retry, resume it. Otherwise ignore this note."
    )
    assert captured_contents is not None
    assert any(expected_note in str(part) for entry in captured_contents for part in entry.get("parts", []))
    # Stored history does NOT contain the note
    assert not any(expected_note in str(part) for entry in session.history for part in entry.get("parts", []))
    # After successful turn, pending_request_text is cleared
    assert session.pending_request_text is None


@pytest.mark.asyncio
async def test_customer_with_no_saved_request_gets_no_note():
    engine, session, _ = _setup_test_engine()
    customer_id = "919876543210"
    session.pending_request_text = None

    captured_contents = None

    async def model_simple(contents, **_kwargs):
        nonlocal captured_contents
        captured_contents = contents
        return {"candidates": [{"content": {"parts": [{"text": "Hello! How can I help?"}]}}]}

    engine._call_llm = model_simple
    msg = NormalizedIncomingMessage(
        sender_id=customer_id,
        message_id="msg-hello",
        text="Hello",
    )
    resp = await engine.handle_message(msg)

    assert resp.conversation_state == "READY"
    assert captured_contents is not None
    assert not any("Saved unfinished request from earlier" in str(part) for entry in captured_contents for part in entry.get("parts", []))
