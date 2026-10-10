"""Run independent commerce reads together and all effects in model order."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("grocer.agent.tool_scheduler")

T = TypeVar("T")

_READ_TOOLS = {
    "get_saved_addresses",
    "get_go_to_items",
    "search_products",
    "get_cart",
    "track_order",
    "check_replenishment",
}


async def _safe_execute(call: dict[str, Any], execute: Callable[[dict[str, Any]], Awaitable[T]]) -> T | dict[str, Any]:
    try:
        return await execute(call)
    except Exception as exc:
        tool_name = call.get("name", "unknown")
        logger.warning("Tool execution error for %s: %s", tool_name, exc)
        return {
            "success": False,
            "error": "TOOL_EXECUTION_ERROR",
            "tool": tool_name,
            "message": f"Tool {tool_name} failed: {exc}",
        }


async def execute_tool_calls(
    calls: list[dict[str, Any]], execute: Callable[[dict[str, Any]], Awaitable[T]]
) -> list[T]:
    results: list[T] = []
    reads: list[dict[str, Any]] = []
    for call in calls:
        if call.get("name") in _READ_TOOLS:
            reads.append(call)
            continue
        if reads:
            raw_res = await asyncio.gather(*(_safe_execute(read, execute) for read in reads))
            results.extend(raw_res)
            reads.clear()
        results.append(await _safe_execute(call, execute))
    if reads:
        raw_res = await asyncio.gather(*(_safe_execute(read, execute) for read in reads))
        results.extend(raw_res)
    return results
