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
    import os
    import json
    from backend.api.routes.household import reset_scenario_data
    
    # Get currently active scenario or default to standard
    scenario = "standard"
    try:
        active_scenario_path = os.path.join(os.path.dirname(__file__), "..", "..", "active_scenario.json")
        if os.path.exists(active_scenario_path):
            with open(active_scenario_path, "r") as f:
                data = json.load(f)
                scenario = data.get("scenario", "standard")
    except Exception as e:
        print(f"Warning: Failed to read active scenario: {e}")
        
    try:
        await reset_scenario_data(user_id, scenario, db)
    except Exception as e:
        print(f"Warning: Failed to auto-reset scenario data: {e}")

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
            # Normalize timezone — DB may store naive UTC datetimes
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
            'status':                    status,  # depleted / critical / low / ok / unknown
            'updated_at':                m.updated_at.isoformat() if m.updated_at is not None else None,
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
