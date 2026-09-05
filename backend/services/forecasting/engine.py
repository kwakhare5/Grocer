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
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import Order, OrderItem, Forecast
from backend.events.bus import bus
from backend.services.simulation.seed_data import PRODUCTS
from backend.services.forecasting.models import (
    DemandPoint,
    detect_anomalies,
    clean_demand_series,
    baseline_predict,
    exponential_smoothing_predict,
    compute_confidence,
    evaluate_forecast,
    ModelEvaluationResult,
)

# How many tail days to hold out for model selection evaluation
_HOLDOUT_DAYS = 3
_MIN_HISTORY_FOR_TIMESERIES = 7  # days


class ForecastingEngine:
    """Generates Forecast rows from historical Order data in the simulation DB.

    Usage:
        engine = ForecastingEngine()
        count = await engine.run(db, horizons=[6, 12, 24, 48])
    """

    async def run(
        self,
        db: AsyncSession,
        horizon_hours: int | None = None,
        horizons: list[int] | None = None,
    ) -> int:
        """Generate forecasts for every (store, product) pair across specified horizons.

        Returns the number of Forecast rows written.
        """
        if horizons is None:
            horizons = [horizon_hours] if horizon_hours is not None else [24]

        daily_demand = await self._aggregate_daily_demand(db)
        count = 0

        for h in horizons:
            for (store_id, product_id), series in daily_demand.items():
                if not series:
                    continue

                forecast_id = uuid.uuid4()
                predicted, model_name, confidence = self._fit_and_predict(
                    series, h, product_id=product_id
                )

                row = Forecast(
                    forecast_id=forecast_id,
                    store_id=store_id,
                    product_id=product_id,
                    forecast_window_hours=h,
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
                        "horizon_hours": h,
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
        """Query all delivered orders and aggregate demand by (store, product, day) with continuous zero-padding."""
        stmt = (
            select(OrderItem, Order)
            .join(Order, OrderItem.order_id == Order.order_id)
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            return {}

        dates = [row.Order.created_at for row in rows]
        min_date = min(dates).date()
        max_date = max(dates).date()
        total_days = (max_date - min_date).days + 1

        acc: dict[tuple, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for row in rows:
            order = row.Order
            item = row.OrderItem
            order_date = order.created_at.date()
            day_index = (order_date - min_date).days
            key = (order.store_id, item.product_id)
            acc[key][day_index] += float(item.quantity)

        # Build continuous dense DemandPoint series
        series_map: dict[tuple[uuid.UUID, uuid.UUID], list[DemandPoint]] = {}
        for key, day_map in acc.items():
            series: list[DemandPoint] = []
            for day_index in range(total_days):
                curr_date = min_date + timedelta(days=day_index)
                dow = curr_date.weekday()
                qty = day_map.get(day_index, 0.0)
                series.append(DemandPoint(day_index, dow, qty))
            series_map[key] = series

        return series_map

    def _fit_and_predict(
        self,
        series: list[DemandPoint],
        horizon_hours: int,
        product_id: uuid.UUID | None = None,
    ) -> tuple[float, str, float]:
        """Fit both models, optionally compare on holdout, return (prediction, model_name, confidence).
        
        Falls back to catalog seed prior if history is too short (< 7 days) or series has zero orders.
        """
        if len(series) < _MIN_HISTORY_FOR_TIMESERIES or sum(p.quantity for p in series) == 0.0:
            if product_id:
                seed_p = next((p for p in PRODUCTS if p.product_id == product_id), None)
                if seed_p and seed_p.daily_demand_mean > 0:
                    pred = seed_p.daily_demand_mean * (horizon_hours / 24.0)
                    return round(pred, 4), "baseline_seed_prior", 0.50

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

    async def evaluate_on_history(
        self,
        db: AsyncSession,
        holdout_days: int = 3,
    ) -> dict[str, ModelEvaluationResult]:
        """Perform empirical rolling-origin backtesting across historical orders.

        Splits demand series into training and holdout test sets, scoring baseline vs
        exponential smoothing against real simulator ground truth.
        """
        daily_demand = await self._aggregate_daily_demand(db)
        if not daily_demand:
            return {
                "baseline": ModelEvaluationResult(0.0, 0.0, 0.0, "baseline", 0),
                "exponential_smoothing": ModelEvaluationResult(0.0, 0.0, 0.0, "exponential_smoothing", 0),
            }

        bl_actuals: list[float] = []
        bl_preds: list[float] = []

        es_actuals: list[float] = []
        es_preds: list[float] = []

        for (store_id, product_id), series in daily_demand.items():
            if len(series) <= holdout_days + 2:
                continue

            train = series[:-holdout_days]
            holdout = series[-holdout_days:]

            for pt in holdout:
                actual_qty = pt.quantity

                b_pred = baseline_predict(train, horizon_hours=24, forecast_day_of_week=pt.day_of_week)
                bl_actuals.append(actual_qty)
                bl_preds.append(b_pred)

                es_pred = exponential_smoothing_predict(train, horizon_hours=24)
                es_actuals.append(actual_qty)
                es_preds.append(es_pred)

        bl_eval = evaluate_forecast(bl_actuals, bl_preds, "baseline")
        es_eval = evaluate_forecast(es_actuals, es_preds, "exponential_smoothing")

        return {
            "baseline": bl_eval,
            "exponential_smoothing": es_eval,
        }

