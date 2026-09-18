"""Repositories for durable shopping tasks and WhatsApp inbox/outbox records."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from backend.intent.task_model import ShoppingTask


class TaskVersionConflict(RuntimeError):
    """A concurrent turn changed the task after it was read."""


class ShoppingTaskRepository(ABC):
    """Persistence boundary for ordered, optimistic shopping-task updates."""

    @abstractmethod
    async def get(self, task_id: str) -> ShoppingTask | None:
        raise NotImplementedError

    @abstractmethod
    async def create(self, task: ShoppingTask) -> ShoppingTask:
        raise NotImplementedError

    @abstractmethod
    async def save(self, task: ShoppingTask, *, expected_version: int) -> ShoppingTask:
        raise NotImplementedError

    @abstractmethod
    async def record_inbound_event(
        self, *, provider: str, message_id: str, payload: dict[str, Any], task_id: str | None
    ) -> bool:
        """Persist an inbound event once. False means it was already recorded."""
        raise NotImplementedError

    @abstractmethod
    async def enqueue_outbound_message(
        self, *, task_id: str, message_id: str, payload: dict[str, Any]
    ) -> None:
        raise NotImplementedError


class InMemoryShoppingTaskRepository(ShoppingTaskRepository):
    """Deterministic test repository; never use it as a deployed state store."""

    def __init__(self) -> None:
        self._tasks: dict[str, ShoppingTask] = {}
        self._inbound_events: set[tuple[str, str]] = set()
        self.outbox: list[dict[str, Any]] = []

    async def get(self, task_id: str) -> ShoppingTask | None:
        task = self._tasks.get(task_id)
        return ShoppingTask.model_validate(task.model_dump(mode="json")) if task else None

    async def create(self, task: ShoppingTask) -> ShoppingTask:
        if task.task_id in self._tasks:
            raise TaskVersionConflict(f"Task {task.task_id} already exists.")
        self._tasks[task.task_id] = ShoppingTask.model_validate(task.model_dump(mode="json"))
        return await self.get_required(task.task_id)

    async def get_required(self, task_id: str) -> ShoppingTask:
        task = await self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    async def save(self, task: ShoppingTask, *, expected_version: int) -> ShoppingTask:
        current = self._tasks.get(task.task_id)
        if current is None or current.version != expected_version:
            raise TaskVersionConflict(f"Task {task.task_id} changed concurrently.")
        self._tasks[task.task_id] = ShoppingTask.model_validate(task.model_dump(mode="json"))
        return await self.get_required(task.task_id)

    async def record_inbound_event(
        self, *, provider: str, message_id: str, payload: dict[str, Any], task_id: str | None
    ) -> bool:
        del payload, task_id
        key = (provider, message_id)
        if key in self._inbound_events:
            return False
        self._inbound_events.add(key)
        return True

    async def enqueue_outbound_message(
        self, *, task_id: str, message_id: str, payload: dict[str, Any]
    ) -> None:
        self.outbox.append(
            {"task_id": task_id, "message_id": message_id, "payload": payload}
        )


class PostgresShoppingTaskRepository(ShoppingTaskRepository):
    """PostgreSQL implementation using optimistic versioning and JSONB payloads.

    ``pool`` is an ``asyncpg.Pool``. It is injected so database lifecycle remains
    infrastructure-owned rather than hidden in domain code.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def get(self, task_id: str) -> ShoppingTask | None:
        row = await self._pool.fetchrow(
            "SELECT payload FROM grocer_internal.shopping_tasks WHERE task_id = $1", task_id
        )
        if row is None:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return ShoppingTask.model_validate(payload)

    async def create(self, task: ShoppingTask) -> ShoppingTask:
        payload = task.model_dump(mode="json")
        try:
            await self._pool.execute(
                """
                INSERT INTO grocer_internal.shopping_tasks
                    (task_id, customer_id, state, version, payload, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                """,
                task.task_id,
                task.customer_id,
                task.state.value,
                task.version,
                json.dumps(payload),
                task.created_at,
                task.updated_at,
            )
        except Exception as exc:
            if type(exc).__name__ == "UniqueViolationError":
                raise TaskVersionConflict(f"Task {task.task_id} already exists.") from exc
            raise
        return task

    async def save(self, task: ShoppingTask, *, expected_version: int) -> ShoppingTask:
        payload = task.model_dump(mode="json")
        result = await self._pool.execute(
            """
            UPDATE grocer_internal.shopping_tasks
            SET state = $2, version = $3, payload = $4::jsonb, updated_at = $5
            WHERE task_id = $1 AND version = $6
            """,
            task.task_id,
            task.state.value,
            task.version,
            json.dumps(payload),
            task.updated_at,
            expected_version,
        )
        if result != "UPDATE 1":
            raise TaskVersionConflict(f"Task {task.task_id} changed concurrently.")
        return task

    async def record_inbound_event(
        self, *, provider: str, message_id: str, payload: dict[str, Any], task_id: str | None
    ) -> bool:
        result = await self._pool.execute(
            """
            INSERT INTO grocer_internal.inbound_events
                (provider, message_id, task_id, payload, received_at)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            ON CONFLICT (provider, message_id) DO NOTHING
            """,
            provider,
            message_id,
            task_id,
            json.dumps(payload),
            datetime.now(timezone.utc),
        )
        return result == "INSERT 0 1"

    async def enqueue_outbound_message(
        self, *, task_id: str, message_id: str, payload: dict[str, Any]
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO grocer_internal.outbound_messages
                (task_id, source_message_id, payload, status, attempts, created_at)
            VALUES ($1, $2, $3::jsonb, 'PENDING', 0, $4)
            """,
            task_id,
            message_id,
            json.dumps(payload),
            datetime.now(timezone.utc),
        )


async def create_postgres_pool(database_url: str, *, max_size: int = 5) -> Any:
    """Create an SSL-only asyncpg pool suitable for a managed Postgres backend."""
    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError("Install asyncpg before enabling DATABASE_URL.") from exc

    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=max_size,
        ssl=True,
        statement_cache_size=0,
    )
