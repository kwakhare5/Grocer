"""Focused tests for the Gemini shopping-task language boundary."""
from __future__ import annotations

import json

import httpx
import pytest

from backend.intent.model_understanding import GeminiMessageUnderstandingService
from backend.intent.task_model import TaskOperation


def _gemini_response(payload: dict[str, object]) -> dict[str, object]:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(payload)}],
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_interpret_uses_context_and_returns_validated_model_result() -> None:
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "operation": "KEEP_ONLY_ITEMS",
                    "items": [
                        {
                            "name": "milk",
                            "quantity": 1,
                            "unit": "units",
                            "preference_source": "explicit",
                            "quantity_is_explicit": False,
                            "resolution_status": "UNRESOLVED",
                        },
                        {
                            "name": "bread",
                            "quantity": 1,
                            "unit": "units",
                            "preference_source": "explicit",
                            "quantity_is_explicit": False,
                            "resolution_status": "UNRESOLVED",
                        },
                    ],
                    "target_item": None,
                    "quantity": None,
                    "selection_value": None,
                    "selected_sku_id": None,
                    "confidence": 0.97,
                    "ambiguities": [],
                    "missing_details": [],
                    "source": "model",
                }
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = GeminiMessageUnderstandingService(api_key="test-key", client=client)
        result = await service.interpret(
            "cancel the others, just keep milk and bread",
            context={
                "state": "AWAITING_CHECKOUT_CONFIRMATION",
                "basket": ["milk", "bread", "coke"],
                "pending_question": "Confirm this order?",
            },
        )

    assert result is not None
    assert result.operation == TaskOperation.KEEP_ONLY_ITEMS
    assert [item.name for item in result.items] == ["milk", "bread"]
    assert result.source == "model"
    assert captured_request is not None
    sent = json.loads(captured_request.content)
    prompt = sent["contents"][0]["parts"][0]["text"]
    assert "AWAITING_CHECKOUT_CONFIRMATION" in prompt
    assert "Confirm this order?" in prompt
    assert sent["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in sent["generationConfig"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_payload",
    [
        {},
        {"candidates": []},
        _gemini_response({"operation": "NOT_AN_OPERATION", "confidence": 1}),
        {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]},
    ],
)
async def test_interpret_returns_none_for_invalid_model_responses(
    response_payload: dict[str, object],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = GeminiMessageUnderstandingService(api_key="test-key", client=client)
        assert await service.interpret("hello", context={"state": "READY"}) is None


@pytest.mark.asyncio
async def test_interpret_returns_none_for_low_confidence() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "operation": "CLARIFY",
                    "confidence": 0.4,
                    "ambiguities": ["Unclear reference"],
                    "missing_details": [],
                    "source": "model",
                }
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = GeminiMessageUnderstandingService(api_key="test-key", client=client)
        assert await service.interpret("do that", context={}) is None


@pytest.mark.asyncio
async def test_interpret_returns_none_for_network_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = GeminiMessageUnderstandingService(api_key="test-key", client=client)
        assert await service.interpret("add milk", context={}) is None


@pytest.mark.asyncio
async def test_interpret_skips_network_without_key_or_message() -> None:
    called = False

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = GeminiMessageUnderstandingService(api_key=None, client=client)
        service._api_key = None
        assert await service.interpret("add milk", context={}) is None

        keyed_service = GeminiMessageUnderstandingService(api_key="test-key", client=client)
        assert await keyed_service.interpret("   ", context={}) is None

    assert called is False
