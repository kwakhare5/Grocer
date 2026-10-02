"""Run independent commerce reads together and all effects in model order."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

_READ_TOOLS = {"get_saved_addresses", "get_go_to_items", "search_products", "get_cart", "track_order"}


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
            results.extend(await asyncio.gather(*(execute(read) for read in reads)))
            reads.clear()
        results.append(await execute(call))
    if reads:
        results.extend(await asyncio.gather(*(execute(read) for read in reads)))
    return results
