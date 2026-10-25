"""Grocer v1.0 — Global Pytest Fixtures.

Provides clean-slate testing harnesses, async event loops, and database fixtures.
Zero project mocks are permitted per AGENTS.md rules.
"""
import os
import pytest
import pytest_asyncio
from pathlib import Path

# Ensure repository root is on sys.path
import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import settings

@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to committed real staging fixtures."""
    return Path(__file__).resolve().parent / "fixtures"
