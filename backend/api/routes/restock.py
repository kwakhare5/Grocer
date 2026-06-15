"""
Restock Alert API — Task 2.3
Exposes endpoints to:
  - GET  /api/restock/{user_id}          → list recent alerts for a household
  - POST /api/restock/{user_id}/check-now → trigger an immediate depletion check

Depletion check logic:
  1. Query consumption_models for items depleting within ALERT_THRESHOLD_DAYS.
  2. Filter out items already alerted in the last 24h (de-duplication).
  3. Return the list — caller (scheduler or manual trigger) decides whether to send WhatsApp.

Why this separation: the check function is pure data; sending WhatsApp is a side-effect.
Keeping them separate makes the depletion logic independently testable.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from backend.database.connection import get_db
from backend.database.models import Household, ConsumptionModel, RestockAlert
from backend.config import settings
from backend.ml.confidence_scorer import ConfidenceScorer

_scorer = ConfidenceScorer()

router = APIRouter(prefix='/api/restock', tags=['restock'])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_household_by_user_id(user_id: str, db: AsyncSession) -> Household:
    """Raise 404 if household does not exist yet (user must sync first)."""
    result = await db.execute(
        select(Household).where(Household.user_id == user_id)
    )
    household = result.scalar_one_or_none()
    if not household:
        raise HTTPException(
            status_code=404,
            detail=f'Household not found for user_id={user_id}. Run /sync first.'
        )
    return household


async def check_depletions_for_household(household_id: str, db: AsyncSession, bypass_cooldown: bool = False) -> list[dict]:
    """
    Return items that are predicted to deplete within ALERT_THRESHOLD_DAYS
    and have confidence >= MIN_CONFIDENCE, excluding any item already alerted
    in the last 24 hours.

    Returns a list of dicts — one per depleting item — sorted by urgency
    (soonest depletion first).
    """
    threshold_days = settings.ALERT_THRESHOLD_DAYS
    min_confidence = settings.MIN_CONFIDENCE
    now = datetime.now(timezone.utc)

    # --- Step 1: find all candidate items ------------------------------------
    stmt = select(ConsumptionModel).where(
        ConsumptionModel.household_id == household_id,
        ConsumptionModel.confidence_score >= min_confidence,
        ConsumptionModel.estimated_depletion_date.isnot(None),
    )

    result = await db.execute(stmt)
    candidate_models = result.scalars().all()

    if not candidate_models:
        return []

    # --- Step 2: load item_ids alerted in last 24h ---------------------------
    cutoff = now - timedelta(hours=24)
    recent_stmt = select(RestockAlert).where(
        RestockAlert.household_id == household_id,
        RestockAlert.sent_at >= cutoff,
        RestockAlert.status.in_(['sent', 'acted']),
    )
    recent_result = await db.execute(recent_stmt)
    recent_alerts = recent_result.scalars().all()

    # item_ids is a JSONB list of item_id strings in RestockAlert
    recently_alerted_ids: set[str] = set()
    for alert in recent_alerts:
        if alert.item_ids is not None:
            for item_id in alert.item_ids:
                recently_alerted_ids.add(str(item_id))

    # --- Step 3: filter using 45% stock level and format ---------------------
    depleting = []
    for model in candidate_models:
        now_aware = now
        depletion_aware = model.estimated_depletion_date
        # Make both timezone-aware if needed for safe subtraction
        if depletion_aware.tzinfo is None:
            depletion_aware = depletion_aware.replace(tzinfo=timezone.utc)

        days_remaining = (depletion_aware - now_aware).total_seconds() / 86400
        cycle: float = model.consumption_cycle_days or 30.0  # type: ignore
        
        # Stock remaining level in %
        fill_percent = (days_remaining / cycle) * 100 if cycle > 0 else 0.0
        
        # Only alert if stock level is below or equal to 45% and days remaining is within threshold
        if days_remaining > threshold_days or fill_percent > 45.0:
            continue

        if not bypass_cooldown and str(model.item_id) in recently_alerted_ids:
            continue  # already alerted in last 24h — skip

        depleting.append({
            'item_id':                 str(model.item_id),
            'item_name':               model.item_name,
            'category':                model.category,
            'confidence_score':        model.confidence_score,
            'confidence_label':        _scorer.human_readable(model.confidence_score),  # type: ignore
            'avg_daily_consumption':   model.avg_daily_consumption,
            'estimated_depletion_date': model.estimated_depletion_date.isoformat(),
            'days_remaining':          round(days_remaining, 1),
            'last_purchase_date':      model.last_purchase_date.isoformat() if model.last_purchase_date is not None else None,
        })

    # Sort by days_remaining ascending so most urgent items are first
    depleting.sort(key=lambda x: x['days_remaining'])
    return depleting



# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get('/{user_id}')
async def get_restock_status(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return the current depletion status for a household.
    Useful for the dashboard to show the "Items Running Low" section.
    Does NOT trigger a WhatsApp alert — read-only.
    """
    household = await _get_household_by_user_id(user_id, db)
    items = await check_depletions_for_household(str(household.id), db)
    return {
        'user_id':          user_id,
        'household_id':     str(household.id),
        'threshold_days':   settings.ALERT_THRESHOLD_DAYS,
        'min_confidence':   settings.MIN_CONFIDENCE,
        'depleting_count':  len(items),
        'depleting_items':  items,
    }


