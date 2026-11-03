"""Grocer — Swiggy client error envelopes.

A business error from Swiggy must surface as a tool error, never as a malformed
cart. The HTTP boundary is stubbed; no live Swiggy call is made.
"""

from __future__ import annotations

from typing import ClassVar, Self

import httpx
import pytest

from backend.integrations.commerce.swiggy_client import (
    SwiggyClient,
    SwiggyToolError,
    tool_error_message,
)


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    payload: ClassVar[dict] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def post(self, *args, **kwargs) -> _FakeResponse:
        return _FakeResponse(self.payload)


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
    _FakeClient.payload = {
        "result": {
            "structuredContent": {
                "success": False,
                "error": "Please review your cart.",
            }
        }
    }
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    with pytest.raises(SwiggyToolError, match="review your cart"):
        SwiggyClient(auth_token="test").get_cart()
