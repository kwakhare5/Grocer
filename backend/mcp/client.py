"""
Swiggy Instamart MCP Client wrapper — Task 1.4
Centralizes all HTTP interactions with the Swiggy Instamart MCP server.
"""

import httpx
import logging
from backend.config import settings

logger = logging.getLogger(__name__)


class SwiggyMCPClient:
    def __init__(self, base_url: str = settings.MCP_BASE_URL):
        self.base_url = base_url
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    async def get_instamart_orders(self, user_id: str, limit: int = 200) -> dict:
        """Fetch complete order history for a user."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/get_instamart_orders",
                params={"user_id": user_id, "limit": limit}
            )
            response.raise_for_status()
            return response.json()

    async def search_instamart_items(self, query: str) -> dict:
        """Search products matching query in the catalog."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/search_instamart_items",
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()

    async def update_instamart_cart(self, items: list) -> dict:
        """Update or create cart with standard line items."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/update_instamart_cart",
                json={"items": items}
            )
            response.raise_for_status()
            return response.json()

    async def place_instamart_order(self, cart_id: str) -> dict:
        """Place the Swiggy Instamart order."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/place_instamart_order",
                json={"cart_id": cart_id}
            )
            response.raise_for_status()
            return response.json()


mcp_client = SwiggyMCPClient()
