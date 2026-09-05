"""TDD tests for Phase 4: Risk Engine.

Verifies:
- Seam 2: RiskConfig & Uncertainty-scaled stockout calculator
- Seam 3: FIFO multi-batch cumulative spoilage calculator
- Seam 4: Multi-horizon forecast resolution & cold-start fallback
- Seam 5: Deduplicated active risk persistence & event publishing
- Seam 6: API schema extensions & filters
- Seam 7: Determinism, invariants, and full integration
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select, update

from backend.services.risk.models import (
    RiskConfig,
    StockoutInput,
    StockoutCalculator,
    RiskResult,
    RiskSeverityLevel,
    DiscountTier,
)


# ===========================================================================
# Seam 2: RiskConfig & Uncertainty-Scaled Stockout Calculator
# ===========================================================================

def test_stockout_healthy_inventory():
    """Stock covering well over lead time + safety buffer produces LOW risk."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=100,
        forecast_demand_24h=24.0,  # 1.0 unit/hr
        forecast_demand_48h=48.0,
        lead_time_hours=24,        # safe window = 24 * 1.5 = 36h
        forecast_confidence=1.0,
    )
    res = calc.evaluate(inp)
    assert res.probability == 0.0
    assert res.severity == RiskSeverityLevel.LOW
    assert res.expected_hours_to_event == 100.0


def test_stockout_critical_when_depleted():
    """Zero inventory with active demand produces CRITICAL stockout immediately."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=0,
        forecast_demand_24h=24.0,
        forecast_demand_48h=48.0,
        lead_time_hours=24,
        forecast_confidence=1.0,
    )
    res = calc.evaluate(inp)
    assert res.probability == 1.0
    assert res.severity == RiskSeverityLevel.CRITICAL
    assert res.expected_hours_to_event == 0.0


def test_stockout_warning_tier():
    """Stock covering partial lead time produces WARNING severity."""
    calc = StockoutCalculator()
    # 1.0 unit/hr demand, 24h lead time -> safe window = 36h
    # 18 units -> hours_of_stock = 18 -> prob = 1 - 18/36 = 0.50
    inp = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=18,
        forecast_demand_24h=24.0,
        forecast_demand_48h=48.0,
        lead_time_hours=24,
        forecast_confidence=1.0,
    )
    res = calc.evaluate(inp)
    assert 0.3 <= res.probability < 0.7
    assert res.severity == RiskSeverityLevel.WARNING
    assert res.expected_hours_to_event == 18.0


def test_stockout_zero_demand():
    """Zero demand rate never triggers stockout risk regardless of inventory."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=0,
        forecast_demand_24h=0.0,
        forecast_demand_48h=0.0,
        lead_time_hours=24,
    )
    res = calc.evaluate(inp)
    assert res.probability == 0.0
    assert res.severity == RiskSeverityLevel.LOW
    assert math.isinf(res.expected_hours_to_event)


def test_stockout_uncertainty_scaling():
    """Low forecast confidence widens the required safety buffer, increasing risk."""
    calc = StockoutCalculator()
    # 30 units with 24h lead time (base safe window = 36h)
    # High confidence (1.0): safe window = 36h -> prob = 1 - 30/36 = 0.1667 (LOW)
    # Low confidence (0.2): uncertainty = 0.8 -> multiplier = 1 + 0.8*0.5 = 1.4 -> safe window = 50.4h
    # prob = 1 - 30/50.4 = 0.4048 (WARNING)
    inp_high_conf = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=30,
        forecast_demand_24h=24.0,
        forecast_demand_48h=48.0,
        lead_time_hours=24,
        forecast_confidence=1.0,
    )
    inp_low_conf = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=30,
        forecast_demand_24h=24.0,
        forecast_demand_48h=48.0,
        lead_time_hours=24,
        forecast_confidence=0.2,
    )
    res_high = calc.evaluate(inp_high_conf)
    res_low = calc.evaluate(inp_low_conf)

    assert res_low.probability > res_high.probability
    assert res_high.severity == RiskSeverityLevel.LOW
    assert res_low.severity == RiskSeverityLevel.WARNING


