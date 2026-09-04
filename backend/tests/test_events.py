"""Tests for the in-process EventBus (spec §30).

Seams under test:
1. subscribe() / register() — handler registration
2. publish() — in-process dispatch to all matching handlers
3. publish() with persist=True — Event row written to audit DB
4. publish() to event with no handlers — silent no-op
5. Multiple handlers on same event type — all called
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.events.bus import EventBus
from backend.models.core import Event


# ---------------------------------------------------------------------------
# Unit tests — pure in-process dispatch (no DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_and_dispatch():
    """Registered handler is called once when matching event is published."""
    bus = EventBus()
    calls: list[tuple[str, str, dict]] = []

    @bus.subscribe("ORDER_CREATED")
    async def handler(entity_type: str, entity_id: str, payload: dict) -> None:
        calls.append((entity_type, entity_id, payload))

    eid = uuid.uuid4()
    await bus.publish(None, "ORDER_CREATED", "order", eid, {"qty": 5}, persist=False)

    assert len(calls) == 1
    assert calls[0] == ("order", str(eid), {"qty": 5})


@pytest.mark.asyncio
async def test_no_handler_for_event_is_silent():
    """Publishing an event with no subscribers is a no-op (no exception)."""
    bus = EventBus()
    # Should not raise
    await bus.publish(None, "UNKNOWN_EVENT", "thing", uuid.uuid4(), persist=False)


@pytest.mark.asyncio
async def test_multiple_handlers_all_called():
    """Multiple handlers registered for same event type — all invoked."""
    bus = EventBus()
    log: list[str] = []

    async def h1(et, ei, p): log.append("h1")
    async def h2(et, ei, p): log.append("h2")

    bus.register("TICK", h1)
    bus.register("TICK", h2)

    await bus.publish(None, "TICK", "sim", uuid.uuid4(), persist=False)
    assert "h1" in log
    assert "h2" in log


@pytest.mark.asyncio
async def test_handler_receives_payload():
    """Handler receives the exact payload dict that was published."""
    bus = EventBus()
    received: list[dict] = []

    @bus.subscribe("FORECAST_UPDATED")
    async def handler(et, ei, payload):
        received.append(payload)

    await bus.publish(None, "FORECAST_UPDATED", "forecast", uuid.uuid4(),
                      {"model": "baseline", "mae": 1.2}, persist=False)

    assert received == [{"model": "baseline", "mae": 1.2}]


# ---------------------------------------------------------------------------
# Integration tests — persistence to Event audit table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_persists_event_row(db_session):
    """publish() with persist=True writes exactly one Event row to the DB."""
    bus = EventBus()
    eid = uuid.uuid4()

    await bus.publish(db_session, "INVENTORY_CHANGED", "inventory", eid,
                      {"delta": -3}, persist=True)
    await db_session.commit()

    result = await db_session.execute(select(Event).where(Event.event_type == "INVENTORY_CHANGED"))
    rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].entity_type == "inventory"
    assert rows[0].payload == {"delta": -3}


@pytest.mark.asyncio
async def test_publish_persist_false_writes_no_row(db_session):
    """publish() with persist=False leaves the Event table unchanged."""
    bus = EventBus()
    await bus.publish(db_session, "RISK_DETECTED", "risk", uuid.uuid4(),
                      {"severity": "HIGH"}, persist=False)
    await db_session.commit()

    result = await db_session.execute(select(Event).where(Event.event_type == "RISK_DETECTED"))
    rows = result.scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_publish_persists_and_dispatches(db_session):
    """publish() simultaneously persists the row and calls the handler."""
    bus = EventBus()
    dispatched: list[str] = []

    @bus.subscribe("TIME_ADVANCED")
    async def handler(et, ei, payload):
        dispatched.append(payload.get("hours", 0))

    sim_id = uuid.uuid4()
    await bus.publish(db_session, "TIME_ADVANCED", "simulation", sim_id,
                      {"hours": 24}, persist=True)
    await db_session.commit()

    # Handler was called
    assert dispatched == [24]

    # Row was written
    result = await db_session.execute(select(Event).where(Event.event_type == "TIME_ADVANCED"))
    assert len(result.scalars().all()) == 1
