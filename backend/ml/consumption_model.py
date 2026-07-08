"""
Consumption Model — Task 2.1
Builds per-item consumption forecasts from purchase history using Prophet,
with anomaly-aware preprocessing (travel gaps, guest-visit spikes, dietary
change detection) so a single outlier order doesn't distort every future
depletion prediction.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
from prophet import Prophet
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Order, OrderItem, ConsumptionModel
from backend.config import settings
from backend.ml.confidence_scorer import ConfidenceScorer
from backend.ml.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)


class ConsumptionModeler:
    MIN_DATA_POINTS = 3

    def __init__(self):
        self._anomaly_detector = AnomalyDetector()

    async def build_model_for_item(self, household_id: str, item_id: str, item_name: str, db: AsyncSession) -> dict | None:
        stmt = (
            select(OrderItem.standard_quantity, Order.placed_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .where(OrderItem.item_id == item_id)
            .order_by(Order.placed_at.asc())
        )
        result = await db.execute(stmt)
        purchases = [dict(p) for p in result.mappings().all()]

        if len(purchases) < self.MIN_DATA_POINTS:
            return None

        purchases_sorted = sorted(purchases, key=lambda p: p["placed_at"])
        naive_baseline = sum(p["standard_quantity"] for p in purchases_sorted) / len(purchases_sorted)

        # --------------------------------------------------------------
        # Anomaly detection (previously computed nowhere — dead code).
        # Guest spikes inflate the apparent daily rate; travel gaps
        # inflate the apparent cycle length. Both get corrected below
        # instead of feeding straight into the forecast.
        # --------------------------------------------------------------
        guest_result = self._anomaly_detector.detect_guest_visit(
            [{"placed_at": p["placed_at"], "standard_quantity": p["standard_quantity"]} for p in purchases_sorted],
            baseline_qty=naive_baseline,
        )
        guest_spike_dates = (
            {e["date"] for e in guest_result.get("events", [])} if guest_result["detected"] else set()
        )

        purchase_dates = [p["placed_at"] for p in purchases_sorted]
        travel_result = self._anomaly_detector.detect_travel(purchase_dates)
        travel_gaps = travel_result.get("gaps", []) if travel_result["detected"] else []
        travel_gap_starts = {g["start"] for g in travel_gaps}
        travel_days = sum(g["duration_days"] for g in travel_gaps)

        # Cycle days: exclude the travel-gap interval(s) so an away-from-home
        # stretch doesn't get averaged in as if it were a slow buying week.
        diffs_with_start = []
        for i in range(1, len(purchases_sorted)):
            start = purchases_sorted[i - 1]["placed_at"]
            end = purchases_sorted[i]["placed_at"]
            diffs_with_start.append((start, (end - start).days))

        normal_diffs = [d for (start, d) in diffs_with_start if start not in travel_gap_starts]
        if normal_diffs:
            cycle_days = float(sum(normal_diffs) / len(normal_diffs))
        elif diffs_with_start:
            cycle_days = float(sum(d for _, d in diffs_with_start) / len(diffs_with_start))
        else:
            cycle_days = 0.0

        # Cap (not drop) guest-spike quantities so Prophet sees a smoother
        # series without losing the purchase event's timing information.
        clean_rows = []
        for p in purchases_sorted:
            qty = p["standard_quantity"]
            if p["placed_at"] in guest_spike_dates:
                qty = min(qty, naive_baseline)
            clean_rows.append({"ds": p["placed_at"], "y": qty})

        df = pd.DataFrame(clean_rows)
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)

        # --------------------------------------------------------------
        # Prophet — fit on CUMULATIVE consumption so the fitted trend
        # component is what actually produces avg_daily_consumption,
        # instead of being fit and thrown away (previous behavior).
        # --------------------------------------------------------------
        df_cum = df.sort_values("ds").copy()
        df_cum["y"] = df_cum["y"].cumsum()

        avg_daily = None
        try:
            import logging as log
            log.getLogger('prophet').setLevel(log.WARNING)
            log.getLogger('cmdstanpy').setLevel(log.WARNING)

            import asyncio
            model = Prophet(
                growth='linear',
                seasonality_mode='additive',
                yearly_seasonality=False,  # type: ignore
                weekly_seasonality=(len(purchases_sorted) >= 10),  # type: ignore
                daily_seasonality=False,  # type: ignore
                interval_width=0.80,
            )
            await asyncio.to_thread(model.fit, df_cum)

            horizon_days = max(3, int(df["ds"].diff().dt.days.dropna().mean() or 7))
            future = await asyncio.to_thread(model.make_future_dataframe, periods=horizon_days)
            forecast = await asyncio.to_thread(model.predict, future)

            last_actual_cum = float(df_cum["y"].iloc[-1])
            future_tail = forecast[forecast["ds"] > df_cum["ds"].max()]
            if not future_tail.empty:
                projected_cum = float(future_tail["yhat"].iloc[-1])
                slope = (projected_cum - last_actual_cum) / horizon_days
                if slope > 0:
                    avg_daily = slope
        except Exception as e:
            logger.warning(
                f"Prophet fit/forecast failed for {item_name}: {e}. "
                f"Falling back to arithmetic time-series estimate."
            )

        # Arithmetic fallback / floor — also anomaly-aware (excludes travel days).
        total_qty = float(df["y"].sum())
        total_days = max((df["ds"].max() - df["ds"].min()).days, 1)
        active_days = max(total_days - travel_days, 1)
        arithmetic_avg_daily = total_qty / active_days

        if avg_daily is None or avg_daily <= 0:
            avg_daily = arithmetic_avg_daily

        last = purchases_sorted[-1]
        last_date = last["placed_at"]
        last_qty = float(last["standard_quantity"])

        depletion = last_date + timedelta(days=last_qty / avg_daily) if avg_daily > 0 else None

        scorer = ConfidenceScorer()
        confidence = scorer.score(purchase_dates, len(purchases_sorted))
        if confidence < settings.MIN_CONFIDENCE:
            return None

        return {
            "household_id": household_id,
            "item_id": item_id,
            "item_name": item_name,
            "avg_daily_consumption": round(avg_daily, 4),
            "consumption_cycle_days": round(cycle_days, 1),
            "last_purchase_date": last_date,
            "last_purchase_quantity": last_qty,
            "estimated_depletion_date": depletion,
            "confidence_score": round(confidence, 3),
            "data_points": len(purchases_sorted),
            "updated_at": datetime.now(),
        }

    async def rebuild_all_models(self, household_id: str, db: AsyncSession) -> dict:
        stmt = (
            select(OrderItem.item_id, OrderItem.item_name, func.count().label('cnt'))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .group_by(OrderItem.item_id, OrderItem.item_name)
            .having(func.count() >= self.MIN_DATA_POINTS)
            .order_by(func.count().desc())
        )
        result = await db.execute(stmt)
        items = result.mappings().all()

        results = {"built": 0, "skipped": 0, "errors": 0}

        for item in items:
            try:
                data = await self.build_model_for_item(household_id, item["item_id"], item["item_name"], db)
                if not data:
                    results["skipped"] += 1
                    continue

                # Per-item SAVEPOINT — a failure here only rolls back this
                # item, not the entire batch (fixes C5). Combined with the
                # unique constraint (fixes C4), concurrent rebuilds are now
                # safe instead of merely usually-fine.
                async with db.begin_nested():
                    stmt_existing = select(ConsumptionModel).where(
                        ConsumptionModel.household_id == household_id,
                        ConsumptionModel.item_id == item["item_id"]
                    )
                    existing_result = await db.execute(stmt_existing)
                    existing_model = existing_result.scalar_one_or_none()

                    if existing_model:
                        for key, value in data.items():
                            setattr(existing_model, key, value)
                    else:
                        db.add(ConsumptionModel(**data))

                results["built"] += 1
            except Exception as e:
                logger.error(f"Error building model for {item['item_name']}: {e}")
                results["errors"] += 1

        await db.commit()

        try:
            await self._flag_dietary_changes(household_id, db)
        except Exception as e:
            logger.warning(f"Dietary change detection failed for household {household_id}: {e}")

        return results

    async def _flag_dietary_changes(self, household_id: str, db: AsyncSession) -> None:
        """
        Groups order items by category per month, runs the dietary-change
        heuristic, and marks matching ConsumptionModel rows as
        is_anomaly_excluded=True so they're paused from restock alerts
        (see restock.py::check_depletions_for_household) until confirmed —
        matching the "confirm_with_user" action AnomalyDetector already
        specifies but that nothing previously read.
        """
        stmt = (
            select(OrderItem.category, Order.placed_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .where(OrderItem.category.isnot(None))
        )
        result = await db.execute(stmt)
        rows = result.mappings().all()
        if not rows:
            return

        monthly_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in rows:
            month_key = row["placed_at"].strftime("%Y-%m")
            monthly_counts[row["category"]][month_key] += 1

        category_series = {
            cat: [count for _, count in sorted(months.items())]
            for cat, months in monthly_counts.items()
        }

        detection = self._anomaly_detector.detect_dietary_change(category_series)

        if not detection["detected"]:
            await db.execute(
                update(ConsumptionModel)
                .where(ConsumptionModel.household_id == household_id)
                .values(is_anomaly_excluded=False)
            )
            await db.commit()
            return

        changed_categories = {c["category"] for c in detection["changes"]}
        await db.execute(
            update(ConsumptionModel)
            .where(ConsumptionModel.household_id == household_id)
            .where(ConsumptionModel.category.in_(changed_categories))
            .values(is_anomaly_excluded=True)
        )
        await db.execute(
            update(ConsumptionModel)
            .where(ConsumptionModel.household_id == household_id)
            .where(ConsumptionModel.category.notin_(changed_categories))
            .values(is_anomaly_excluded=False)
        )
        await db.commit()
        logger.info(
            f"Household {household_id}: flagged categories {changed_categories} for dietary-change review"
        )
