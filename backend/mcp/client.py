"""
PreFill MCP Client wrapper — Task 1.4
Centralizes all HTTP interactions with the PreFill MCP server.
"""

import httpx
import logging
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)


class PreFillMCPClient:
    def __init__(self, base_url: str = settings.MCP_BASE_URL):
        self.base_url = base_url
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        """Open the shared connection pool. Call once from the FastAPI lifespan."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        # Fallback for contexts where startup() wasn't called (standalone
        # scripts, seed_prices.py, etc.)
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def get_platform_orders(self, user_id: str, limit: int = 200) -> dict:
        """Fetch complete order history for a user."""
        response = await self.client.get(
            "/get_platform_orders",
            params={"user_id": user_id, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

    async def search_platform_items(self, query: str) -> dict:
        """Search products matching query in the catalog."""
        response = await self.client.post(
            "/search_platform_items",
            json={"query": query}
        )
        response.raise_for_status()
        return response.json()

    async def update_platform_cart(self, items: list) -> dict:
        """Update or create cart with standard line items."""
        response = await self.client.post(
            "/update_platform_cart",
            json={"items": items}
        )
        response.raise_for_status()
        return response.json()

    async def place_platform_order(self, cart_id: str) -> dict:
        """Place the quick commerce order."""
        response = await self.client.post(
            "/place_platform_order",
            json={"cart_id": cart_id}
        )
        response.raise_for_status()
        return response.json()


mcp_client = PreFillMCPClient()
