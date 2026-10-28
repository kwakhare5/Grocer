"""Grocer v1.0 — Provider-Agnostic LLM Adapter (ADR 0012).

One JSON-mode completion call. Callers never talk to a provider directly, and
no provider is allowed to call Swiggy. Swapping the brain is an env change.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger("grocer.llm")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
RETRY_DELAY_SECONDS = 1.0
MIN_CALL_INTERVAL_SECONDS = 0.75

_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h)")
_RETRY_MESSAGE = re.compile(r"try again in ([\d.]+)\s*(ms|s|m)", re.IGNORECASE)


def _parse_duration_seconds(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    total = 0.0
    found = False
    for value, unit in _DURATION_PART.findall(text):
        found = True
        total += float(value) * {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}[unit]
    return total if found else None


def _retry_wait_seconds(response: httpx.Response) -> float:
    """How long Groq wants us to wait, from headers or the error message."""
    for header in (
        "retry-after",
        "x-ratelimit-reset-tokens",
        "x-ratelimit-reset-requests",
    ):
        seconds = _parse_duration_seconds(response.headers.get(header))
        if seconds is not None:
            return min(60.0, max(0.5, seconds))
    try:
        message = str(response.json().get("error", {}).get("message") or "")
    except ValueError:
        message = ""
    match = _RETRY_MESSAGE.search(message)
    if match:
        seconds = float(match.group(1)) * (0.001 if match.group(2) == "ms" else 1.0)
        return min(60.0, max(0.5, seconds))
    return RETRY_DELAY_SECONDS


class _GroqGate:
    """One queue for every Groq call, shared by routing and item evaluation.

    Calls are spaced, and a 429 or a zero-token header parks every thread until
    the reset instead of hammering the free tier.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_allowed = 0.0
        self._blocked_until = 0.0

    def wait(self, deadline: float | None = None) -> bool:
        with self._lock:
            now = time.monotonic()
            target = max(now, self._next_allowed, self._blocked_until)
            if deadline is not None and target >= deadline:
                return False
            self._next_allowed = target + MIN_CALL_INTERVAL_SECONDS
        if target > now:
            time.sleep(target - now)
        return True

    def block_for(self, seconds: float) -> None:
        with self._lock:
            self._blocked_until = max(
                self._blocked_until, time.monotonic() + max(0.0, seconds)
            )

    def observe(self, headers: Any) -> None:
        remaining = headers.get("x-ratelimit-remaining-tokens")
        if remaining is None:
            return
        try:
            left = int(float(remaining))
        except (TypeError, ValueError):
            return
        if left <= 0:
            reset = _parse_duration_seconds(headers.get("x-ratelimit-reset-tokens"))
            if reset is not None:
                self.block_for(reset)


_GROQ_GATE = _GroqGate()


@dataclass(frozen=True)
class LLMResult:
    """One completion, parsed as JSON, with the provider that produced it."""

    data: dict[str, Any] | None
    provider: str
    error: str | None = None
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.data is not None


def _groq_json(system_prompt: str, user_prompt: str) -> LLMResult:
    if not settings.GROQ_API_KEY:
        return LLMResult(None, "groq", "GROQ_API_KEY is not set")

    payload = {
        "model": settings.GROQ_MODEL,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    started = time.monotonic()
    deadline = started + settings.LLM_TIMEOUT_SECONDS
    last_error = "groq request failed"
    for attempt in range(2):
        if not _GROQ_GATE.wait(deadline):
            last_error = "rate limit wait exceeded the turn budget"
            break
        remaining = deadline - time.monotonic()
        if remaining < 1.0:
            break
        try:
            response = httpx.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload,
                timeout=remaining,
            )
            _GROQ_GATE.observe(response.headers)
            if response.status_code in RETRYABLE_STATUS and attempt == 0:
                last_error = f"HTTP {response.status_code}"
                _GROQ_GATE.block_for(_retry_wait_seconds(response))
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise TypeError("Groq returned JSON that is not an object")
            latency_ms = int((time.monotonic() - started) * 1000)
            return LLMResult(parsed, "groq", latency_ms=latency_ms)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = str(exc)
            # A bad key or a bad request will not improve on a second attempt.
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in RETRYABLE_STATUS:
                break
            if attempt == 0:
                time.sleep(min(RETRY_DELAY_SECONDS, max(0.0, deadline - time.monotonic())))

    latency_ms = int((time.monotonic() - started) * 1000)
    logger.warning(
        "Groq completion failed on %s after %sms: %s",
        settings.GROQ_MODEL,
        latency_ms,
        last_error,
    )
    return LLMResult(None, "groq", last_error, latency_ms=latency_ms)


def _gemini_json(system_prompt: str, user_prompt: str) -> LLMResult:
    if not settings.GEMINI_API_KEY:
        return LLMResult(None, "gemini", "GEMINI_API_KEY is not set")
    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
    except ImportError as exc:
        return LLMResult(None, "gemini", str(exc))

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
                return LLMResult(parsed, "gemini")
        except (APIError, OSError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Gemini completion failed on %s: %s", model_name, exc)
    return LLMResult(None, "gemini", "gemini unavailable")


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
    return LLMResult(None, chosen, f"unknown LLM provider: {chosen}")
