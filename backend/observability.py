"""Per-turn tracing as structured log payloads. No message text, phone, or address."""

from __future__ import annotations

import contextvars
import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("grocer.trace")

# Uvicorn leaves the root logger at WARNING, so the trace owns its handler.
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

_trace: contextvars.ContextVar[TurnTrace | None] = contextvars.ContextVar(
    "grocer_turn_trace", default=None
)


@dataclass
class TurnTrace:
    request_id: str
    started: float = field(default_factory=time.monotonic)
    capability: str | None = None
    safety: str | None = None
    swiggy_calls: int = 0
    model_calls: int = 0
    fallbacks: int = 0

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)


def begin_turn(request_id: str) -> TurnTrace:
    trace = TurnTrace(request_id=request_id)
    _trace.set(trace)
    return trace


def current_trace() -> TurnTrace | None:
    return _trace.get()


def set_turn_context(
    *, capability: str | None = None, safety: str | None = None
) -> None:
    trace = current_trace()
    if trace is None:
        return
    if capability is not None:
        trace.capability = capability
    if safety is not None:
        trace.safety = safety


def _emit(event: str, **fields: object) -> None:
    trace = current_trace()
    payload: dict[str, object] = {"event": event}
    if trace is not None:
        payload["request_id"] = trace.request_id
    payload.update(fields)
    logger.info(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))


def record_swiggy_call(tool: str, latency_ms: int, ok: bool) -> None:
    trace = current_trace()
    if trace is not None:
        trace.swiggy_calls += 1
    _emit("swiggy_call", tool=tool, latency_ms=latency_ms, ok=ok)


def record_swiggy_retry(tool: str, wait_seconds: float) -> None:
    _emit("swiggy_retry", tool=tool, wait_seconds=round(wait_seconds, 2))


def record_model_call(provider: str, latency_ms: int, ok: bool) -> None:
    trace = current_trace()
    if trace is not None:
        trace.model_calls += 1
    _emit("model_call", provider=provider, latency_ms=latency_ms, ok=ok)


def record_fallback() -> None:
    trace = current_trace()
    if trace is not None:
        trace.fallbacks += 1


def end_turn(status: str) -> None:
    trace = current_trace()
    if trace is None:
        return
    _emit(
        "turn",
        status=status,
        capability=trace.capability,
        safety=trace.safety,
        latency_ms=trace.elapsed_ms(),
        swiggy_calls=trace.swiggy_calls,
        model_calls=trace.model_calls,
        fallbacks=trace.fallbacks,
    )
    _trace.set(None)
