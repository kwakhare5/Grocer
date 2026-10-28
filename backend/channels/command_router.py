"""Grocer — Deterministic Inbound Command Router (Layer 1 -> Layer 4).

Decouples deterministic administrative and privacy commands (e.g., 'delete my data')
from the raw transport webhook ingress.
"""

from __future__ import annotations

from typing import Any

from backend.agent.dpdp import handle_delete_my_data


async def dispatch_text_command(
    text: str,
    user_id: str,
    conn: Any,
) -> dict[str, Any] | None:
    """Evaluate inbound text for deterministic administrative or privacy commands."""
    normalized = text.strip().lower()
    if normalized == "delete my data":
        return await handle_delete_my_data(conn, user_id)
    return None
