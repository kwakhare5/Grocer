"""Automated pytest suite for the Human Stress & Chaos Matrix.

Runs:
1. 25 Multi-Turn Persona Trajectories
2. Combinatorial Input & Typo Permutations
3. 1,000 Property-Based Invariant Fuzz Iterations
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.agent.engine import GroceryAgentEngine
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from scripts.human_stress_matrix import (
    TRAJECTORIES,
    generate_combinatorial_cases,
    verify_math_fee_conservation_invariant,
    verify_turn_boundary_invariant,
    verify_anti_amnesia_invariant,
    run_tier3_property_fuzzing,
)


@pytest.mark.live_llm
@pytest.mark.asyncio
@pytest.mark.parametrize("trajectory", TRAJECTORIES, ids=[t.trajectory_id for t in TRAJECTORIES])
async def test_multi_turn_persona_trajectory(trajectory, mock_commerce):
    """Execute each of the 25 multi-turn human personas and verify state and receipt invariants."""
    engine = GroceryAgentEngine(commerce=mock_commerce)
    customer_id = f"pytest_traj_{trajectory.trajectory_id.lower()}"
    engine._history[customer_id] = []

    if trajectory.trajectory_id == "T12":
        mock_commerce.inject_min_order_threshold(99.0)

    for turn_idx, turn in enumerate(trajectory.turns, 1):
        msg = NormalizedIncomingMessage(
            message_id=f"msg_{trajectory.trajectory_id}_t{turn_idx}",
            channel=ChannelType.WHATSAPP,
            sender_id="+919876543210",
            customer_id=customer_id,
            text=turn.user_input,
            interactive_id=turn.interactive_id,
        )

        resp = await engine.handle_message(msg)
        resp_text_low = resp.text.casefold()

        # Invariant 1: State must match expectation if specified
        if turn.expected_state:
            assert resp.conversation_state == turn.expected_state, (
                f"{trajectory.trajectory_id} Turn {turn_idx}: expected {turn.expected_state}, got {resp.conversation_state}"
            )

        # Invariant 2: Must contain expected concepts
        for kw in turn.must_contain:
            assert kw.casefold() in resp_text_low, (
                f"{trajectory.trajectory_id} Turn {turn_idx}: missing expected concept '{kw}'. Got: {resp.text[:150]}"
            )

        # Invariant 3: Must not contain forbidden terms (e.g. amnesiac greetings)
        for nkw in turn.must_not_contain:
            assert nkw.casefold() not in resp_text_low, (
                f"{trajectory.trajectory_id} Turn {turn_idx}: contained forbidden term '{nkw}'. Got: {resp.text[:150]}"
            )

        # Invariant 4: Check receipt if required
        if turn.check_receipt:
            assert ("🛒 *your basket" in resp_text_low or "🛒 your basket" in resp_text_low), (
                f"{trajectory.trajectory_id} Turn {turn_idx}: expected receipt card in output. Got: {resp.text[:150]}"
            )

        # Invariant 5: Check confirmation buttons
        if turn.check_confirmation_buttons:
            assert resp.requires_confirmation is True, (
                f"{trajectory.trajectory_id} Turn {turn_idx}: expected requires_confirmation=True"
            )
            assert len(resp.interactive_actions) >= 2, (
                f"{trajectory.trajectory_id} Turn {turn_idx}: expected interactive buttons"
            )

        # Invariant 6: Budget cap enforcement
        if turn.max_total and resp.order_total:
            assert resp.order_total <= turn.max_total * 1.05, (
                f"{trajectory.trajectory_id} Turn {turn_idx}: order total ₹{resp.order_total} > ₹{turn.max_total}"
            )

        # Invariant 7: History turn boundary sanity
        hist = engine.get_history(customer_id)
        assert verify_turn_boundary_invariant(hist), (
            f"{trajectory.trajectory_id} Turn {turn_idx}: history turn boundary corrupted"
        )


@pytest.mark.live_llm
@pytest.mark.asyncio
async def test_combinatorial_permutations_smoke(mock_commerce):
    """Run a sample of 25 combinatorial permutations verifying zero crashes and no raw JSON."""
    engine = GroceryAgentEngine(commerce=mock_commerce)
    cases = generate_combinatorial_cases(count=25)

    for i, case in enumerate(cases, 1):
        cid = f"pytest_comb_{i}"
        msg = NormalizedIncomingMessage(
            message_id=f"msg_comb_{i}",
            channel=ChannelType.WHATSAPP,
            sender_id=f"+9198888{i:04d}",
            customer_id=cid,
            text=case["prompt"],
        )
        resp = await engine.handle_message(msg)
        assert resp.text.strip(), f"Case {i} returned empty text"
        assert "```json" not in resp.text, f"Case {i} leaked JSON"
        assert '{"success":' not in resp.text, f"Case {i} leaked JSON"


def test_property_based_invariants_1000_runs():
    """Verify 1,000 property fuzzing iterations on math conservation, turn boundaries, and anti-amnesia."""
    passed, total, failures = run_tier3_property_fuzzing(count=1000)
    assert passed == total, f"Property fuzzing had {len(failures)} failures: {failures[:5]}"
