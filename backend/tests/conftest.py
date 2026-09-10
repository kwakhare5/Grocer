from collections.abc import AsyncGenerator

import pytest_asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api import intent_chat
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.session import default_session_store
from backend.main import create_app


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
