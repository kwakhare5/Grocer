"""
Predictions API — Task 3.3 (frontend hydration)
Exposes consumption model predictions for a household.

Endpoints:
  - GET /api/predictions/{user_id}
      Returns all ConsumptionModel rows for the household, formatted for the
      frontend Predictions page. Sorted by days_remaining ascending (most urgent first).

Why read directly from ConsumptionModel table (not re-run Prophet)?
  Prophet fitting is slow (~2-10s per item). The scheduler rebuilds models weekly.
  The API just reads the pre-computed predictions. This keeps the endpoint fast (<100ms).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from backend.database.connection import get_db
from backend.database.models import Household, ConsumptionModel

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
    """
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
        status = 'unknown'

        if m.estimated_depletion_date:
            dep = m.estimated_depletion_date
            # Normalize timezone — DB may store naive UTC datetimes
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)
            days_remaining = round((dep - now).total_seconds() / 86400, 1)

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
            'last_purchase_date':        m.last_purchase_date.isoformat() if m.last_purchase_date else None,
            'last_purchase_quantity':    m.last_purchase_quantity,
            'estimated_depletion_date':  m.estimated_depletion_date.isoformat() if m.estimated_depletion_date else None,
            'days_remaining':            days_remaining,
            'confidence_score':          m.confidence_score,
            'data_points':               m.data_points,
            'status':                    status,  # depleted / critical / low / ok / unknown
            'updated_at':                m.updated_at.isoformat() if m.updated_at else None,
        })

    return {
        'user_id':          user_id,
        'household_id':     str(hh.id),
        'total_items':      len(predictions),
        'predictions':      predictions,
        'generated_at':     now.isoformat(),
    }


@router.get('/')
async def predictions_index():
    """Index endpoint — lists available prediction routes."""
    return {
        'endpoints': [
            'GET /api/predictions/{user_id} — full prediction list for a household',
        ]
    }
