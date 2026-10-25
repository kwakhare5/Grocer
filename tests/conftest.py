"""Grocer v1.0 — Global Pytest Fixtures.

Provides clean-slate testing harnesses, async event loops, and database fixtures.
Zero project mocks are permitted per AGENTS.md rules.
"""

# Ensure repository root is on sys.path
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to committed real staging fixtures."""
    return Path(__file__).resolve().parent / "fixtures"
