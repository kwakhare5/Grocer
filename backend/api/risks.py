"""Risk REST API — spec §32.

Endpoints:
    GET  /api/risks                  — list risks with optional filters (store_id, product_id, risk_type, severity, status)
    GET  /api/risks/{risk_id}        — get risk details
    POST /api/risks/evaluate         — trigger risk engine evaluation
    POST /api/risks/{risk_id}/resolve — resolve an active risk
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Risk
from backend.models.enums import RiskType, RiskSeverity, RiskStatus
from backend.api.schemas import (
    RiskResponse,
    RiskEvaluateResponse,
    RiskResolveResponse,
)
from backend.services.risk.engine import RiskEngine

router = APIRouter(prefix="/api/risks", tags=["risks"])


@router.get("", response_model=list[RiskResponse])
async def list_risks(
    store_id: Optional[uuid.UUID] = Query(None),
    product_id: Optional[uuid.UUID] = Query(None),
    risk_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[RiskResponse]:
    """List all detected risks with optional filtering."""
    stmt = select(Risk).order_by(Risk.created_at.desc()).limit(limit)
    if store_id:
        stmt = stmt.where(Risk.store_id == store_id)
    if product_id:
        stmt = stmt.where(Risk.product_id == product_id)
    if risk_type:
        stmt = stmt.where(Risk.risk_type == risk_type)
    if severity:
        stmt = stmt.where(Risk.severity == severity)
    if status:
        stmt = stmt.where(Risk.status == status)

    result = await db.execute(stmt)
    risks = result.scalars().all()
    return [
        RiskResponse(
            risk_id=r.risk_id,
            store_id=r.store_id,
            product_id=r.product_id,
            risk_type=r.risk_type.value if hasattr(r.risk_type, "value") else str(r.risk_type),
            severity=r.severity.value if hasattr(r.severity, "value") else str(r.severity),
            probability=r.probability,
            expected_time=r.expected_time,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            created_at=r.created_at,
        )
        for r in risks
    ]


@router.get("/{risk_id}", response_model=RiskResponse)
async def get_risk(
    risk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RiskResponse:
    """Get a single risk by ID."""
    risk = await db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return RiskResponse(
        risk_id=risk.risk_id,
        store_id=risk.store_id,
        product_id=risk.product_id,
        risk_type=risk.risk_type.value if hasattr(risk.risk_type, "value") else str(risk.risk_type),
        severity=risk.severity.value if hasattr(risk.severity, "value") else str(risk.severity),
        probability=risk.probability,
        expected_time=risk.expected_time,
        status=risk.status.value if hasattr(risk.status, "value") else str(risk.status),
        created_at=risk.created_at,
    )


@router.post("/evaluate", response_model=RiskEvaluateResponse)
async def evaluate_risks(
    db: AsyncSession = Depends(get_db),
) -> RiskEvaluateResponse:
    """Trigger the RiskEngine to scan inventory & batches and generate risks."""
    engine = RiskEngine()
    count = await engine.run(db)
    await db.commit()
    return RiskEvaluateResponse(risks_detected=count)


@router.post("/{risk_id}/resolve", response_model=RiskResolveResponse)
async def resolve_risk(
    risk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RiskResolveResponse:
    """Resolve an existing risk."""
    engine = RiskEngine()
    risk = await engine.resolve(db, risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    await db.commit()
    return RiskResolveResponse(risk_id=risk.risk_id, status=risk.status.value)
