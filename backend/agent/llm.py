"""Grocer v1.0 — Provider-Agnostic LLM Adapter (ADR 0012).

One JSON-mode completion call. Callers never talk to a provider directly, and
no provider is allowed to call Swiggy. Swapping the brain is an env change.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger("grocer.llm")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
RETRY_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class LLMResult:
    """One completion, parsed as JSON, with the provider that produced it."""

    data: dict[str, Any] | None
    provider: str
    model: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


def _groq_json(system_prompt: str, user_prompt: str) -> LLMResult:
    if not settings.GROQ_API_KEY:
        return LLMResult(None, "groq", settings.GROQ_MODEL, "GROQ_API_KEY is not set")

    payload = {
        "model": settings.GROQ_MODEL,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    last_error = "groq request failed"
    for attempt in range(2):
        try:
            response = httpx.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
            if response.status_code in RETRYABLE_STATUS and attempt == 0:
                last_error = f"HTTP {response.status_code}"
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise TypeError("Groq returned JSON that is not an object")
            return LLMResult(parsed, "groq", settings.GROQ_MODEL)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = str(exc)
            if attempt == 0:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.warning("Groq completion failed on %s: %s", settings.GROQ_MODEL, last_error)
    return LLMResult(None, "groq", settings.GROQ_MODEL, last_error)


def _gemini_json(system_prompt: str, user_prompt: str) -> LLMResult:
    if not settings.GEMINI_API_KEY:
        return LLMResult(None, "gemini", settings.GEMINI_MODEL, "GEMINI_API_KEY is not set")
    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
    except ImportError as exc:
        return LLMResult(None, "gemini", settings.GEMINI_MODEL, str(exc))

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    for model_name in (settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            if response.text:
                parsed = json.loads(response.text)
                if not isinstance(parsed, dict):
                    raise TypeError("Gemini returned JSON that is not an object")
                return LLMResult(parsed, "gemini", model_name)
        except (APIError, OSError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Gemini completion failed on %s: %s", model_name, exc)
    return LLMResult(None, "gemini", settings.GEMINI_MODEL, "gemini unavailable")


def complete_json(
    system_prompt: str,
    user_prompt: str,
    provider: str | None = None,
) -> LLMResult:
    """Return one JSON completion from the configured provider.

    No silent cross-provider fallback: a failed call is reported as failed so
    tests and evaluation can attribute results to the model that produced them.
    """
    chosen = (provider or settings.LLM_PROVIDER or "groq").strip().lower()
    if chosen == "gemini":
        return _gemini_json(system_prompt, user_prompt)
    if chosen == "groq":
        return _groq_json(system_prompt, user_prompt)
    return LLMResult(None, chosen, "", f"unknown LLM provider: {chosen}")
