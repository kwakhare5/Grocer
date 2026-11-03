"""Grocer — Standalone Database Migration Runner.

Applies pending SQL migrations, then runs the schema verification helper.
"""
import asyncio
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import apply_migrations
from scripts.verify_db import verify


async def run():
    print("Connecting to Supabase PostgreSQL...")
    print("Applying SQL migrations...")
    applied = await apply_migrations()
    print(f"Applied migrations: {applied}")
    await verify()


if __name__ == "__main__":
    asyncio.run(run())
