"""Grocer v1.0 — App queries run as the least-privilege database role."""

from __future__ import annotations

import asyncpg
import pytest

from backend.database import get_db_pool


@pytest.mark.db
@pytest.mark.asyncio
async def test_app_pool_uses_grocer_app_and_cannot_create_tables():
    pool = await get_db_pool()
    assert await pool.fetchval("SELECT current_user;") == "grocer_app"
    assert await pool.fetchval("SELECT count(*) FROM grocer.users;") >= 0
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("CREATE TABLE grocer.role_escape_probe (id int);")
    exists = await pool.fetchval("SELECT to_regclass('grocer.role_escape_probe');")
    assert exists is None
    assert not await pool.fetchval(
        "SELECT has_table_privilege('grocer_app', 'grocer.schema_migrations', 'INSERT');"
    )
