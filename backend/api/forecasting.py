"""Forecast REST API — spec §32.

Endpoints:
    GET  /api/forecasts              — list forecasts (with filters)
    POST /api/forecasts/generate     — trigger forecast generation
    GET  /api/forecasts/evaluate     — compare baseline vs exp_smoothing metrics
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Forecast
from backend.api.schemas import (
    ForecastResponse,
    ForecastGenerateRequest,
    ForecastEvaluationResponse,
)
from backend.services.forecasting.engine import ForecastingEngine
from backend.services.forecasting.models import evaluate_forecast

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


@router.get("", response_model=list[ForecastResponse])
async def list_forecasts(
    store_id: Optional[uuid.UUID] = Query(None),
    product_id: Optional[uuid.UUID] = Query(None),
    model_name: Optional[str] = Query(None),
    horizon_hours: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[ForecastResponse]:
    """List all forecasts, optionally filtered by store, product, model, or horizon."""
    stmt = select(Forecast).order_by(Forecast.created_at.desc()).limit(limit)
    if store_id:
        stmt = stmt.where(Forecast.store_id == store_id)
    if product_id:
        stmt = stmt.where(Forecast.product_id == product_id)
    if model_name:
        stmt = stmt.where(Forecast.model_name == model_name)
    if horizon_hours:
        stmt = stmt.where(Forecast.forecast_window_hours == horizon_hours)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/generate", response_model=dict)
async def generate_forecasts(
    req: ForecastGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger forecast generation across single or multiple horizons."""
    engine = ForecastingEngine()
    horizons = req.horizons or ([req.horizon_hours] if req.horizon_hours is not None else [24])
    count = await engine.run(db, horizons=horizons)
    await db.commit()
    return {
        "forecasts_generated": count,
        "horizon_hours": horizons[0] if len(horizons) == 1 else None,
        "horizons": horizons,
    }


@router.get("/evaluate", response_model=list[ForecastEvaluationResponse])
async def evaluate_models(
    db: AsyncSession = Depends(get_db),
) -> list[ForecastEvaluationResponse]:
    """Compare baseline vs exp_smoothing model accuracy against simulator ground truth orders."""
    engine = ForecastingEngine()
    eval_dict = await engine.evaluate_on_history(db, holdout_days=3)

    evaluations: list[ForecastEvaluationResponse] = []
    for model_name, res in eval_dict.items():
        evaluations.append(
            ForecastEvaluationResponse(
                model_name=model_name,
                mae=res.mae,
                rmse=res.rmse,
                mape=res.mape,
                n_samples=res.n,
            )
        )
    return sorted(evaluations, key=lambda e: e.mae)
