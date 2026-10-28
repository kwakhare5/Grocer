"""Grocer — Database Connection Pooling & Advisory Lock Management.

Manages asyncpg connection pool to PostgreSQL (Supabase) with strict SSL,
connection pooling, advisory locking for per-user concurrency, and migration execution.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

from backend.config import settings

logger = logging.getLogger("grocer.database")

_pool: asyncpg.Pool | None = None
_pool_loop: asyncio.AbstractEventLoop | None = None
_APP_ROLE = "grocer_app"


async def _apply_app_role(conn: asyncpg.Connection) -> None:
    """Drop every pooled connection to the least-privilege app role.

    The login stays the project owner so migrations can run on a separate
    connection; ordinary queries must never fall back to owner rights.
    """
    has_role = await conn.fetchval("SELECT to_regrole($1) IS NOT NULL;", _APP_ROLE)
    if not has_role:
        raise RuntimeError(
            f"Required database role '{_APP_ROLE}' is missing; run migrations."
        )
    await conn.execute("SELECT set_config('role', $1, false);", _APP_ROLE)


def _under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


def _database_name(dsn: str) -> str:
    return urlparse(dsn).path.lstrip("/")


def resolve_database_url() -> str:
    """Return the DSN for this process.

    Tests never fall back to the production database: without TEST_DATABASE_URL
    they fail loudly instead of writing real customer data. The test DSN must
    name the grocer_test database in the same project.
    """
    if _under_pytest():
        if not settings.TEST_DATABASE_URL:
            raise RuntimeError(
                "Refusing to use DATABASE_URL while running tests. Set "
                "TEST_DATABASE_URL to the grocer_test database."
            )
        test_db = _database_name(settings.TEST_DATABASE_URL)
        if test_db != "grocer_test":
            raise RuntimeError(
                f"Refusing to run tests against database '{test_db}'. "
                "TEST_DATABASE_URL must point at grocer_test."
            )
        if test_db == _database_name(settings.DATABASE_URL):
            raise RuntimeError(
                "Refusing to run tests: TEST_DATABASE_URL and DATABASE_URL "
                "name the same database."
            )
        return settings.TEST_DATABASE_URL
    return settings.DATABASE_URL


async def get_db_pool() -> asyncpg.Pool:
    """Retrieve or initialize the global PostgreSQL connection pool."""
    global _pool, _pool_loop
    current_loop = asyncio.get_running_loop()
    if _pool is None or _pool_loop is not current_loop or _pool_loop.is_closed():
        logger.info("Initializing asyncpg connection pool to PostgreSQL...")
        _pool = await asyncpg.create_pool(
            dsn=resolve_database_url(),
            min_size=settings.DATABASE_POOL_MIN_SIZE,
            max_size=settings.DATABASE_POOL_MAX_SIZE,
            command_timeout=30.0,
            init=_apply_app_role,
        )
        _pool_loop = current_loop
    return _pool


async def close_db_pool() -> None:
    """Close the global connection pool cleanly upon application shutdown."""
    global _pool, _pool_loop
    if _pool is not None:
        logger.info("Closing asyncpg connection pool...")
        try:
            if _pool_loop is not None and not _pool_loop.is_closed():
                await _pool.close()
        finally:
            _pool = None
            _pool_loop = None


async def check_db_health() -> bool:
    """Healthy means reachable, migrated, and running as the app role."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            return bool(
                await conn.fetchval(
                    """
                    SELECT to_regclass('grocer.sessions') IS NOT NULL
                       AND to_regclass('grocer.oauth_states') IS NOT NULL;
                    """
                )
            )
    except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, RuntimeError) as exc:
        logger.error("Database health check failed: %s", exc)
        return False


async def apply_migrations() -> list[str]:
    """Apply SQL migrations that have not run yet, in filename order.

    Each file is recorded in grocer.schema_migrations only after it succeeds, so
    a fresh deploy builds the full schema and a warm deploy skips everything.
    Runs on its own owner connection; the app pool is created only after the
    migrations (and the grocer_app role) exist.
    """
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    applied: list[str] = []

    if not migrations_dir.exists():
        logger.warning("No migrations directory found at %s", migrations_dir)
        return applied

    conn = await asyncpg.connect(
        dsn=resolve_database_url(),
        command_timeout=30.0,
    )
    try:
        await conn.execute("create schema if not exists grocer;")
        await conn.execute(
            """
            create table if not exists grocer.schema_migrations (
                filename text primary key,
                applied_at timestamptz not null default now()
            );
            """
        )
        done = {
            row["filename"]
            for row in await conn.fetch("SELECT filename FROM grocer.schema_migrations;")
        }

        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if sql_file.name in done:
                continue
            logger.info("Applying migration: %s", sql_file.name)
            sql_content = sql_file.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql_content)
                await conn.execute(
                    "INSERT INTO grocer.schema_migrations (filename) VALUES ($1);",
                    sql_file.name,
                )
            applied.append(sql_file.name)
    finally:
        await conn.close()

    return applied
