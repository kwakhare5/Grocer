from __future__ import annotations

import json

import httpx
import pytest

from backend.integrations.commerce.exceptions import CommerceError
from backend.integrations.commerce.swiggy_client import SwiggyMcpClient


class _FakeAsyncClient:
    def __init__(self, response: httpx.Response, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._response = response

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def post(self, *args: object, **kwargs: object) -> httpx.Response:
        del args, kwargs
        return self._response


@pytest.mark.asyncio
async def test_successful_non_json_provider_response_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        headers={"content-type": "text/plain"},
        content=b"temporarily unavailable",
    )
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(response, *args, **kwargs),
    )

    with pytest.raises(CommerceError) as exc_info:
        await SwiggyMcpClient("https://provider.invalid").call_tool("get_addresses", {})

    assert exc_info.value.code == "INVALID_PROVIDER_RESPONSE"
    assert "unexpected response" in exc_info.value.message.casefold()
    assert "temporarily unavailable" not in exc_info.value.message


@pytest.mark.asyncio
async def test_sse_provider_response_decodes_json_rpc_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = (
        "event: message\n"
        f"data: {json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {'data': {'addresses': []}}})}\n\n"
    )
    response = httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=body.encode("utf-8"),
    )
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(response, *args, **kwargs),
    )

    result = await SwiggyMcpClient("https://provider.invalid").call_tool(
        "get_addresses", {}
    )

    assert result == {"data": {"addresses": []}}
