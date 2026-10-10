"""Database connection pooling utilities."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


async def create_postgres_pool(database_url: str, *, max_size: int = 5) -> Any:
    """Create an asyncpg connection pool (SSL-required for remote, SSL-disabled for localhost)."""
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("Install asyncpg before enabling DATABASE_URL.") from exc

    local_database = (urlparse(database_url).hostname or "") in {"127.0.0.1", "localhost", "::1"}
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=max_size,
        ssl=False if local_database else "require",
        statement_cache_size=0,
        timeout=10.0,
        command_timeout=15.0,
        max_inactive_connection_lifetime=180.0,
    )
