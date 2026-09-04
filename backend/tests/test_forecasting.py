"""TDD tests for the forecasting engine (spec §12).

Test seams, in order of the red→green loop:

1. DemandPoint — data container
2. Anomaly detection — Z-score / IQR spike filter
3. Baseline predictor — moving average + day-of-week seasonality
4. Confidence scorer — multi-factor output in [0, 1]
5. Evaluation metrics — MAE, RMSE, MAPE
6. Time-series predictor — exponential smoothing with seasonality
7. ForecastingEngine (integration) — reads history, writes Forecast rows
"""
from __future__ import annotations

import math
import pytest

from backend.services.forecasting.models import (
    DemandPoint,
    detect_anomalies,
    clean_demand_series,
    baseline_predict,
    compute_confidence,
    evaluate_forecast,
    ModelEvaluationResult,
    exponential_smoothing_predict,
)


# ---------------------------------------------------------------------------
# 1. DemandPoint
# ---------------------------------------------------------------------------

def test_demand_point_stores_fields():
    """DemandPoint is a simple data container."""
    dp = DemandPoint(day_index=0, day_of_week=1, quantity=10.0)
    assert dp.day_index == 0
    assert dp.day_of_week == 1
    assert dp.quantity == 10.0


# ---------------------------------------------------------------------------
# 2. Anomaly detection
# ---------------------------------------------------------------------------

def test_detect_anomalies_flags_spikes():
    """Z-score > 3 on a 6x spike is flagged as anomaly."""
    # 9 normal points + 1 extreme spike
    series = [DemandPoint(i, i % 7, 10.0) for i in range(9)]
    series.append(DemandPoint(9, 2, 600.0))   # spike
    anomaly_indices = detect_anomalies(series, z_threshold=3.0)
    assert 9 in anomaly_indices


def test_detect_anomalies_no_flag_on_stable_data():
    """No anomalies detected when demand is perfectly uniform."""
    series = [DemandPoint(i, i % 7, 15.0) for i in range(30)]
    assert detect_anomalies(series) == []


def test_detect_anomalies_empty_series_returns_empty():
    """Empty series yields empty anomaly list without error."""
    assert detect_anomalies([]) == []


def test_clean_demand_series_replaces_anomalies_with_median():
    """Anomalous points are replaced with the series median in cleaned output."""
    series = [DemandPoint(i, i % 7, 10.0) for i in range(9)]
    series.append(DemandPoint(9, 2, 600.0))
    cleaned = clean_demand_series(series)
    # The spike index should be approximately the median of normal values
    assert cleaned[9].quantity <= 20.0  # not the spike value any more


# ---------------------------------------------------------------------------
# 3. Baseline predictor
# ---------------------------------------------------------------------------

def test_baseline_predict_uniform_demand():
    """On perfectly uniform demand, baseline prediction equals that demand."""
    series = [DemandPoint(i, i % 7, 10.0) for i in range(30)]
    result = baseline_predict(series, horizon_hours=24)
    # With uniform data and no day-of-week variation, prediction ≈ 10
    assert abs(result - 10.0) < 2.0


def test_baseline_predict_higher_on_weekend():
    """Baseline predictor lifts forecast for weekend days (5=Sat, 6=Sun) when they have higher historical demand."""
    # Mon–Fri = 8, Sat–Sun = 20 (weekend demand is 2.5x higher)
    series = []
    for i in range(28):
        dow = i % 7
        qty = 20.0 if dow >= 5 else 8.0
        series.append(DemandPoint(i, dow, qty))
    # Predict for a Monday (horizon = 24h from a Monday)
    weekday_pred = baseline_predict(series, horizon_hours=24, forecast_day_of_week=1)
    # Predict for a Saturday
    weekend_pred = baseline_predict(series, horizon_hours=24, forecast_day_of_week=6)
    assert weekend_pred > weekday_pred


def test_baseline_predict_scales_with_horizon():
    """A 48h horizon prediction is approximately double a 24h prediction."""
    series = [DemandPoint(i, i % 7, 12.0) for i in range(30)]
    pred_24 = baseline_predict(series, horizon_hours=24)
    pred_48 = baseline_predict(series, horizon_hours=48)
    ratio = pred_48 / pred_24
    assert 1.8 <= ratio <= 2.2


def test_baseline_predict_minimum_series_length():
    """Baseline works with as few as 3 data points."""
    series = [DemandPoint(i, i % 7, 5.0) for i in range(3)]
    result = baseline_predict(series, horizon_hours=24)
    assert result > 0


# ---------------------------------------------------------------------------
# 4. Confidence scorer
# ---------------------------------------------------------------------------

def test_confidence_returns_float_in_unit_interval():
    """compute_confidence always returns a value in [0.0, 1.0]."""
    series = [DemandPoint(i, i % 7, 10.0) for i in range(30)]
    c = compute_confidence(series, anomaly_count=0)
    assert 0.0 <= c <= 1.0


def test_confidence_lower_for_high_variance():
    """Higher coefficient of variation yields lower confidence."""
    stable = [DemandPoint(i, i % 7, 10.0) for i in range(30)]
    noisy  = [DemandPoint(i, i % 7, 10.0 + (i % 5) * 15) for i in range(30)]
    c_stable = compute_confidence(stable, anomaly_count=0)
    c_noisy  = compute_confidence(noisy, anomaly_count=0)
    assert c_stable > c_noisy


def test_confidence_lower_for_more_anomalies():
    """More anomalies in history → lower confidence."""
    series = [DemandPoint(i, i % 7, 10.0) for i in range(30)]
    c_clean = compute_confidence(series, anomaly_count=0)
    c_dirty = compute_confidence(series, anomaly_count=10)
    assert c_clean > c_dirty


