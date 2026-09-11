from collections.abc import AsyncGenerator

import pytest_asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api import intent_chat
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.session import default_session_store
from backend.intent.stages.address_stage import default_address_manager
from backend.main import create_app


@pytest.fixture(autouse=True)
def clean_isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    session_file = tmp_path / "test_sessions.json"
    address_file = tmp_path / "test_addresses.json"
    monkeypatch.setenv("GROCER_SESSION_CACHE", str(session_file))
    monkeypatch.setenv("GROCER_ADDRESS_CACHE", str(address_file))
    default_session_store.reset()
    default_address_manager.reset()
    yield
    default_session_store.reset()
    default_address_manager.reset()


@pytest_asyncio.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an isolated, non-network HTTP client for API tests."""
    monkeypatch.setattr(
        intent_chat,
        "_orchestrator",
        GrocerOrchestrator(
            commerce_adapter=MockCommerceAdapter(),
            session_store=default_session_store,
        ),
    )
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
