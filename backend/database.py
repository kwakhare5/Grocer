"""Database connection pooling utilities."""
from __future__ import annotations

from typing import Any


async def create_postgres_pool(database_url: str, *, max_size: int = 5) -> Any:
    """Create an SSL-only asyncpg pool suitable for a managed Postgres backend."""
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("Install asyncpg before enabling DATABASE_URL.") from exc

    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=max_size,
        ssl="require",
        statement_cache_size=0,
    )
