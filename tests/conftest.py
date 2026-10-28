"""Grocer v1.0 — Global Pytest Fixtures.

Database-backed tests are marked `db`. They run only when TEST_DATABASE_URL is
set, and every user they create is deleted when the session ends.
"""

# Ensure repository root is on sys.path
import asyncio
import sys
from pathlib import Path

import asyncpg
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import settings

_DB_TESTS_RAN = False
_BASELINE_USER_IDS: set[str] | None = None


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "db: needs PostgreSQL; requires TEST_DATABASE_URL"
    )
    config.addinivalue_line(
        "markers", "live: calls a live external service; excluded by default"
    )
    config.addinivalue_line(
        "markers",
        "scripted: injects a fake external client on purpose; never proof of live behavior",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if settings.TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(
        reason="TEST_DATABASE_URL not set; refusing to use the production database"
    )
    for item in items:
        if item.get_closest_marker("db"):
            item.add_marker(skip)


@pytest.fixture(autouse=True)
async def _prepare_test_database(request: pytest.FixtureRequest) -> None:
    """Build the schema lazily for marked tests."""
    global _DB_TESTS_RAN, _BASELINE_USER_IDS
    if request.node.get_closest_marker("db") is None:
        return
    if not settings.TEST_DATABASE_URL:
        return
    _DB_TESTS_RAN = True
    from backend.database import apply_migrations, get_db_pool

    pool = await get_db_pool()
    await apply_migrations()
    if _BASELINE_USER_IDS is None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id::text AS id FROM grocer.users;")
        _BASELINE_USER_IDS = {row["id"] for row in rows}


async def _delete_rows_not_in_baseline(baseline: set[str]) -> None:
    conn = await asyncpg.connect(dsn=settings.TEST_DATABASE_URL)
    try:
        async with conn.transaction():
            # checkouts has no cascade, so remove it before approvals and users.
            for table, column in (
                ("checkouts", "user_id"),
                ("approvals", "user_id"),
                ("inbound_messages", "user_id"),
            ):
                await conn.execute(
                    f"DELETE FROM grocer.{table} WHERE {column} IN ("
                    "SELECT id FROM grocer.users WHERE NOT (id::text = ANY($1)));",
                    baseline,
                )
            await conn.execute(
                "DELETE FROM grocer.users WHERE NOT (id::text = ANY($1));", baseline
            )
    finally:
        await conn.close()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove every user the test run created, including their child rows."""
    if not _DB_TESTS_RAN or _BASELINE_USER_IDS is None:
        return
    asyncio.run(_delete_rows_not_in_baseline(_BASELINE_USER_IDS))


