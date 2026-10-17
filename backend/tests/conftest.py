"""Pytest root configuration and fixtures for Grocer."""
from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "whatsapp_postgres_e2e" in item.nodeid:
            item.add_marker(pytest.mark.e2e)
