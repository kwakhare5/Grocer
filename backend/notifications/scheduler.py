"""
Scheduler — Task 2.6
Runs background jobs on a cron schedule using APScheduler AsyncIOScheduler.

Jobs registered:
  1. daily_depletion_check_all  — 08:00 every day
     Iterates all households with notifications_enabled=True,
     checks for depleting items, and logs a RestockAlert per item.

  2. track_commodity_prices     — 07:00 every day
     Samples catalog prices with realistic market noise and writes
     rows to the TimescaleDB `price_history` hypertable.

  3. rebuild_all_models_job     — 02:00 every Sunday
     Re-runs Prophet for every household so predictions stay fresh
     as new orders accumulate over the week.

Why AsyncIOScheduler?
  FastAPI runs on asyncio. BackgroundScheduler spins a separate thread
  and requires thread-safe DB access. AsyncIOScheduler shares the same
  event loop so we can await async DB sessions directly without risk.

Why separate functions instead of inline lambdas?
  APScheduler serialises job callables by name for restart recovery.
  Inline lambdas are un-serialisable. Named module-level coroutines are safe.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from backend.database.connection import AsyncSessionLocal
from backend.database.models import Household, RestockAlert
from backend.ml.consumption_model import ConsumptionModeler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton scheduler — imported and started from main.py lifespan
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


# ---------------------------------------------------------------------------
# Job 1: daily_depletion_check_all
# ---------------------------------------------------------------------------

# Volatility tiers by category — mirrors price_agent and generate_orders.py
_VOLATILITY: dict[str, float] = {
    "dairy":      0.04,
    "staples":    0.06,
    "vegetables": 0.30,
    "protein":    0.08,
    "bakery":     0.03,
}


async def daily_depletion_check_all() -> None:
    """
    Run every morning at 08:00 IST.
    For every household with notifications enabled, check which items are
    predicted to deplete within ALERT_THRESHOLD_DAYS and write a RestockAlert
    per depleting item (status='pending').

    Why one alert per item?
      The RestockAlert schema (CLAUDE.md spec) has item_id / item_name as
      single-value columns, not a JSON list. One row per item gives us clean
      per-item audit trails and lets us update status independently.
    """

    now = datetime.now(timezone.utc)
    logger.info("[Scheduler] daily_depletion_check_all started — %s", now.isoformat())

    async with AsyncSessionLocal() as db:
        # Fetch all opted-in households
        result = await db.execute(
            select(Household).where(Household.notifications_enabled == True)  # noqa: E712
        )
        households = result.scalars().all()
        logger.info("[Scheduler] Checking %d household(s)", len(households))

        for hh in households:
            try:
                # Re-use the restock route helper to get depleting items
                from backend.api.routes.restock import check_depletions_for_household

                items = await check_depletions_for_household(str(hh.id), db)
                if not items:
                    logger.debug("[Scheduler] Household %s — nothing depleting", hh.user_id)
                    continue

                item_ids_list = [item["item_id"] for item in items]
                from backend.seed.catalog import format_restock_alert_message
                message = format_restock_alert_message(items)
                alert = RestockAlert(
                    household_id=hh.id,
                    item_ids=item_ids_list,
                    message_sent=message,
                    sent_at=now,
                    status="pending",
                )
                db.add(alert)

                await db.commit()
                logger.info(
                    "[Scheduler] Household %s — %d alert(s) logged",
                    hh.user_id, len(items)
                )

            except Exception as exc:
                await db.rollback()
                logger.error("[Scheduler] Error processing household %s: %s", hh.user_id, exc)


# ---------------------------------------------------------------------------
# Job 2: track_commodity_prices
# ---------------------------------------------------------------------------

async def track_commodity_prices() -> None:
    """
    Run every morning at 07:00 IST (before depletion check).
    Triggers the Price Intelligence Agent to sample latest PreFill mock catalog
    prices, write them to TimescaleDB, analyze price changes, and dispatch WhatsApp alerts.
    """
    now = datetime.now(timezone.utc)
    logger.info("[Scheduler] track_commodity_prices started — %s", now.isoformat())

    async with AsyncSessionLocal() as db:
        from backend.agents.price_agent import track_and_alert_prices
        try:
            result = await track_and_alert_prices(db)
            logger.info(
                "[Scheduler] Price agent executed: recorded=%d alerts=%d",
                result["prices_recorded"], len(result["alerts_triggered"])
            )
        except Exception as exc:
            logger.error("[Scheduler] Price tracking agent failed: %s", exc)


# ---------------------------------------------------------------------------
# Job 3: rebuild_all_models_job
# ---------------------------------------------------------------------------

async def rebuild_all_models_job() -> None:
    """
    Run every Sunday at 02:00 IST.
    Re-runs the Prophet consumption model for every household so that
    weekly order patterns accumulate into fresh depletion predictions.

    Why weekly (not daily)?
      Prophet fitting is CPU-intensive for large item catalogues.
      A weekly rebuild keeps predictions fresh while avoiding daytime load.
      Manual triggers remain available via POST /api/household/{user_id}/rebuild.
    """
    logger.info("[Scheduler] rebuild_all_models_job started")
    modeler = ConsumptionModeler()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Household))
        households = result.scalars().all()

        for hh in households:
            try:
                stats = await modeler.rebuild_all_models(str(hh.id), db)
                logger.info(
                    "[Scheduler] Household %s models rebuilt — built=%d skipped=%d errors=%d",
                    hh.user_id, stats["built"], stats["skipped"], stats["errors"]
                )
            except Exception as exc:
                logger.error(
                    "[Scheduler] Model rebuild failed for %s: %s", hh.user_id, exc
                )


# ---------------------------------------------------------------------------
# Lifecycle helper — called from main.py lifespan
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """Register all jobs and start the scheduler. Called once on FastAPI startup."""
    scheduler.add_job(
        daily_depletion_check_all,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="daily_depletion_check",
        replace_existing=True,
        misfire_grace_time=3600,  # tolerate up to 1h misfire (e.g. server restart)
    )
    scheduler.add_job(
        track_commodity_prices,
        trigger=CronTrigger(hour=7, minute=0, timezone="Asia/Kolkata"),
        id="track_prices",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        rebuild_all_models_job,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0, timezone="Asia/Kolkata"),
        id="weekly_model_rebuild",
        replace_existing=True,
        misfire_grace_time=7200,
    )
    scheduler.start()
    logger.info(
        "[Scheduler] Started. Jobs: %s",
        [job.id for job in scheduler.get_jobs()]
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler. Called on FastAPI shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped.")
