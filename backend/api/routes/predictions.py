"""
Predictions API — Task 3.3 (frontend hydration)
Exposes consumption model predictions for a household.

Endpoints:
  - GET /api/predictions/{user_id}
      Returns all ConsumptionModel rows for the household, formatted for the
      frontend Predictions page. Sorted by days_remaining ascending (most urgent first).

Why read directly from ConsumptionModel table (not re-run Prophet)?
  Prophet fitting is slow (~2-10s per item). The scheduler rebuilds models weekly,
  and POST /api/household/{user_id}/rebuild-models triggers it on demand.
  This endpoint is READ-ONLY and has no side effects — it does not regenerate
  scenario data or touch ML models. Use POST /api/household/{user_id}/scenario
  to switch demo scenarios instead.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from backend.database.connection import get_db
from backend.database.models import Household, ConsumptionModel
from backend.services.cache import get_cached, set_cached

router = APIRouter(prefix='/api/predictions', tags=['predictions'])


async def _get_household(user_id: str, db: AsyncSession) -> Household:
    result = await db.execute(select(Household).where(Household.user_id == user_id))
    hh = result.scalar_one_or_none()
    if not hh:
        raise HTTPException(status_code=404, detail=f'Household not found for user: {user_id}')
    return hh


@router.get('/{user_id}')
async def get_predictions(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return all consumption model predictions for a household.
    Sorted by urgency: items depleting soonest appear first.
    Items with no depletion date (avg_daily=0) appear at the end.

    Pure read — see module docstring. No scenario reset, no model rebuild.
    """
    cache_key = f"predictions:{user_id}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached

    hh = await _get_household(user_id, db)

    result = await db.execute(
        select(ConsumptionModel)
        .where(ConsumptionModel.household_id == hh.id)
        .order_by(ConsumptionModel.estimated_depletion_date.asc().nullslast())
    )
    models = result.scalars().all()

    now = datetime.now(timezone.utc)
    predictions = []

    for m in models:
        days_remaining: float | None = None
        stock_fill_percent: float | None = None
        status = 'unknown'

        if m.estimated_depletion_date is not None:
            dep = m.estimated_depletion_date
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)
            raw_days = (dep - now).total_seconds() / 86400

            cycle = float(m.consumption_cycle_days or 30.0)  # type: ignore
            fill_val = (raw_days / cycle) * 100 if cycle > 0 else 0.0
            stock_fill_percent = max(0.0, min(100.0, fill_val))

            days_remaining = round(raw_days, 1)

            if days_remaining < 0:
                status = 'depleted'
            elif days_remaining <= 3:
                status = 'critical'
            elif days_remaining <= 7:
                status = 'low'
            else:
                status = 'ok'

        predictions.append({
            'item_id':                   str(m.item_id),
            'item_name':                 m.item_name,
            'category':                  m.category,
            'avg_daily_consumption':     m.avg_daily_consumption,
            'consumption_cycle_days':    m.consumption_cycle_days,
            'last_purchase_date':        m.last_purchase_date.isoformat() if m.last_purchase_date is not None else None,
            'last_purchase_quantity':    m.last_purchase_quantity,
            'estimated_depletion_date':  m.estimated_depletion_date.isoformat() if m.estimated_depletion_date is not None else None,
            'days_remaining':            days_remaining,
            'stock_fill_percent':        round(stock_fill_percent, 1) if stock_fill_percent is not None else 100.0,
            'confidence_score':          m.confidence_score,
            'data_points':               m.data_points,
            'status':                    status,
            'updated_at':                m.updated_at.isoformat() if m.updated_at is not None else None,
            'is_anomaly_excluded':       getattr(m, 'is_anomaly_excluded', False),  # NEW — additive field, see C2
        })

    response = {
        'user_id':          user_id,
        'household_id':     str(hh.id),
        'total_items':      len(predictions),
        'predictions':      predictions,
        'generated_at':     now.isoformat(),
    }

    await set_cached(cache_key, response, ttl_seconds=20)
    return response


@router.get('/')
async def predictions_index():
    return {
        'endpoints': [
            'GET /api/predictions/{user_id} — full prediction list for a household',
        ]
    }
