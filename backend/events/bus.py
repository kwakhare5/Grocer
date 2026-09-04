"""In-process event bus for GROCER v2.

LOCKED (spec §30): async in-process pub/sub — zero Kafka/RabbitMQ.
Events are published to registered async handlers and persisted to
the Event audit table via an optional database session.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession


# Handler type: async callable receiving entity_type, entity_id, payload
EventHandler = Callable[[str, str, Any], Awaitable[None]]


class EventBus:
    """Simple in-process async event pub/sub bus.

    Usage:
        bus = EventBus()

        @bus.subscribe("ORDER_CREATED")
        async def on_order(entity_type, entity_id, payload):
            ...

        await bus.publish(db, "ORDER_CREATED", "order", order_id, {...})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator to register a handler for a given event type."""

        def decorator(fn: EventHandler) -> EventHandler:
            self._handlers[event_type].append(fn)
            return fn

        return decorator

    def register(self, event_type: str, handler: EventHandler) -> None:
        """Programmatically register a handler."""
        self._handlers[event_type].append(handler)

    async def publish(
        self,
        db: AsyncSession,
        event_type: str,
        entity_type: str,
        entity_id: uuid.UUID | str,
        payload: Any = None,
        *,
        persist: bool = True,
    ) -> None:
        """Publish an event.

        - Calls all registered handlers for *event_type*.
        - If persist=True and db is provided, writes an Event row for audit trail.
        """
        if payload is None:
            payload = {}

        # Persist to audit log first
        if persist and db is not None:
            # Import here to avoid circular imports at module level
            from backend.models.core import Event  # noqa: PLC0415

            row = Event(
                event_id=uuid.uuid4(),
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                entity_type=entity_type,
                entity_id=uuid.UUID(str(entity_id)),
                payload=payload,
            )
            db.add(row)
            # Flush so the row gets a PK; caller is responsible for commit.
            await db.flush()

        # Dispatch to in-process handlers
        for handler in self._handlers.get(event_type, []):
            await handler(entity_type, str(entity_id), payload)


# Singleton bus — imported by services that need to publish or subscribe.
bus = EventBus()