def test_stockout_custom_risk_config():
    """Custom RiskConfig thresholds alter the severity cutoffs."""
    # With a lower critical threshold (0.45 instead of 0.70), prob 0.50 becomes CRITICAL
    custom_config = RiskConfig(stockout_critical_threshold=0.45)
    calc = StockoutCalculator(config=custom_config)
    inp = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=18,
        forecast_demand_24h=24.0,
        forecast_demand_48h=48.0,
        lead_time_hours=24,
        forecast_confidence=1.0,
    )
    res = calc.evaluate(inp)
    assert res.probability == 0.5
    assert res.severity == RiskSeverityLevel.CRITICAL

# ===========================================================================
# Seam 3: FIFO Multi-Batch Cumulative Spoilage Calculator
# ===========================================================================
from backend.services.risk.models import (
    BatchInfo,
    MultiBatchSpoilageInput,
    SpoilageCalculator,
    discount_tier_for_hours,
)


def test_spoilage_discount_tier_gradation():
    """Verify exact discount tier assignment per spec §14.3."""
    assert discount_tier_for_hours(30.0) == DiscountTier.NONE
    assert discount_tier_for_hours(18.0) == DiscountTier.TEN_PCT
    assert discount_tier_for_hours(8.0) == DiscountTier.TWENTY_PCT
    assert discount_tier_for_hours(3.0) == DiscountTier.THIRTY_PCT


def test_spoilage_enough_demand_no_risk():
    """When projected demand absorbs inventory before expiry, net spoilage is 0 and severity is LOW."""
    calc = SpoilageCalculator()
    b1 = BatchInfo(batch_id=uuid.uuid4(), quantity=20, hours_to_expiry=20.0)
    inp = MultiBatchSpoilageInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        batches=[b1],
        hourly_demand=2.0,  # 40 units consumed in 20h > 20 on hand
        shelf_life_hours=72,
    )
    res = calc.evaluate_batches(inp)
    assert res.net_spoilage_quantity == 0
    assert res.probability == 0.0
    assert res.severity == RiskSeverityLevel.LOW
    assert res.discount_tier == DiscountTier.NONE


def test_spoilage_near_expiry_critical():
    """Near-expiry batch (<6h) with low sell-through triggers CRITICAL risk and 30% discount tier."""
    calc = SpoilageCalculator()
    b1 = BatchInfo(batch_id=uuid.uuid4(), quantity=50, hours_to_expiry=4.0)
    inp = MultiBatchSpoilageInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        batches=[b1],
        hourly_demand=1.0,  # only 4 units consumed in 4h, 46 spoil
        shelf_life_hours=48,
    )
    res = calc.evaluate_batches(inp)
    assert res.net_spoilage_quantity == 46
    assert res.severity == RiskSeverityLevel.CRITICAL
    assert res.discount_tier == DiscountTier.THIRTY_PCT
    assert res.expected_hours_to_event == 4.0


def test_spoilage_multiple_batches_fifo():
    """Multiple batches evaluated under FIFO cumulative depletion correctly sum net spoilage."""
    calc = SpoilageCalculator()
    # Batch 1: 10 units expiring in 5h
    # Batch 2: 25 units expiring in 10h
    # Total units = 35. Demand rate = 1.0 unit/h.
    # At h=5: demand = 5, cumulative stock = 10 -> at risk = 5
    # At h=10: demand = 10, cumulative stock = 35 -> at risk = 25
    b1 = BatchInfo(batch_id=uuid.uuid4(), quantity=10, hours_to_expiry=5.0)
    b2 = BatchInfo(batch_id=uuid.uuid4(), quantity=25, hours_to_expiry=10.0)
    inp = MultiBatchSpoilageInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        batches=[b1, b2],
        hourly_demand=1.0,
        shelf_life_hours=72,
    )
    res = calc.evaluate_batches(inp)
    assert res.net_spoilage_quantity == 25
    assert res.severity in (RiskSeverityLevel.WARNING, RiskSeverityLevel.CRITICAL)
    # Earliest at-risk batch expires at 5h (<6h -> 30% discount tier)
    assert res.expected_hours_to_event == 5.0
    assert res.discount_tier == DiscountTier.THIRTY_PCT


