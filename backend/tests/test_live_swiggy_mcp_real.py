"""Authoritative Real-Calls-Over-Mocks test verifying live Swiggy MCP & live Gemini API.

Strictly adheres to Master Rule:
Zero mocking of project code, databases, APIs, or MCP tools.
"""
from __future__ import annotations

import pytest
from backend.config import settings
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.agent.gemini import GeminiClient


@pytest.mark.asyncio
async def test_live_swiggy_mcp_real_addresses_and_catalog():
    """Verify live Swiggy MCP endpoint returns real customer addresses and live dark store catalog."""
    assert settings.SWIGGY_AUTH_TOKEN, "SWIGGY_AUTH_TOKEN must be present in .env"
    adapter = SwiggyMCPAdapter(
        base_url=settings.SWIGGY_MCP_BASE_URL,
        auth_token=settings.SWIGGY_AUTH_TOKEN,
        owner_customer_id="cust-live-test",
    )
    with adapter.customer_scope("cust-live-test"):
        # 1. Real Swiggy MCP get_addresses call
        addresses = await adapter.get_addresses(customer_id="cust-live-test")
        assert len(addresses) >= 1, "Expected at least 1 real saved address from live Swiggy MCP"
        first_addr = addresses[0]
        assert first_addr.id, "Live address must have an ID"
        assert "Maharashtra" in first_addr.street or "Pune" in first_addr.street or "Karan" in first_addr.street

        # 2. Real Swiggy MCP live dark store product search
        products = await adapter.search_products(first_addr.id, "Amul Taaza Milk")
        assert len(products) >= 1, "Expected real in-stock dark store products"
        assert any("amul" in p.name.lower() or "milk" in p.name.lower() for p in products)


@pytest.mark.asyncio
async def test_live_gemini_real_nlu_completion():
    """Verify live Gemini API returns real completions."""
    assert settings.GEMINI_API_KEY, "GEMINI_API_KEY must be present in .env"
    gemini = GeminiClient(api_key=settings.GEMINI_API_KEY)
    res = await gemini.generate_content(
        contents=[{"role": "user", "parts": [{"text": "Name 3 grocery staples in a comma-separated list"}]}],
        system_text="You are Grocer concierge."
    )
    assert res is not None
    candidates = res.get("candidates", [])
    assert len(candidates) >= 1
    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    assert len(text) > 0
