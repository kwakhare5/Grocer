"""Pytest root configuration and fixtures for Grocer."""
from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
import pytest

# Force load .env from project root so all tests have live Supabase and live MCP credentials
_root_env = Path(__file__).resolve().parents[2] / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env, override=False)


def pytest_collection_modifyitems(items):
    for item in items:
        if "whatsapp_postgres_e2e" in item.nodeid:
            item.add_marker(pytest.mark.e2e)
