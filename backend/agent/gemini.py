"""Isolated Native Gemini API client for GROCER."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)


class GeminiClient:
    """Async client communicating directly with Google's native generateContent API."""

    def __init__(
        self,
        api_key: str,
        primary_model: str = "gemini-3.5-flash-lite",
        fallback_model: str = "gemini-3.5-flash-lite",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._last_call_time: float = 0.0

    async def get_http_client(self) -> httpx.AsyncClient:
        """Reuse persistent HTTP/2 connection pool."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def close(self) -> None:
        """Close persistent HTTP connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate_content(
        self,
        contents: list[dict[str, Any]],
        system_text: str,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> Optional[dict[str, Any]]:
        """Call Gemini generateContent with automatic model fallback and rate-limit backoff."""
        if not self.api_key:
            logger.error("No Gemini API key configured.")
            return None

        # Rate throttle (minimum 200ms spacing between turns)
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_call_time
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)
        self._last_call_time = asyncio.get_running_loop().time()

        models = [self.primary_model, self.fallback_model]
        client = await self.get_http_client()

        cleaned_contents = []
        for entry in contents:
            if not isinstance(entry, dict) or "parts" not in entry:
                continue
            cleaned_parts = []
            _allowed_keys = {
                "text", "functionCall", "functionResponse",
                "thoughtSignature", "thought_signature", "thought",
            }
            for part in entry.get("parts", []):
                if not isinstance(part, dict):
                    continue
                cleaned_part = {k: v for k, v in part.items() if k in _allowed_keys}
                if cleaned_part:
                    cleaned_parts.append(cleaned_part)
            if cleaned_parts:
                cleaned_contents.append({
                    "role": entry.get("role", "user"),
                    "parts": cleaned_parts,
                })

        # Enforce strict Gemini alternating role requirements (user -> model -> user -> model)
        alternated_contents = []
        for entry in cleaned_contents:
            if alternated_contents and alternated_contents[-1]["role"] == entry["role"]:
                alternated_contents[-1]["parts"].extend(entry["parts"])
            else:
                alternated_contents.append(entry)

        while alternated_contents and alternated_contents[0]["role"] != "user":
            alternated_contents.pop(0)

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": alternated_contents,
            "generationConfig": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        for attempt, model in enumerate(models):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (429, 503, 404):
                    logger.warning(
                        "Gemini %s returned %d on attempt %d; pivoting to fallback...",
                        model, resp.status_code, attempt + 1
                    )
                    await asyncio.sleep(0.5)
                    continue

                if resp.status_code == 400:
                    logger.warning("Gemini HTTP 400 on payload: %s", resp.text[:400])
                    if len(contents) > 1:
                        logger.warning("HTTP 400 on multi-turn history. Retrying text-only parts...")
                    salvaged = [
                        {
                            "role": entry.get("role"),
                            "parts": [p for p in entry.get("parts", []) if "text" in p]
                        }
                        for entry in contents
                    ]
                    salvaged = [entry for entry in salvaged if entry["parts"]]
                    retry_payload = dict(payload)
                    retry_payload["contents"] = salvaged
                    resp = await client.post(url, json=retry_payload, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    if "candidates" in data:
                        return data

                logger.error("Gemini %s error: %d %s", model, resp.status_code, resp.text[:200])
            except Exception as exc:
                logger.error("Gemini call exception on model %s: %r", model, exc)
                if attempt + 1 < len(models):
                    await asyncio.sleep(0.5)
                    continue
                return None

        return None
