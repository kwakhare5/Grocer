"""Factory for obtaining configured CommercePort adapter."""
from __future__ import annotations

from backend.config import settings
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.token_vault import default_token_vault


_cached_mock_adapter: MockCommerceAdapter | None = None
_cached_swiggy_adapter: SwiggyMCPAdapter | None = None


def get_commerce_adapter(force_mock: bool = False) -> CommercePort:
    """Resolve and return active CommercePort adapter based on settings."""
    global _cached_mock_adapter, _cached_swiggy_adapter

    adapter_type = "mock" if force_mock else getattr(settings, "COMMERCE_ADAPTER_TYPE", "mock").lower()

    if adapter_type == "swiggy_mcp":
        if _cached_swiggy_adapter is None:
            base_url = getattr(settings, "SWIGGY_MCP_BASE_URL", "https://mcp.swiggy.com/im")
            _cached_swiggy_adapter = SwiggyMCPAdapter(
                base_url=base_url,
                token_resolver=default_token_vault.get_token_durable,
            )
        return _cached_swiggy_adapter

    if _cached_mock_adapter is None:
        _cached_mock_adapter = MockCommerceAdapter()
    return _cached_mock_adapter
