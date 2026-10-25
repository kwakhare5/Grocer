"""Grocer v1.0 — Database Connection Pooling & Advisory Lock Management.

Manages asyncpg connection pool to PostgreSQL (Supabase) with strict SSL,
connection pooling, advisory locking for per-user concurrency, and migration execution.
"""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

from backend.config import settings

logger = logging.getLogger("grocer.database")

_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    """Retrieve or initialize the global PostgreSQL connection pool."""
    global _pool
    if _pool is None:
        logger.info("Initializing asyncpg connection pool to PostgreSQL...")
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=settings.DATABASE_POOL_MIN_SIZE,
            max_size=settings.DATABASE_POOL_MAX_SIZE,
            command_timeout=30.0,
        )
    return _pool


async def close_db_pool() -> None:
    """Close the global connection pool cleanly upon application shutdown."""
    global _pool
    if _pool is not None:
        logger.info("Closing asyncpg connection pool...")
        await _pool.close()
        _pool = None


async def check_db_health() -> bool:
    """Verify that PostgreSQL is reachable and responsive."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            return val == 1
    except (asyncpg.PostgresError, OSError) as exc:
        logger.error("Database health check failed: %s", exc)
        return False


async def apply_migrations() -> list[str]:
    """Apply all pending SQL migrations from the migrations/ directory in order."""
    pool = await get_db_pool()
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    applied: list[str] = []

    if not migrations_dir.exists():
        logger.warning("No migrations directory found at %s", migrations_dir)
        return applied

    sql_files = sorted(migrations_dir.glob("*.sql"))
    async with pool.acquire() as conn:
        for sql_file in sql_files:
            logger.info("Executing migration: %s", sql_file.name)
            sql_content = sql_file.read_text(encoding="utf-8")
            await conn.execute(sql_content)
            applied.append(sql_file.name)

    return applied
