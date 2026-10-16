"""Sequential safe tool executor.
Maintained for backward compatibility; ReAct loop now uses inline sequential execution.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("grocer.agent.tool_scheduler")

T = TypeVar("T")


async def execute_tool_calls(
    calls: list[dict[str, Any]], execute: Callable[[dict[str, Any]], Awaitable[T]]
) -> list[T]:
    """Execute tool calls sequentially in model order without race conditions."""
    results: list[T] = []
    for call in calls:
        try:
            results.append(await execute(call))
        except Exception as exc:
            tool_name = call.get("name", "unknown")
            logger.warning("Tool execution error for %s: %s", tool_name, exc)
            results.append({  # type: ignore[arg-type]
                "success": False,
                "error": "TOOL_EXECUTION_ERROR",
                "tool": tool_name,
                "message": f"Tool {tool_name} failed: {exc}",
            })
    return results


__all__ = ["execute_tool_calls"]
