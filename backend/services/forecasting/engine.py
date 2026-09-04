"""GROCER v2 Forecasting Engine.

Orchestrates forecast generation over simulator historical data:
  1. Aggregate daily demand per (store, product) from Order/OrderItem history.
  2. Detect and clean anomalies (§12.4).
  3. Fit Baseline model and (if enough data) Time-Series model.
  4. Select the model with lower MAE on held-out tail (when possible).
  5. Compute dynamic confidence score (§12.3).
  6. Persist Forecast rows to DB (§29.9).
  7. Emit FORECAST_UPDATED events (§30).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import Order, OrderItem, Forecast
from backend.events.bus import bus
from backend.services.forecasting.models import (
    DemandPoint,
    detect_anomalies,
    clean_demand_series,
    baseline_predict,
    exponential_smoothing_predict,
    compute_confidence,
    evaluate_forecast,
)

# How many tail days to hold out for model selection evaluation
_HOLDOUT_DAYS = 3
_MIN_HISTORY_FOR_TIMESERIES = 7  # days


class ForecastingEngine:
    """Generates Forecast rows from historical Order data in the simulation DB.

    Usage:
        engine = ForecastingEngine()
        count = await engine.run(db, horizon_hours=24)
    """

    async def run(
        self,
        db: AsyncSession,
        horizon_hours: int = 24,
    ) -> int:
        """Generate forecasts for every (store, product) pair with history.

        Returns the number of Forecast rows written.
        """
        daily_demand = await self._aggregate_daily_demand(db)
        count = 0

        for (store_id, product_id), series in daily_demand.items():
            if not series:
                continue

            forecast_id = uuid.uuid4()
            predicted, model_name, confidence = self._fit_and_predict(
                series, horizon_hours
            )

            row = Forecast(
                forecast_id=forecast_id,
                store_id=store_id,
                product_id=product_id,
                forecast_window_hours=horizon_hours,
                predicted_demand=round(predicted, 4),
                confidence=confidence,
                model_name=model_name,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            await db.flush()

            # Emit event for each forecast (persisted=True writes Event row)
            await bus.publish(
                db,
                "FORECAST_UPDATED",
                "forecast",
                forecast_id,
                {
                    "store_id": str(store_id),
                    "product_id": str(product_id),
                    "model": model_name,
                    "predicted_demand": predicted,
                    "confidence": confidence,
                    "horizon_hours": horizon_hours,
                },
                persist=True,
            )
            count += 1

        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _aggregate_daily_demand(
        self,
        db: AsyncSession,
    ) -> dict[tuple[uuid.UUID, uuid.UUID], list[DemandPoint]]:
        """Query all delivered orders and aggregate demand by (store, product, day)."""
        # Load all order items with their order metadata
        stmt = (
            select(OrderItem, Order)
            .join(Order, OrderItem.order_id == Order.order_id)
        )
        result = await db.execute(stmt)
        rows = result.all()

        # Group by (store_id, product_id) → day_index → total quantity
        # day_index is computed relative to the earliest order date
        if not rows:
            return {}

        # Find earliest date for day_index anchor
        dates = [row.Order.created_at for row in rows]
        min_date = min(dates).date()

        # Accumulate: key=(store_id, product_id), value=dict[day_index -> (dow, qty)]
        acc: dict[tuple, dict[int, list]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            order = row.Order
            item = row.OrderItem
            order_date = order.created_at.date()
            day_index = (order_date - min_date).days
            dow = order_date.weekday()  # 0=Mon … 6=Sun
            key = (order.store_id, item.product_id)
            acc[key][day_index].append((dow, item.quantity))

        # Build DemandPoint series
        series_map: dict[tuple[uuid.UUID, uuid.UUID], list[DemandPoint]] = {}
        for key, day_map in acc.items():
            series: list[DemandPoint] = []
            for day_index in sorted(day_map.keys()):
                entries = day_map[day_index]
                dow = entries[0][0]
                total_qty = sum(q for _, q in entries)
                series.append(DemandPoint(day_index, dow, float(total_qty)))
            series_map[key] = series

        return series_map

    def _fit_and_predict(
        self,
        series: list[DemandPoint],
        horizon_hours: int,
    ) -> tuple[float, str, float]:
        """Fit both models, optionally compare on holdout, return (prediction, model_name, confidence)."""
        anomaly_indices = detect_anomalies(series)
        cleaned = clean_demand_series(series)

        # Always compute baseline
        baseline_pred = baseline_predict(cleaned, horizon_hours)

        # Only attempt time-series if enough history
        use_timeseries = len(series) >= _MIN_HISTORY_FOR_TIMESERIES

        if use_timeseries and len(series) > _HOLDOUT_DAYS + 3:
            # Hold out the last N days for model selection
            train = cleaned[:-_HOLDOUT_DAYS]
            holdout = cleaned[-_HOLDOUT_DAYS:]
            holdout_actual = [p.quantity for p in holdout]

            # Baseline on training data
            bl_preds_holdout = [baseline_predict(train, 24) for _ in holdout]
            bl_eval = evaluate_forecast(holdout_actual, bl_preds_holdout, "baseline")

            # Exponential smoothing on training data
            es_preds_holdout = [exponential_smoothing_predict(train, 24) for _ in holdout]
            es_eval = evaluate_forecast(holdout_actual, es_preds_holdout, "exp_smoothing")

            # Select model with lower MAE
            if es_eval.mae <= bl_eval.mae:
                prediction = exponential_smoothing_predict(cleaned, horizon_hours)
                model_name = "exp_smoothing"
            else:
                prediction = baseline_pred
                model_name = "baseline"
        elif use_timeseries:
            prediction = exponential_smoothing_predict(cleaned, horizon_hours)
            model_name = "exp_smoothing"
        else:
            prediction = baseline_pred
            model_name = "baseline"

        confidence = compute_confidence(series, anomaly_count=len(anomaly_indices))
        return max(0.0, prediction), model_name, confidence
