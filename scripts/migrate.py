"""Grocer v1.0 — Standalone Database Migration Runner.

Executes pending SQL migrations against Supabase PostgreSQL and verifies table creation.
"""
import asyncio
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import apply_migrations, close_db_pool, get_db_pool


async def run():
    print("Connecting to Supabase PostgreSQL...")
    pool = await get_db_pool()
    try:
        print("Applying SQL migrations...")
        applied = await apply_migrations()
        print(f"Applied migrations: {applied}")

        async with pool.acquire() as conn:
            # Check tables created under 'grocer' schema
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'grocer'
                ORDER BY table_name;
            """)
            print(f"\nTables in schema 'grocer' ({len(tables)}):")
            for t in tables:
                print(f"  [x] grocer.{t['table_name']}")

            expected = {
                "address_coords",
                "approvals",
                "checkouts",
                "inbound_messages",
                "oauth_tokens",
                "schema_migrations",
                "sessions",
                "users",
            }
            actual = {t["table_name"] for t in tables}
            missing = expected - actual

            if missing:
                print(f"\nERROR: Missing expected tables: {missing}")
                sys.exit(1)
            else:
                print("\nSUCCESS: All 8 Grocer tables present in Supabase!")
    finally:
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(run())
