"""Grocer — Swiggy client error envelopes and retry behavior.

A business error from Swiggy must surface as a tool error, never as a malformed
cart. The HTTP boundary is stubbed; no live Swiggy call is made.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Self

import httpx
import pytest

from backend.integrations.commerce.swiggy_client import (
    SwiggyClient,
    SwiggyToolError,
    tool_error_message,
)


class _FakeResponse:
    def __init__(
        self,
        payload: dict,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://mcp.swiggy.com/im")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    responses: ClassVar[list[_FakeResponse]] = []
    posts: ClassVar[int] = 0

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def post(self, *args, **kwargs) -> _FakeResponse:
        type(self).posts += 1
        return type(self).responses.pop(0)


def _cart_payload() -> dict:
    return json.loads(
        (Path(__file__).parent / "fixtures" / "get_cart.json").read_text(
            encoding="utf-8"
        )
    )


def test_tool_error_message_reads_string_and_dict_errors():
    assert (
        tool_error_message({"success": False, "error": "Please review your cart."})
        == "Please review your cart."
    )
    assert (
        tool_error_message({"success": False, "error": {"message": "Store closed"}})
        == "Store closed"
    )
    assert tool_error_message({"success": True, "data": {}}) is None


def test_structured_cart_error_raises_tool_error(monkeypatch):
    _FakeClient.responses = [
        _FakeResponse(
            {
                "result": {
                    "structuredContent": {
                        "success": False,
                        "error": "Please review your cart.",
                    }
                }
            }
        )
    ]
    _FakeClient.posts = 0
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    with pytest.raises(SwiggyToolError, match="review your cart"):
        SwiggyClient(auth_token="test").get_cart()


def test_429_is_retried_with_retry_after(monkeypatch):
    _FakeClient.responses = [
        _FakeResponse({}, status_code=429, headers={"retry-after": "0"}),
        _FakeResponse(_cart_payload()),
    ]
    _FakeClient.posts = 0
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    cart = SwiggyClient(auth_token="test").get_cart()

    assert cart.items[0].spinId == "spin_amul_1l"
    assert _FakeClient.posts == 2


def test_gateway_cap_is_retried_with_retry_after(monkeypatch):
    _FakeClient.responses = [
        _FakeResponse(
            {"error": {"code": -32000, "message": "gateway cap"}},
            headers={"retry-after": "0"},
        ),
        _FakeResponse(_cart_payload()),
    ]
    _FakeClient.posts = 0
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    cart = SwiggyClient(auth_token="test").get_cart()

    assert cart.items[0].spinId == "spin_amul_1l"
    assert _FakeClient.posts == 2


def test_second_429_is_an_honest_tool_error(monkeypatch):
    _FakeClient.responses = [
        _FakeResponse({}, status_code=429, headers={"retry-after": "0"}),
        _FakeResponse({}, status_code=429, headers={"retry-after": "0"}),
    ]
    _FakeClient.posts = 0
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    with pytest.raises(SwiggyToolError, match="busy"):
        SwiggyClient(auth_token="test").get_cart()

    assert _FakeClient.posts == 2