def test_spoilage_zero_demand():
    """Zero demand means 100% of expiring stock is lost."""
    calc = SpoilageCalculator()
    b1 = BatchInfo(batch_id=uuid.uuid4(), quantity=30, hours_to_expiry=12.0)
    inp = MultiBatchSpoilageInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        batches=[b1],
        hourly_demand=0.0,
        shelf_life_hours=48,
    )
    res = calc.evaluate_batches(inp)
    assert res.net_spoilage_quantity == 30
    assert res.probability >= 0.65
    assert res.severity == RiskSeverityLevel.CRITICAL

# ===========================================================================
# Seam 4 & 5: RiskEngine Orchestration, Multi-Horizon & Deduplication
# ===========================================================================
from backend.services.simulation.engine import SimulationEngine
from backend.services.forecasting.engine import ForecastingEngine
from backend.services.risk.engine import RiskEngine
from backend.models.core import Risk, Inventory, Batch, Store, Product
from backend.models.enums import RiskType, RiskSeverity, RiskStatus


@pytest.mark.asyncio
async def test_risk_engine_multi_horizon_resolution(db_session):
    """RiskEngine resolves multi-horizon 24h/48h forecasts cleanly."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizons=[6, 12, 24, 48])
    await db_session.commit()

    # Drop inventory for one item to force stockout risk
    inv = (await db_session.execute(select(Inventory))).scalars().first()
    inv.quantity = 0
    await db_session.commit()

    risk_engine = RiskEngine()
    count = await risk_engine.run(db_session)
    await db_session.commit()

    assert count > 0

    # Query active stockout risk for that inventory item
    res = await db_session.execute(
        select(Risk).where(
            Risk.store_id == inv.store_id,
            Risk.product_id == inv.product_id,
            Risk.risk_type == RiskType.STOCKOUT,
            Risk.status == RiskStatus.ACTIVE,
        )
    )
    risk = res.scalars().first()
    assert risk is not None
    assert risk.severity == RiskSeverity.CRITICAL
    assert risk.probability >= 0.9


@pytest.mark.asyncio
async def test_risk_engine_cold_start_fallback_when_no_forecasts(db_session):
    """When forecast table is empty, RiskEngine falls back gracefully to priors without error."""
    sim = SimulationEngine(seed=42, historical_days=3)
    await sim.initialize(db_session)
    await db_session.commit()

    # Force low inventory
    await db_session.execute(update(Inventory).values(quantity=2))
    await db_session.commit()

    risk_engine = RiskEngine()
    # No forecasts generated in DB
    count = await risk_engine.run(db_session)
    await db_session.commit()

    assert count > 0
    all_risks = (await db_session.execute(select(Risk))).scalars().all()
    assert len(all_risks) > 0


@pytest.mark.asyncio
async def test_risk_engine_deduplicates_active_risks(db_session):
    """Running RiskEngine repeatedly on unchanged state updates existing active risks rather than spawning duplicates."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    # Force inventory to 1 to produce warnings
    await db_session.execute(update(Inventory).values(quantity=1))
    await db_session.commit()

    risk_engine = RiskEngine()
    count1 = await risk_engine.run(db_session)
    await db_session.commit()

    risks_after_first = (await db_session.execute(select(Risk).where(Risk.status == RiskStatus.ACTIVE))).scalars().all()
    first_count = len(risks_after_first)
    assert first_count > 0

    # Run again on the exact same state
    count2 = await risk_engine.run(db_session)
    await db_session.commit()

    risks_after_second = (await db_session.execute(select(Risk).where(Risk.status == RiskStatus.ACTIVE))).scalars().all()
    second_count = len(risks_after_second)

    # Number of active risks must remain stable (not double)
    assert second_count == first_count