@router.post('/{user_id}/check-now')
async def trigger_restock_check(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Manually trigger a depletion check and log a RestockAlert record if items are found.
    In production this endpoint is called by APScheduler every morning at 8am.
    For demo purposes it can also be called directly via curl.

    Note: WhatsApp sending is handled separately by the notifications layer.
    This endpoint only persists the alert record with status='pending'.
    """
    household = await _get_household_by_user_id(user_id, db)
    items = await check_depletions_for_household(str(household.id), db)

    if not items:
        return {
            'alerts_triggered': 0,
            'message':          'No items depleting within threshold window.',
            'items':            [],
        }

    # Write one RestockAlert per household check (JSONB list of all depleting item IDs)
    now = datetime.now(timezone.utc)
    from backend.seed.catalog import format_restock_alert_message
    message = format_restock_alert_message(items)
    alert = RestockAlert(
        household_id=household.id,
        item_ids=[item['item_id'] for item in items],
        message_sent=message,
        sent_at=now,
        status='pending',
    )
    db.add(alert)
    await db.flush()
    alert_id = str(alert.id)
    await db.commit()

    return {
        'alerts_triggered': len(items),
        'alert_id':         alert_id,
        'message':          f'{len(items)} item(s) depleting within {settings.ALERT_THRESHOLD_DAYS} days.',
        'whatsapp_preview':  message,
        'items': [
            {
                'name':           i['item_name'],
                'days_remaining': i['days_remaining'],
                'confidence':     i['confidence_label'],
            }
            for i in items
        ],
    }


@router.get('/{user_id}/history')
async def get_alert_history(user_id: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """
    Return the last N restock alerts for a household.
    Used by the dashboard to show "Alert History" and track acted/dismissed status.
    """
    household = await _get_household_by_user_id(user_id, db)

    stmt = select(RestockAlert).where(
        RestockAlert.household_id == household.id
    ).order_by(RestockAlert.sent_at.desc()).limit(limit)

    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return {
        'user_id':   user_id,
        'alerts': [
            {
                'id':        str(a.id),
                'item_ids':  a.item_ids,
                'message':   a.message_sent,
                'sent_at':   a.sent_at.isoformat() if a.sent_at is not None else None,
                'status':    a.status,
                'acted_at':  a.acted_at.isoformat() if a.acted_at is not None else None,
            }
            for a in alerts
        ],
    }
