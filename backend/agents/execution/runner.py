"""Agent ExecutionRunner -- async entry point for the execution graph.

Usage:
    runner = ExecutionRunner()
    result = await runner.run(db, recommendation_id)

The runner:
1. Builds the initial AgentState.
2. Invokes the LangGraph execution graph via .ainvoke().
3. Commits the DB session on success.
4. Returns a typed RunResult describing the outcome.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.execution.graph import execution_graph
from backend.agents.execution.state import AgentState


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class RunResult:
    """Typed result returned by ExecutionRunner.run()."""

    run_id: uuid.UUID
    recommendation_id: uuid.UUID
    status: str                          # "completed" | "requires_human_review" | "failed"
    action_type: Optional[str]
    events: list[dict]
    error: Optional[str]
    new_recommendation_id: Optional[uuid.UUID]
    requires_human_review: bool
    started_at: datetime
    finished_at: datetime

    def to_dict(self) -> dict:
        return {
            "run_id":                 str(self.run_id),
            "recommendation_id":      str(self.recommendation_id),
            "status":                 self.status,
            "action_type":            self.action_type,
            "events":                 self.events,
            "error":                  self.error,
            "new_recommendation_id":  str(self.new_recommendation_id) if self.new_recommendation_id else None,
            "requires_human_review":  self.requires_human_review,
            "started_at":             self.started_at.isoformat(),
            "finished_at":            self.finished_at.isoformat(),
        }


class ExecutionRunner:
    """Async runner that drives the LangGraph execution graph for a single recommendation."""

    async def run(self, db: AsyncSession, recommendation_id: uuid.UUID) -> RunResult:
        """Run the execution graph for the given recommendation.

        Returns a RunResult regardless of success/failure.
        Callers are responsible for committing the session after this method returns.
        """
        run_id    = uuid.uuid4()
        started   = _naive_now()

        # Build initial state
        initial_state: AgentState = {
            "recommendation_id":  recommendation_id,
            "db":                 db,
            "recommendation":     None,
            "error":              None,
            "pre_check_passed":   True,
            "stale_inventory":    False,
            "pre_check_error":    None,
            "execution_result":   None,
            "execution_error":    None,
            "verified":           False,
            "verify_error":       None,
            "status":             "running",
            "events":             [],
            "recovery_action":    None,
            "new_recommendation_id": None,
            "requires_human_review": False,
        }

        # Run the graph
        final_state: AgentState = await execution_graph.ainvoke(initial_state)

        finished = _naive_now()

        # Extract action_type from the recommendation snapshot
        rec_snap = final_state.get("recommendation") or {}
        action_type = rec_snap.get("action_type")

        new_rec_id_raw = final_state.get("new_recommendation_id")
        new_rec_id = new_rec_id_raw if isinstance(new_rec_id_raw, uuid.UUID) else (
            uuid.UUID(str(new_rec_id_raw)) if new_rec_id_raw else None
        )

        return RunResult(
            run_id=run_id,
            recommendation_id=recommendation_id,
            status=final_state.get("status", "failed"),
            action_type=action_type,
            events=final_state.get("events", []),
            error=final_state.get("error") or final_state.get("execution_error"),
            new_recommendation_id=new_rec_id,
            requires_human_review=final_state.get("requires_human_review", False),
            started_at=started,
            finished_at=finished,
        )