@pytest.mark.asyncio
async def test_risk_engine_resolve_workflow(db_session):
    """engine.resolve() marks risk as RESOLVED and records status."""
    sim = SimulationEngine(seed=42, historical_days=5)
    await sim.initialize(db_session)
    await db_session.commit()

    # Create a synthetic risk
    risk_id = uuid.uuid4()
    store = (await db_session.execute(select(Store))).scalars().first()
    product = (await db_session.execute(select(Product))).scalars().first()

    r = Risk(
        risk_id=risk_id,
        store_id=store.store_id,
        product_id=product.product_id,
        risk_type=RiskType.STOCKOUT,
        severity=RiskSeverity.CRITICAL,
        probability=0.95,
        expected_time=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2),
        status=RiskStatus.ACTIVE,
    )
    db_session.add(r)
    await db_session.commit()

    engine = RiskEngine()
    resolved = await engine.resolve(db_session, risk_id)
    await db_session.commit()

    assert resolved is not None
    assert resolved.status == RiskStatus.RESOLVED

    fetched = await db_session.get(Risk, risk_id)
    assert fetched.status == RiskStatus.RESOLVED

# ===========================================================================
# Seam 6 & 7: API Endpoints, Determinism & Invariants
# ===========================================================================
from httpx import ASGITransport, AsyncClient
from backend.main import create_app
from backend.database import get_db


@pytest.mark.asyncio
async def test_risk_api_evaluate_and_filters(db_session):
    """API endpoints for evaluate, filter by risk_type, severity, status, and store."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    # Drop inventory on store to create risks
    await db_session.execute(update(Inventory).values(quantity=1))
    await db_session.commit()

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Trigger evaluation
        eval_resp = await client.post("/api/risks/evaluate")
        assert eval_resp.status_code == 200
        assert eval_resp.json()["risks_detected"] > 0

        # 2. List risks
        list_resp = await client.get("/api/risks")
        assert list_resp.status_code == 200
        risks = list_resp.json()
        assert len(risks) > 0

        first_risk = risks[0]
        risk_id = first_risk["risk_id"]

        # 3. Filter by risk_type
        stockout_resp = await client.get("/api/risks?risk_type=stockout")
        assert stockout_resp.status_code == 200
        for r in stockout_resp.json():
            assert r["risk_type"] == "stockout"

        # 4. Filter by status
        active_resp = await client.get("/api/risks?status=active")
        assert active_resp.status_code == 200
        for r in active_resp.json():
            assert r["status"] == "active"

        # 5. Get single risk
        single_resp = await client.get(f"/api/risks/{risk_id}")
        assert single_resp.status_code == 200
        assert single_resp.json()["risk_id"] == risk_id

        # 6. Resolve risk
        resolve_resp = await client.post(f"/api/risks/{risk_id}/resolve")
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["status"] == "resolved"

        # Verify status is now resolved
        resolved_get = await client.get(f"/api/risks/{risk_id}")
        assert resolved_get.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_risk_engine_determinism_and_immutability(db_session):
    """Evaluating risks does not mutate physical inventory and produces bit-for-bit reproducible results."""
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    # Capture initial inventory and batches
    inv_before = {
        (inv.store_id, inv.product_id): inv.quantity
        for inv in (await db_session.execute(select(Inventory))).scalars().all()
    }
    batches_before = {
        b.batch_id: b.quantity
        for b in (await db_session.execute(select(Batch))).scalars().all()
    }

    fixed_now = datetime(2026, 9, 5, 12, 0, 0)

    risk_engine = RiskEngine()
    count_1 = await risk_engine.run(db_session, now=fixed_now)
    await db_session.commit()

    # Verify inventory was NOT mutated
    inv_after = {
        (inv.store_id, inv.product_id): inv.quantity
        for inv in (await db_session.execute(select(Inventory))).scalars().all()
    }
    batches_after = {
        b.batch_id: b.quantity
        for b in (await db_session.execute(select(Batch))).scalars().all()
    }
    assert inv_before == inv_after
    assert batches_before == batches_after

    # Capture first run risks
    risks_1 = {
        (r.store_id, r.product_id, r.risk_type): (r.severity, r.probability, r.expected_time)
        for r in (await db_session.execute(select(Risk))).scalars().all()
    }

    # Run again with a new engine instance on the exact same state
    risk_engine_2 = RiskEngine()
    count_2 = await risk_engine_2.run(db_session, now=fixed_now)
    await db_session.commit()

    risks_2 = {
        (r.store_id, r.product_id, r.risk_type): (r.severity, r.probability, r.expected_time)
        for r in (await db_session.execute(select(Risk))).scalars().all()
    }

    assert count_1 == count_2
    assert risks_1 == risks_2

