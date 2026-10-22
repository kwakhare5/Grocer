"""Tests for Slice 7d: 90s claim lease with heartbeat and advisory turn lock removal."""
from __future__ import annotations

import asyncio
import itertools
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.channels.message_store import CLAIM_LEASE_SECONDS, PostgresMessageStore
from backend.channels.models import ChannelType, NormalizedIncomingMessage
from backend.tests.suites.helpers import postgres_pool


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_claim_older_than_90s_is_reclaimed_with_uncertainty_reply(postgres_pool):
    assert CLAIM_LEASE_SECONDS == 90
    store = PostgresMessageStore(postgres_pool)
    msg = NormalizedIncomingMessage(
        message_id="wamid.slice7d.stale",
        channel=ChannelType.WHATSAPP,
        sender_id="919999900001",
        customer_id="cust-slice7d-stale",
        text="add 2 apples",
    )
    await store.enqueue_many([msg])

    # Mark as PROCESSING with claimed_at 95s ago (older than 90s lease)
    await postgres_pool.execute(
        "UPDATE grocer_internal.inbound_messages SET status='PROCESSING', claimed_at=now() - interval '95 seconds' WHERE message_id=$1",
        msg.message_id,
    )
    recovered = await store.recover_stale_processing()
    assert recovered == 1

    inbound = await postgres_pool.fetchrow(
        "SELECT status FROM grocer_internal.inbound_messages WHERE message_id=$1",
        msg.message_id,
    )
    assert inbound["status"] == "PROCESSED"

    outbound = await postgres_pool.fetch(
        "SELECT payload FROM grocer_internal.outbound_messages WHERE customer_id=$1 ORDER BY id DESC",
        msg.customer_id,
    )
    assert len(outbound) == 1
    reply_payload = json.loads(outbound[0]["payload"])
    assert "UNCERTAIN_ACTION" in reply_payload.get("events", [])
    assert "couldn't verify" in reply_payload.get("text", "").lower()

    # Also verify that a claim younger than 90s (e.g. 70s ago) is NOT reclaimed
    msg_fresh = NormalizedIncomingMessage(
        message_id="wamid.slice7d.fresh",
        channel=ChannelType.WHATSAPP,
        sender_id="919999900002",
        customer_id="cust-slice7d-fresh",
        text="add bread",
    )
    await store.enqueue_many([msg_fresh])
    await postgres_pool.execute(
        "UPDATE grocer_internal.inbound_messages SET status='PROCESSING', claimed_at=now() - interval '70 seconds' WHERE message_id=$1",
        msg_fresh.message_id,
    )
    recovered_fresh = await store.recover_stale_processing()
    assert recovered_fresh == 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_heartbeat_keeps_claim_alive_past_90s(postgres_pool):
    store = PostgresMessageStore(postgres_pool)
    msg = NormalizedIncomingMessage(
        message_id="wamid.slice7d.heartbeat",
        channel=ChannelType.WHATSAPP,
        sender_id="919999900003",
        customer_id="cust-slice7d-heartbeat",
        text="add butter",
    )
    await store.enqueue_many([msg])

    # Mark as PROCESSING initially 80s ago
    await postgres_pool.execute(
        "UPDATE grocer_internal.inbound_messages SET status='PROCESSING', claimed_at=now() - interval '80 seconds' WHERE message_id=$1",
        msg.message_id,
    )
    row = await postgres_pool.fetchrow(
        "SELECT id FROM grocer_internal.inbound_messages WHERE message_id=$1",
        msg.message_id,
    )
    inbound_id = row["id"]

    # Heartbeat updates claimed_at to now() and returns 1 updated row
    rows_updated = await store.heartbeat_processing(inbound_id)
    assert rows_updated == 1

    # Read claimed_at from DB and assert it is now within 2 seconds of now
    row_after = await postgres_pool.fetchrow(
        "SELECT EXTRACT(EPOCH FROM (now() - claimed_at)) AS diff_sec FROM grocer_internal.inbound_messages WHERE id=$1",
        inbound_id,
    )
    assert abs(row_after["diff_sec"]) <= 2.0

    # Since claimed_at was updated to now, recover_stale_processing does NOT reclaim it
    recovered = await store.recover_stale_processing()
    assert recovered == 0

    # Still PROCESSING
    check = await postgres_pool.fetchrow(
        "SELECT status FROM grocer_internal.inbound_messages WHERE id=$1",
        inbound_id,
    )
    assert check["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_heartbeat_zero_rows_cancels_turn_and_sends_no_second_fallback(monkeypatch):
    from backend.api.whatsapp import drain_message_queue

    monkeypatch.setattr("backend.api.whatsapp.HEARTBEAT_INTERVAL_SECONDS", 0.01)

    msg = NormalizedIncomingMessage(
        message_id="wamid.slice7d.cancelled",
        channel=ChannelType.WHATSAPP,
        sender_id="919999900004",
        customer_id="cust-slice7d-cancelled",
        text="add milk",
    )

    claims = [(101, msg)]
    async def fake_claim_next():
        return claims.pop(0) if claims else None

    mock_store = MagicMock()
    mock_store.recover_stale_processing = AsyncMock(return_value=0)
    mock_store.recover_stale_outbound = AsyncMock(return_value=0)
    mock_store.claim_outbound = AsyncMock(return_value=None)
    mock_store.claim_next = fake_claim_next
    # Heartbeat returns 0 rows updated (claim lost to recovery)
    mock_store.heartbeat_processing = AsyncMock(return_value=0)
    mock_store.stage_response = AsyncMock()
    mock_store.mark_processing_failed = AsyncMock()

    turn_cancelled = False
    async def slow_turn(_message):
        nonlocal turn_cancelled
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            turn_cancelled = True
            raise

    mock_engine = MagicMock()
    mock_engine.handle_message = slow_turn

    await drain_message_queue(mock_store, mock_engine)

    assert turn_cancelled is True, "In-flight handle_message task was not cancelled"
    mock_store.stage_response.assert_not_called()
    mock_store.mark_processing_failed.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_crash_edge_retries_and_cancels_after_two_failed_ticks(monkeypatch):
    from backend.api.whatsapp import drain_message_queue

    monkeypatch.setattr("backend.api.whatsapp.HEARTBEAT_INTERVAL_SECONDS", 0.01)

    msg = NormalizedIncomingMessage(
        message_id="wamid.slice7d.crash-edge",
        channel=ChannelType.WHATSAPP,
        sender_id="919999900005",
        customer_id="cust-slice7d-crash-edge",
        text="add bread",
    )

    claims = [(102, msg)]
    async def fake_claim_next():
        return claims.pop(0) if claims else None

    mock_store = MagicMock()
    mock_store.recover_stale_processing = AsyncMock(return_value=0)
    mock_store.recover_stale_outbound = AsyncMock(return_value=0)
    mock_store.claim_outbound = AsyncMock(return_value=None)
    mock_store.claim_next = fake_claim_next
    # Heartbeat raises on both ticks
    mock_store.heartbeat_processing = AsyncMock(side_effect=RuntimeError("database blip"))
    mock_store.stage_response = AsyncMock()
    mock_store.mark_processing_failed = AsyncMock()

    turn_cancelled = False
    async def slow_turn(_message):
        nonlocal turn_cancelled
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            turn_cancelled = True
            raise

    mock_engine = MagicMock()
    mock_engine.handle_message = slow_turn

    await drain_message_queue(mock_store, mock_engine)

    assert turn_cancelled is True, "In-flight handle_message task was not cancelled after 2 failed heartbeat ticks"
    assert mock_store.heartbeat_processing.call_count >= 2, "Heartbeat was not retried on next tick before cancelling"
    mock_store.stage_response.assert_not_called()
    mock_store.mark_processing_failed.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_single_error_retries_and_completes_turn(monkeypatch):
    from backend.api.whatsapp import drain_message_queue
    from backend.channels.models import NormalizedOutgoingResponse

    monkeypatch.setattr("backend.api.whatsapp.HEARTBEAT_INTERVAL_SECONDS", 0.01)

    msg = NormalizedIncomingMessage(
        message_id="wamid.slice7d.single-err",
        channel=ChannelType.WHATSAPP,
        sender_id="919999900006",
        customer_id="cust-slice7d-single-err",
        text="add eggs",
    )

    claims = [(103, msg)]
    async def fake_claim_next():
        return claims.pop(0) if claims else None

    mock_store = MagicMock()
    mock_store.recover_stale_processing = AsyncMock(return_value=0)
    mock_store.recover_stale_outbound = AsyncMock(return_value=0)
    mock_store.claim_outbound = AsyncMock(return_value=None)
    mock_store.claim_next = fake_claim_next
    # First tick errors, all subsequent ticks succeed forever
    mock_store.heartbeat_processing = AsyncMock(
        side_effect=itertools.chain([RuntimeError("transient db blip")], itertools.repeat(1))
    )
    mock_store.stage_response = AsyncMock()
    mock_store.mark_processing_failed = AsyncMock()

    async def normal_turn(_message):
        await asyncio.sleep(0.06)
        return NormalizedOutgoingResponse(
            recipient_id=msg.sender_id,
            channel=ChannelType.WHATSAPP,
            text="Added eggs!",
            conversation_state="READY",
        )

    mock_engine = MagicMock()
    mock_engine.handle_message = normal_turn

    await drain_message_queue(mock_store, mock_engine)

    assert mock_store.stage_response.call_count == 1
    assert mock_store.heartbeat_processing.call_count >= 2
