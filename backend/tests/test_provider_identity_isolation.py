"""Swiggy provider credentials remain bound to one customer context."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.session import OrchestratorSessionStore


class IdentityRecordingAdapter(MockCommerceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.active_customer: str | None = None

    @contextmanager
    def customer_scope(self, customer_id: str):  # type: ignore[no-untyped-def]
        previous = self.active_customer
        self.active_customer = customer_id
        try:
            yield
        finally:
            self.active_customer = previous

    async def search_products(self, address_id: str, query: str):  # type: ignore[no-untyped-def]
        assert self.active_customer == "customer-a"
        return await super().search_products(address_id, query)


def test_customer_scoped_token_resolver_never_falls_back_across_users() -> None:
    tokens = {"customer-a": "token-a", "customer-b": "token-b"}
    adapter = SwiggyMCPAdapter(token_resolver=tokens.get)

    with adapter.customer_scope("customer-a"):
        assert adapter._resolve_token() == "token-a"
    with adapter.customer_scope("customer-b"):
        assert adapter._resolve_token() == "token-b"

    assert adapter._resolve_token() is None


def test_static_live_token_requires_and_enforces_owner() -> None:
    adapter = SwiggyMCPAdapter(
        auth_token="secret-token",
        owner_customer_id="customer-a",
    )

    with adapter.customer_scope("customer-a"):
        assert adapter._resolve_token() == "secret-token"
    with adapter.customer_scope("customer-b"):
        with pytest.raises(ProviderAuthError, match="different customer"):
            adapter._resolve_token()


def test_live_factory_rejects_unowned_static_token(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from backend.integrations.commerce import factory

    monkeypatch.setattr(factory.settings, "COMMERCE_ADAPTER_TYPE", "swiggy_mcp")
    monkeypatch.setattr(factory.settings, "SWIGGY_AUTH_TOKEN", "secret-token")
    monkeypatch.setattr(factory.settings, "SWIGGY_CUSTOMER_ID", None, raising=False)

    with pytest.raises(RuntimeError, match="SWIGGY_CUSTOMER_ID"):
        get_commerce_adapter()


@pytest.mark.asyncio
async def test_orchestrator_scopes_provider_calls_to_session_customer() -> None:
    adapter = IdentityRecordingAdapter()
    orchestrator = GrocerOrchestrator(
        commerce_adapter=adapter,
        session_store=OrchestratorSessionStore(),
    )

    result = await orchestrator.handle_turn("session-a", "customer-a", "get 1L milk")

    assert result.session_id == "session-a"
    assert adapter.active_customer is None
