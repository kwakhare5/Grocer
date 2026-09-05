"""Agent Execution REST API -- spec sections 19-21.

Endpoints:
    POST /api/agent/execute/{recommendation_id}
        -- Trigger the LangGraph execution agent for an APPROVED recommendation.
        -- Returns a RunResult describing the outcome.

    GET  /api/agent/runs/{run_id}
        -- Return the status of a previous run (stored in-memory cache for this session).
        -- In production this would be backed by a persistent run-log table.

Safety invariants (spec section 18 LOCKED):
    - The recommendation MUST be in APPROVED status. The agent validates this internally.
    - Any new consequential action after world changes requires fresh human approval.
    - This endpoint will NOT execute a pending or rejected recommendation.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Recommendation
from backend.models.enums import RecommendationStatus
from backend.agents.execution.runner import ExecutionRunner, RunResult
from backend.api.schemas import AgentRunResponse, AgentRunStatusResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])

# In-memory run cache (keyed by run_id str -> RunResult).
# In production: replace with an AgentRun ORM table.
_run_cache: dict[str, RunResult] = {}


@router.post("/execute/{recommendation_id}", response_model=AgentRunResponse)
async def execute_recommendation(
    recommendation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Trigger the LangGraph execution agent for an APPROVED recommendation.

    Returns 404 if the recommendation does not exist.
    Returns 409 if the recommendation is not in APPROVED status.
    Returns 200 with the full RunResult on success or graceful failure.
    """
    # Pre-flight: verify the recommendation exists and is approved
    # (the agent also validates internally, but we surface 404/409 cleanly here)
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec_status = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
    if rec_status != "approved":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Recommendation is in status '{rec_status}', expected 'approved'. "
                "Human approval is required before agent execution (spec section 18 LOCKED)."
            ),
        )

    runner = ExecutionRunner()
    result: RunResult = await runner.run(db, recommendation_id)

    # Commit DB changes made during the run (transfers, reorders, event audit rows)
    await db.commit()

    # Cache the result for subsequent GET /api/agent/runs/{run_id}
    _run_cache[str(result.run_id)] = result

    return AgentRunResponse(
        run_id=str(result.run_id),
        recommendation_id=str(result.recommendation_id),
        status=result.status,
        action_type=result.action_type,
        events=result.events,
        error=result.error,
        new_recommendation_id=str(result.new_recommendation_id) if result.new_recommendation_id else None,
        requires_human_review=result.requires_human_review,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


@router.get("/runs", response_model=list[AgentRunStatusResponse])
async def list_runs() -> list[AgentRunStatusResponse]:
    """Return all recent agent runs in reverse chronological order."""
    return [
        AgentRunStatusResponse(
            run_id=str(r.run_id),
            status=r.status,
            recommendation_id=str(r.recommendation_id),
        )
        for r in reversed(list(_run_cache.values()))
    ]


@router.get("/runs/{run_id}", response_model=AgentRunStatusResponse)
async def get_run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentRunStatusResponse:
    """Return the status of a previous agent run.

    Returns 404 if the run_id is not found in the session cache.
    """
    result = _run_cache.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent run not found")

    return AgentRunStatusResponse(
        run_id=str(result.run_id),
        status=result.status,
        recommendation_id=str(result.recommendation_id),
    )
