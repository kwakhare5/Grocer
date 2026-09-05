"""Recommendations REST API -- spec sections 17, 18 (Human-in-the-loop).

Endpoints:
    POST /api/recommendations/evaluate/{risk_id} -- trigger Decision Engine
    GET  /api/recommendations                    -- list with filters
    GET  /api/recommendations/{id}               -- detail
    POST /api/recommendations/{id}/approve       -- human approval (LOCKED: required for TRANSFER/REORDER/DISCOUNT)
    POST /api/recommendations/{id}/reject        -- operator rejection
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Recommendation
from backend.models.enums import RecommendationStatus
from backend.api.schemas import (
    RecommendationResponse,
    RecommendationEvaluateResponse,
    RecommendationBatchEvaluateResponse,
    RecommendationApproveResponse,
    RecommendationRejectResponse,
)
from backend.services.decision.engine import DecisionOrchestrator

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("/evaluate", response_model=RecommendationBatchEvaluateResponse)
async def batch_evaluate_recommendations(
    db: AsyncSession = Depends(get_db),
) -> RecommendationBatchEvaluateResponse:
    """Run the Decision Engine across all active risks and persist recommendations."""
    orchestrator = DecisionOrchestrator()
    count = await orchestrator.evaluate_all(db)
    await db.commit()
    return RecommendationBatchEvaluateResponse(recommendations_generated=count)


@router.post("/evaluate/{risk_id}", response_model=RecommendationEvaluateResponse)
async def evaluate_recommendation(
    risk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RecommendationEvaluateResponse:
    """Run the Decision Engine for a detected risk and persist the recommendation."""
    orchestrator = DecisionOrchestrator()
    rec = await orchestrator.run(db, risk_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    await db.commit()
    return RecommendationEvaluateResponse(
        recommendation_id=rec.recommendation_id,
        action_type=rec.action_type.value if hasattr(rec.action_type, "value") else str(rec.action_type),
        score=rec.score,
        confidence=rec.confidence,
        reason_codes=rec.reason_codes,
        status=rec.status.value if hasattr(rec.status, "value") else str(rec.status),
    )


@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(
    risk_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    store_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[RecommendationResponse]:
    """List recommendations with optional filters."""
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc()).limit(limit)
    if risk_id:
        stmt = stmt.where(Recommendation.risk_id == risk_id)
    if status:
        stmt = stmt.where(Recommendation.status == status.lower())
    if action_type:
        stmt = stmt.where(Recommendation.action_type == action_type.lower())
    if store_id:
        stmt = stmt.where(
            (Recommendation.source_store_id == store_id)
            | (Recommendation.destination_store_id == store_id)
        )

    result = await db.execute(stmt)
    recs = result.scalars().all()
    return [_to_response(r) for r in recs]


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    """Get a single recommendation by ID."""
    rec = await db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return _to_response(rec)


@router.post("/{recommendation_id}/approve", response_model=RecommendationApproveResponse)
async def approve_recommendation(
    recommendation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RecommendationApproveResponse:
    """Approve a recommendation for execution (spec section 18 -- LOCKED human approval)."""
    orchestrator = DecisionOrchestrator()
    rec = await orchestrator.approve(db, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    await db.commit()
    return RecommendationApproveResponse(
        recommendation_id=rec.recommendation_id,
        status=rec.status.value if hasattr(rec.status, "value") else str(rec.status),
    )


@router.post("/{recommendation_id}/reject", response_model=RecommendationRejectResponse)
async def reject_recommendation(
    recommendation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RecommendationRejectResponse:
    """Reject a recommendation."""
    orchestrator = DecisionOrchestrator()
    rec = await orchestrator.reject(db, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    await db.commit()
    return RecommendationRejectResponse(
        recommendation_id=rec.recommendation_id,
        status=rec.status.value if hasattr(rec.status, "value") else str(rec.status),
    )


def _to_response(rec: Recommendation) -> RecommendationResponse:
    return RecommendationResponse(
        recommendation_id=rec.recommendation_id,
        risk_id=rec.risk_id,
        action_type=rec.action_type.value if hasattr(rec.action_type, "value") else str(rec.action_type),
        quantity=rec.quantity,
        source_store_id=rec.source_store_id,
        destination_store_id=rec.destination_store_id,
        score=rec.score,
        confidence=rec.confidence,
        reason_codes=rec.reason_codes,
        alternatives=rec.alternatives,
        status=rec.status.value if hasattr(rec.status, "value") else str(rec.status),
        created_at=rec.created_at,
    )
