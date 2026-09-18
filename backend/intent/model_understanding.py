"""Context-aware Gemini interpreter for bounded shopping-task operations.

The model only proposes a ``MessageUnderstanding``.  The deterministic reducer
remains responsible for validating transitions and authorizing commerce work.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import ValidationError

from backend.config import settings
from backend.intent.task_model import MessageUnderstanding


logger = logging.getLogger(__name__)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
_SYSTEM_INSTRUCTION = """You interpret one English message for a grocery-ordering agent.
Return exactly one operation using the supplied JSON schema. Use the conversation context,
especially the current state, pending question, basket, and visible choices. Never invent a
product, quantity, choice ID, address ID, payment ID, or SKU. Preserve the customer's wording
for item names. When meaning is uncertain, return CLARIFY and explain the ambiguity or missing
detail. You only interpret language; you never claim that a provider action succeeded and never
authorize checkout. A greeting is ASK_FOR_HELP. A confirmation applies only to the confirmation
currently requested by the context. Set source to model."""


class GeminiMessageUnderstandingService:
    """Request a schema-constrained, non-authoritative interpretation from Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = "gemini-3.5-flash-lite",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 12.0,
        min_confidence: float = 0.8,
    ) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model = model
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._min_confidence = min_confidence

    async def interpret(
        self,
        message: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> MessageUnderstanding | None:
        """Return a validated proposal, or ``None`` when the model is unsafe to use."""
        if not self._api_key or not message.strip():
            return None

        payload = self._payload(message, context or {})
        try:
            if self._client is not None:
                response = await self._post(self._client, payload)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await self._post(client, payload)
            response.raise_for_status()
            understanding = self._parse_response(response.json())
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError, ValidationError):
            # Do not log the exception: HTTP request representations can contain
            # the API key query parameter.
            logger.warning("Gemini message interpretation failed")
            return None

        if understanding.confidence < self._min_confidence:
            return None
        return understanding

    async def _post(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> httpx.Response:
        url = f"{_API_ROOT}/{self._model}:generateContent"
        return await client.post(
            url,
            params={"key": self._api_key},
            json=payload,
            timeout=self._timeout_seconds,
        )

    @staticmethod
    def _payload(message: str, context: Mapping[str, Any]) -> dict[str, Any]:
        context_json = json.dumps(context, ensure_ascii=False, default=str)
        return {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Conversation context:\n{context_json}\n\n"
                                f"Customer message:\n{message.strip()}"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "responseJsonSchema": MessageUnderstanding.model_json_schema(),
            },
        }

    @staticmethod
    def _parse_response(data: Mapping[str, Any]) -> MessageUnderstanding:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Gemini response has no candidates")
        candidate = candidates[0]
        if not isinstance(candidate, Mapping):
            raise TypeError("Gemini candidate is not an object")
        content = candidate.get("content")
        if not isinstance(content, Mapping):
            raise TypeError("Gemini candidate has no content")
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts or not isinstance(parts[0], Mapping):
            raise TypeError("Gemini candidate has no text part")
        text = parts[0].get("text")
        if not isinstance(text, str):
            raise TypeError("Gemini candidate text is invalid")

        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise TypeError("Gemini structured output is not an object")
        raw["source"] = "model"
        return MessageUnderstanding.model_validate(raw)
