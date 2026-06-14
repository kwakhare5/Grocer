"""
Pytest configuration for async tests.
Provides shared fixtures and configures asyncio mode.
"""
import pytest
import asyncio
from backend.database.connection import engine


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()