def test_confidence_lower_for_small_sample():
    """Fewer data points → lower confidence."""
    large = [DemandPoint(i, i % 7, 10.0) for i in range(60)]
    small = [DemandPoint(i, i % 7, 10.0) for i in range(5)]
    c_large = compute_confidence(large, anomaly_count=0)
    c_small = compute_confidence(small, anomaly_count=0)
    assert c_large > c_small


# ---------------------------------------------------------------------------
# 5. Evaluation metrics
# ---------------------------------------------------------------------------

def test_evaluate_forecast_perfect_predictions():
    """Perfect forecasts yield MAE=0, RMSE=0, MAPE=0."""
    actual    = [10.0, 20.0, 15.0, 5.0]
    predicted = [10.0, 20.0, 15.0, 5.0]
    result = evaluate_forecast(actual, predicted)
    assert result.mae == pytest.approx(0.0)
    assert result.rmse == pytest.approx(0.0)
    assert result.mape == pytest.approx(0.0)


def test_evaluate_forecast_known_mae():
    """MAE is correctly computed from a worked example."""
    actual    = [10.0, 20.0]
    predicted = [8.0, 22.0]   # errors: 2, 2 → MAE = 2.0
    result = evaluate_forecast(actual, predicted)
    assert result.mae == pytest.approx(2.0)


def test_evaluate_forecast_known_rmse():
    """RMSE is correctly computed from a worked example."""
    actual    = [10.0, 10.0]
    predicted = [7.0, 13.0]   # squared errors: 9, 9 → RMSE = 3.0
    result = evaluate_forecast(actual, predicted)
    assert result.rmse == pytest.approx(3.0)


def test_evaluate_forecast_known_mape():
    """MAPE is correctly computed from a worked example."""
    actual    = [100.0, 200.0]
    predicted = [90.0, 220.0]  # APE: 10%, 10% → MAPE = 10.0
    result = evaluate_forecast(actual, predicted)
    assert result.mape == pytest.approx(10.0, abs=0.01)


def test_evaluate_forecast_returns_model_evaluation_result():
    """evaluate_forecast returns a ModelEvaluationResult dataclass."""
    result = evaluate_forecast([5.0], [5.0])
    assert isinstance(result, ModelEvaluationResult)
    assert hasattr(result, "mae")
    assert hasattr(result, "rmse")
    assert hasattr(result, "mape")


# ---------------------------------------------------------------------------
# 6. Time-series predictor (exponential smoothing)
# ---------------------------------------------------------------------------

def test_exponential_smoothing_returns_positive_prediction():
    """Time-series model returns a positive demand forecast for 30d history."""
    series = [DemandPoint(i, i % 7, 12.0 + (i % 3)) for i in range(30)]
    result = exponential_smoothing_predict(series, horizon_hours=24)
    assert result > 0


def test_exponential_smoothing_tracks_trend():
    """Exponential smoothing with upward trend predicts higher than the mean."""
    # Steadily rising demand: 5, 6, 7, ... 34
    series = [DemandPoint(i, i % 7, float(5 + i)) for i in range(30)]
    mean_demand = sum(p.quantity for p in series) / len(series)  # ~19.5
    pred = exponential_smoothing_predict(series, horizon_hours=24)
    # Prediction should be close to or above the mean of the later portion
    assert pred > mean_demand * 0.8


def test_exponential_smoothing_too_short_falls_back_to_baseline():
    """With only 2 data points, exponential smoothing falls back gracefully (>0)."""
    series = [DemandPoint(0, 0, 10.0), DemandPoint(1, 1, 10.0)]
    result = exponential_smoothing_predict(series, horizon_hours=24)
    assert result > 0


# ---------------------------------------------------------------------------
# 7. ForecastingEngine integration (uses async DB session)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forecasting_engine_generates_forecasts(db_session):
    """ForecastingEngine runs on seeded simulation data and writes Forecast rows."""
    from sqlalchemy import select
    from backend.models.core import Forecast
    from backend.services.forecasting.engine import ForecastingEngine
    from backend.services.simulation.engine import SimulationEngine

    # Seed a small simulation (7 days for speed)
    sim_engine = SimulationEngine(seed=42, historical_days=7)
    await sim_engine.initialize(db_session)
    await db_session.commit()

    # Run forecaster
    fc_engine = ForecastingEngine()
    count = await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    # At least one forecast row per store/product combination that has history
    assert count > 0

    rows = (await db_session.execute(select(Forecast))).scalars().all()
    assert len(rows) == count


@pytest.mark.asyncio
async def test_forecasting_engine_confidence_in_range(db_session):
    """All generated Forecast rows have confidence in [0.0, 1.0]."""
    from sqlalchemy import select
    from backend.models.core import Forecast
    from backend.services.forecasting.engine import ForecastingEngine
    from backend.services.simulation.engine import SimulationEngine

    sim_engine = SimulationEngine(seed=42, historical_days=7)
    await sim_engine.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    rows = (await db_session.execute(select(Forecast))).scalars().all()
    assert rows, "Expected at least one Forecast row"
    for row in rows:
        assert 0.0 <= row.confidence <= 1.0, f"Out-of-range confidence: {row.confidence}"


@pytest.mark.asyncio
async def test_forecasting_engine_emits_event(db_session):
    """ForecastingEngine emits FORECAST_UPDATED events for each forecast generated."""
    from sqlalchemy import select
    from backend.models.core import Event
    from backend.services.forecasting.engine import ForecastingEngine
    from backend.services.simulation.engine import SimulationEngine

    sim_engine = SimulationEngine(seed=42, historical_days=7)
    await sim_engine.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    count = await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    result = await db_session.execute(
        select(Event).where(Event.event_type == "FORECAST_UPDATED")
    )
    events = result.scalars().all()
    assert len(events) == count
