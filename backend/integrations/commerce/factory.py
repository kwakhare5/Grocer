"""Factory for obtaining configured CommercePort adapter."""
from __future__ import annotations

from backend.config import settings
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


_cached_mock_adapter: MockCommerceAdapter | None = None


def get_commerce_adapter(force_mock: bool = False) -> CommercePort:
    """Resolve and return active CommercePort adapter based on settings."""
    global _cached_mock_adapter

    adapter_type = "mock" if force_mock else getattr(settings, "COMMERCE_ADAPTER_TYPE", "mock").lower()

    if adapter_type == "swiggy_mcp":
        base_url = getattr(settings, "SWIGGY_MCP_BASE_URL", "https://mcp.swiggy.com/im")
        auth_token = getattr(settings, "SWIGGY_AUTH_TOKEN", None)
        return SwiggyMCPAdapter(base_url=base_url, auth_token=auth_token)

    if _cached_mock_adapter is None:
        _cached_mock_adapter = MockCommerceAdapter()
    return _cached_mock_adapter