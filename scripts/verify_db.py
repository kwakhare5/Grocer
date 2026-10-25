"""Grocer v1.0 — Database Verification Helper."""
import asyncio
import sys
from pathlib import Path

# Ensure root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db_pool, close_db_pool

async def verify():
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'grocer' ORDER BY table_name;
            """)
            names = [t['table_name'] for t in tables]
            print(f"Active grocer tables in Supabase: {names}")
            expected = {"approvals", "checkouts", "inbound_messages", "oauth_tokens", "sessions", "users"}
            actual = set(names)
            assert expected == actual, f"Expected {expected}, got {actual}"
            print("Database schema verification PASSED (6/6 tables present).")
    finally:
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(verify())
