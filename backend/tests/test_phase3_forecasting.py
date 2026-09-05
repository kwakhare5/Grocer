"""TDD tests for Phase 3: Measured Demand Forecasting.

Verifies:
- Seam 1: Dense historical demand aggregation & continuous day padding
- Seam 2: Cold-start fallback to seed priors
- Seam 3: Multi-horizon forecasting support (6h, 12h, 24h, 48h)
- Seam 4: Empirical ground-truth backtesting (MAE, RMSE, MAPE)
- Seam 5: Forecasting API extensions (/generate multi-horizon, /evaluate empirical metrics)
- Seam 6: Strict invariants (non-negative predictions, bounded confidence, ground-truth immutability, determinism)
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select, func

from backend.services.simulation.engine import SimulationEngine
from backend.services.forecasting.engine import ForecastingEngine
from backend.services.forecasting.models import (
    DemandPoint,
    evaluate_forecast,
    ModelEvaluationResult,
)
from backend.models.core import Forecast, Order, OrderItem, Inventory, Batch, Store, Product


@pytest.mark.asyncio
async def test_dense_daily_demand_padding(db_session):
    """Aggregation must pad missing days with 0.0 quantity and continuous day indices."""
    engine = SimulationEngine(seed=42, historical_days=5)
    await engine.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    daily_demand = await fc._aggregate_daily_demand(db_session)
    assert len(daily_demand) > 0

    for (store_id, prod_id), series in daily_demand.items():
        if len(series) > 1:
            # Check continuous day indices: day_index[i+1] == day_index[i] + 1
            for i in range(len(series) - 1):
                assert series[i + 1].day_index == series[i].day_index + 1
                # Day of week must match modulo 7
                assert series[i + 1].day_of_week == (series[i].day_of_week + 1) % 7


@pytest.mark.asyncio
async def test_cold_start_fallback_uses_seed_prior(db_session):
    """When history has fewer than 7 days, fallback to seed product prior rather than 0."""
    engine = SimulationEngine(seed=42, historical_days=2)
    await engine.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    # Create empty/very short series
    short_series = [DemandPoint(day_index=0, day_of_week=0, quantity=2.0)]
    
    products = (await db_session.execute(select(Product))).scalars().all()
    sample_prod = products[0]

    pred, model_name, conf = fc._fit_and_predict(short_series, horizon_hours=24, product_id=sample_prod.product_id)
    assert pred > 0.0
    assert "baseline" in model_name or "seed_prior" in model_name or "fallback" in model_name
    assert 0.0 <= conf <= 1.0


@pytest.mark.asyncio
async def test_multi_horizon_generation(db_session):
    """Forecast generation supports multi-horizons (6h, 12h, 24h, 48h) with monotonic demand."""
    engine = SimulationEngine(seed=42, historical_days=7)
    await engine.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    count = await fc.run(db_session, horizons=[6, 12, 24, 48])
    await db_session.commit()
    assert count > 0

    # Group forecasts by (store_id, product_id)
    all_fc = (await db_session.execute(select(Forecast))).scalars().all()
    grouped: dict[tuple, dict[int, Forecast]] = {}
    for f in all_fc:
        key = (f.store_id, f.product_id)
        grouped.setdefault(key, {})[f.forecast_window_hours] = f

    # Verify every group has all 4 horizons and demand scales with horizon
    for key, h_map in list(grouped.items())[:5]:
        assert set(h_map.keys()) == {6, 12, 24, 48}
        assert h_map[6].predicted_demand <= h_map[12].predicted_demand
        assert h_map[12].predicted_demand <= h_map[24].predicted_demand
        assert h_map[24].predicted_demand <= h_map[48].predicted_demand


@pytest.mark.asyncio
async def test_empirical_backtest_evaluation(db_session):
    """Historical backtesting produces genuine empirical evaluation results against ground truth."""
    engine = SimulationEngine(seed=42, historical_days=14)
    await engine.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    eval_results = await fc.evaluate_on_history(db_session, holdout_days=3)

    assert "baseline" in eval_results
    assert "exponential_smoothing" in eval_results

    b_eval = eval_results["baseline"]
    assert b_eval.n > 0
    assert b_eval.mae >= 0.0
    assert b_eval.rmse >= 0.0


@pytest.mark.asyncio
async def test_api_generate_multi_horizon(client):
    """POST /api/forecasts/generate accepts multiple horizons."""
    create_resp = await client.post("/api/simulations/", json={"seed": 42, "historical_days": 5})
    assert create_resp.status_code == 201

    gen_resp = await client.post(
        "/api/forecasts/generate",
        json={"horizons": [6, 12, 24, 48]},
    )
    assert gen_resp.status_code == 200
    data = gen_resp.json()
    assert "forecasts_generated" in data
    assert data["forecasts_generated"] > 0
    assert data["horizons"] == [6, 12, 24, 48]

    # Verify filtering by horizon_hours
    filter_resp = await client.get("/api/forecasts?horizon_hours=6")
    assert filter_resp.status_code == 200
    items_6h = filter_resp.json()
    assert len(items_6h) > 0
    assert all(item["forecast_window_hours"] == 6 for item in items_6h)


@pytest.mark.asyncio
async def test_api_evaluate_returns_empirical_metrics(client):
    """GET /api/forecasts/evaluate returns empirical backtest metrics."""
    create_resp = await client.post("/api/simulations/", json={"seed": 42, "historical_days": 10})
    assert create_resp.status_code == 201

    # Generate forecasts
    await client.post("/api/forecasts/generate", json={"horizons": [24]})

    resp = await client.get("/api/forecasts/evaluate")
    assert resp.status_code == 200
    evals = resp.json()
    assert len(evals) >= 1
    for ev in evals:
        assert "model_name" in ev
        assert "mae" in ev
        assert "rmse" in ev
        assert ev["mae"] >= 0.0
        assert ev["rmse"] >= 0.0


@pytest.mark.asyncio
async def test_invariants_non_negative_and_bounded_confidence(db_session):
    """All generated forecasts must have non-negative demand and confidence in [0, 1]."""
    engine = SimulationEngine(seed=42, historical_days=7)
    await engine.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    await fc.run(db_session, horizons=[6, 12, 24, 48])
    await db_session.commit()

    forecasts = (await db_session.execute(select(Forecast))).scalars().all()
    assert len(forecasts) > 0

    for f in forecasts:
        assert f.predicted_demand >= 0.0, f"Negative prediction for {f.forecast_id}"
        assert 0.0 <= f.confidence <= 1.0, f"Unbounded confidence {f.confidence} for {f.forecast_id}"


@pytest.mark.asyncio
async def test_invariants_ground_truth_immutability(db_session):
    """Forecasting generation MUST NOT mutate orders, items, batches, or inventory quantities."""
    engine = SimulationEngine(seed=42, historical_days=5)
    await engine.initialize(db_session)
    await db_session.commit()

    # Capture ground truth state before forecasting
    order_count_before = (await db_session.execute(select(func.count(Order.order_id)))).scalar()
    item_count_before = (await db_session.execute(select(func.count(OrderItem.id)))).scalar()
    batch_quantities_before = (await db_session.execute(select(Batch.batch_id, Batch.quantity))).all()
    inventory_quantities_before = (await db_session.execute(select(Inventory.id, Inventory.quantity))).all()

    # Run forecasting
    fc = ForecastingEngine()
    await fc.run(db_session, horizons=[6, 12, 24, 48])
    await db_session.commit()

    # Verify ground truth state is completely untouched
    order_count_after = (await db_session.execute(select(func.count(Order.order_id)))).scalar()
    item_count_after = (await db_session.execute(select(func.count(OrderItem.id)))).scalar()
    batch_quantities_after = (await db_session.execute(select(Batch.batch_id, Batch.quantity))).all()
    inventory_quantities_after = (await db_session.execute(select(Inventory.id, Inventory.quantity))).all()


    assert order_count_after == order_count_before
    assert item_count_after == item_count_before
    assert batch_quantities_after == batch_quantities_before
    assert inventory_quantities_after == inventory_quantities_before


@pytest.mark.asyncio
async def test_invariants_deterministic_forecasting(db_session):
    """Running forecasting over identical database state yields identical forecast values."""
    engine = SimulationEngine(seed=42, historical_days=5)
    await engine.initialize(db_session)
    await db_session.commit()

    fc = ForecastingEngine()
    daily_demand = await fc._aggregate_daily_demand(db_session)
    first_key = next(iter(daily_demand))
    series = daily_demand[first_key]

    pred1, model1, conf1 = fc._fit_and_predict(series, horizon_hours=24)
    pred2, model2, conf2 = fc._fit_and_predict(series, horizon_hours=24)

    assert pred1 == pred2
    assert model1 == model2
    assert conf1 == conf2
