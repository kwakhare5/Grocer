from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.connection import get_db
from backend.database.models import Household
from backend.services.sync_service import fetch_and_sync_orders
from backend.ml.household_profiler import update_household_profile

router = APIRouter(prefix='/api/household', tags=['household'])


async def get_or_create_household(user_id: str, db: AsyncSession) -> Household:
    """Get an existing household or create one for this user."""
    result = await db.execute(select(Household).where(Household.user_id == user_id))
    household = result.scalar_one_or_none()
    if not household:
        household = Household(user_id=user_id)
        db.add(household)
        await db.commit()
        await db.refresh(household)
    return household


@router.post("/{user_id}/sync")
async def sync_household_orders(user_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the latest orders from the MCP server and persist new ones to the DB."""
    household = await get_or_create_household(user_id, db)
    synced = await fetch_and_sync_orders(str(household.id), user_id, db)
    return {"message": f"Synced {synced} new orders", "household_id": str(household.id)}


@router.post("/{user_id}/rebuild-models")
async def rebuild_household_models(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger ML model rebuild as a background task — does not block the HTTP thread.
    After models rebuild, automatically re-infers household composition.
    """
    from backend.ml.consumption_model import ConsumptionModeler

    household = await get_or_create_household(user_id, db)
    household_id = str(household.id)
    modeler = ConsumptionModeler()

    async def _rebuild_then_profile():
        # Why separate function: BackgroundTasks can only accept a single callable.
        # We chain rebuild → profiler here so both run in the same background task.
        await modeler.rebuild_all_models(household_id, db)
        await update_household_profile(household_id, db)

    background_tasks.add_task(_rebuild_then_profile)
    return {
        "message": "Model rebuild + profile inference queued. Check predictions in ~60 seconds.",
        "household_id": household_id
    }


@router.get("/{user_id}")
async def get_household_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get household profile details, including inferred composition."""
    result = await db.execute(select(Household).where(Household.user_id == user_id))
    hh = result.scalar_one_or_none()
    if not hh:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Household not found")
    return {
        "id": str(hh.id),
        "user_id": hh.user_id,
        "phone_number": hh.phone_number,
        "composition": hh.composition,
        "composition_confidence": hh.composition_confidence,
        "intelligence_consent": hh.intelligence_consent,
        "notifications_enabled": hh.notifications_enabled,
        "created_at": hh.created_at.isoformat() if hh.created_at else None
    }
