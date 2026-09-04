"""Agent execution state -- TypedDict for LangGraph (spec section 19).

AgentState flows through every node and is the single source of truth
for the execution graph. All nodes read from and write to this dict.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Full state for the execution agent graph.

    Required on entry:
        recommendation_id: UUID of the APPROVED recommendation to execute.
        db: async SQLAlchemy session (injected at graph entry).

    Written by validate node:
        recommendation: dict snapshot of the rec row.
        error: non-empty string if validation fails.

    Written by pre_check node:
        pre_check_passed: True iff world state still matches original recommendation.
        pre_check_error: human-readable reason if pre_check failed.
        stale_inventory: True if source inventory changed enough to invalidate rec.

    Written by execute node:
        execution_result: dict describing what was mutated.
        execution_error: non-empty string if execution failed (technical error).

    Written by verify node:
        verified: True if DB state reflects the intended outcome.
        verify_error: non-empty string if verification failed.

    Written by finalize node:
        status: one of "completed" | "requires_human_review" | "failed"
        events: list of event dicts emitted during this run.

    Written by recover node:
        recovery_action: what the recover node decided (e.g. "recalculated")
        new_recommendation_id: UUID if a new rec was generated.
        requires_human_review: True (always)
    """
    recommendation_id: uuid.UUID
    db: Any                              # AsyncSession; not typed to avoid import

    recommendation: Optional[dict]       # snapshot of the Recommendation row
    error: Optional[str]                 # fatal validation error

    pre_check_passed: bool
    pre_check_error: Optional[str]
    stale_inventory: bool

    execution_result: Optional[dict]
    execution_error: Optional[str]

    verified: bool
    verify_error: Optional[str]

    status: str                          # "completed" | "requires_human_review" | "failed"
    events: list[dict]

    recovery_action: Optional[str]
    new_recommendation_id: Optional[uuid.UUID]
    requires_human_review: bool
