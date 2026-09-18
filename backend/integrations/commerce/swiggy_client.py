"""Low-level JSON-RPC 2.0 MCP transport client for Swiggy Instamart."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import httpx

from backend.integrations.commerce.exceptions import (
    AddressNotServiceableError,
    CartExpiredError,
    CommerceError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    ProviderAuthError,
    ProviderSessionRevokedError,
    UpstreamTimeoutError,
)

logger = logging.getLogger(__name__)


class SwiggyMcpClient:
    """Handles HTTP POST JSON-RPC 2.0 transport and error classification for Swiggy MCP."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        auth_token: Optional[str] = None,
        token_resolver: Optional[Callable[[str], Optional[str]]] = None,
        owner_customer_id: Optional[str] = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._auth_token = auth_token
        self._token_resolver = token_resolver
        self._owner_customer_id = owner_customer_id

    def resolve_token(self, customer_id: Optional[str] = None) -> Optional[str]:
        """Resolve valid token for customer from resolver or static fallback."""
        if self._token_resolver:
            token = self._token_resolver(customer_id) if customer_id else None
            if token:
                return token
        if self._auth_token and self._owner_customer_id:
            if customer_id != self._owner_customer_id:
                raise ProviderAuthError(
                    "Configured Swiggy session belongs to a different customer."
                )
        return self._auth_token

    def parse_error_if_failed(self, response_data: dict[str, Any]) -> None:
        """Classify errors from Swiggy envelope per official error taxonomy."""
        if response_data.get("success") is False:
            err = response_data.get("error", {})
            msg = err.get("message", "Swiggy operation failed")
            msg_lower = msg.lower()

            if "out of stock" in msg_lower or "item_out_of_stock" in msg_lower:
                raise ItemOutOfStockError(spin_id="unknown")
            elif "not serviceable" in msg_lower or "address_not_serviceable" in msg_lower:
                raise AddressNotServiceableError(address_id="current")
            elif "minimum order" in msg_lower or "min order" in msg_lower or "min_order_not_met" in msg_lower:
                raise MinOrderNotMetError(current_total=0.0)
            elif "expired" in msg_lower or "abandoned" in msg_lower or "cart_expired" in msg_lower:
                raise CartExpiredError(cart_id="current")
            elif "unauthenticated" in msg_lower or "token_expired" in msg_lower:
                raise ProviderAuthError(msg)
            elif "session_revoked" in msg_lower:
                raise ProviderSessionRevokedError(msg)
            else:
                raise CommerceError(f"Swiggy error: {msg}")

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        customer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute JSON-RPC 2.0 tool call against Swiggy Instamart MCP endpoint."""
        token = self.resolve_token(customer_id)
        if self._token_resolver is not None and not token:
            raise ProviderAuthError(
                "No active Swiggy session exists for this customer."
            )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.base_url, json=payload, headers=headers)

                if resp.status_code == 401:
                    raise ProviderAuthError("Swiggy MCP session unauthenticated or token expired.")
                elif resp.status_code == 419:
                    raise ProviderSessionRevokedError("Swiggy MCP session revoked. Re-auth required.")
                elif resp.status_code == 504:
                    raise UpstreamTimeoutError("Swiggy MCP upstream gateway timed out.")
                elif resp.status_code >= 500:
                    raise UpstreamTimeoutError(f"Swiggy MCP upstream error: HTTP {resp.status_code}")
                elif resp.status_code >= 400:
                    err_msg = f"Swiggy MCP bad request: HTTP {resp.status_code}"
                    try:
                        err_data = resp.json()
                        if "error" in err_data:
                            self.parse_error_if_failed(err_data)
                    except Exception as parse_exc:
                        if isinstance(parse_exc, CommerceError):
                            raise parse_exc
                    raise CommerceError(err_msg)

                data = resp.json()

                # Check JSON-RPC protocol error
                if "error" in data and not data.get("result"):
                    rpc_err = data["error"]
                    code = rpc_err.get("code")
                    msg = rpc_err.get("message", "Unknown JSON-RPC error")
                    if code == -32001:
                        raise ProviderAuthError(msg)
                    self.parse_error_if_failed({"success": False, "error": rpc_err})
                    raise CommerceError(f"Swiggy MCP RPC error {code}: {msg}")

                result = data.get("result", data)
                # Official Swiggy MCP returns structuredContent inside result
                if isinstance(result, dict) and "structuredContent" in result and "data" not in result:
                    result["data"] = result["structuredContent"]
                    return result
                return result

        except httpx.TimeoutException:
            raise UpstreamTimeoutError("Swiggy MCP request timed out.")
        except httpx.RequestError as exc:
            if isinstance(exc, (ProviderAuthError, UpstreamTimeoutError, CommerceError)):
                raise exc
            raise CommerceError(f"Swiggy MCP network connection failure: {exc}")
