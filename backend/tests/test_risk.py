"""TDD tests for the Risk Engine (spec §5, §13, §29.10, Phase 4).

Test seams in order of the red→green loop:

Unit seams (pure math, no DB):
1. StockoutInput / SpoilageInput — data containers
2. StockoutCalculator — probability, severity, expected_hours_to_stockout
3. SpoilageCalculator — at-risk quantity, probability, severity, discount tier
4. RiskResult — output container

Integration seams (DB):
5. RiskEngine.run() — scans inventory, creates Risk rows, emits RISK_DETECTED events
6. RiskEngine.resolve() — marks a Risk as RESOLVED
7. RiskEngine re-detects risk after inventory drops
"""
from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timedelta

from backend.services.risk.models import (
    StockoutInput,
    SpoilageInput,
    StockoutCalculator,
    SpoilageCalculator,
    RiskResult,
    RiskSeverityLevel,
    DiscountTier,
)


# ─── 1. Data containers ────────────────────────────────────────────────────

def test_stockout_input_stores_fields():
    si = StockoutInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        current_quantity=50,
        forecast_demand_24h=20.0,
        forecast_demand_48h=40.0,
        lead_time_hours=24,
    )
    assert si.current_quantity == 50
    assert si.forecast_demand_24h == 20.0
    assert si.lead_time_hours == 24


def test_spoilage_input_stores_fields():
    sp = SpoilageInput(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        at_risk_quantity=30,
        total_quantity=80,
        min_hours_to_expiry=6.0,
        forecast_demand_before_expiry=10.0,
        shelf_life_hours=72,
    )
    assert sp.at_risk_quantity == 30
    assert sp.min_hours_to_expiry == 6.0


# ─── 2. StockoutCalculator ─────────────────────────────────────────────────

def test_stockout_no_risk_when_inventory_covers_demand():
    """No stockout risk when current stock > 48h forecast."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        current_quantity=100, forecast_demand_24h=10.0, forecast_demand_48h=20.0,
        lead_time_hours=24,
    )
    result = calc.evaluate(inp)
    assert result.probability < 0.2
    assert result.severity == RiskSeverityLevel.LOW


def test_stockout_critical_when_out_of_stock():
    """Zero inventory → critical stockout."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        current_quantity=0, forecast_demand_24h=15.0, forecast_demand_48h=30.0,
        lead_time_hours=24,
    )
    result = calc.evaluate(inp)
    assert result.probability >= 0.9
    assert result.severity == RiskSeverityLevel.CRITICAL


def test_stockout_warning_when_stock_covers_less_than_48h():
    """Stock covering only ~20h of demand at 24h lead time → WARNING."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        current_quantity=8, forecast_demand_24h=10.0, forecast_demand_48h=20.0,
        lead_time_hours=24,
    )
    result = calc.evaluate(inp)
    assert result.severity in (RiskSeverityLevel.WARNING, RiskSeverityLevel.CRITICAL)
    assert result.probability > 0.3


def test_stockout_expected_hours_below_lead_time_is_critical():
    """If expected stockout arrives before lead time → critical."""
    calc = StockoutCalculator()
    inp = StockoutInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        current_quantity=5, forecast_demand_24h=20.0, forecast_demand_48h=40.0,
        lead_time_hours=24,
    )
    result = calc.evaluate(inp)
    # 5 units / (20/24 per hour) ≈ 6h before stockout, less than 24h lead time
    assert result.expected_hours_to_event < 24
    assert result.severity == RiskSeverityLevel.CRITICAL


def test_stockout_result_probability_in_unit_interval():
    """Probability is always in [0.0, 1.0]."""
    calc = StockoutCalculator()
    for qty in [0, 5, 50, 200]:
        inp = StockoutInput(
            store_id=uuid.uuid4(), product_id=uuid.uuid4(),
            current_quantity=qty, forecast_demand_24h=10.0, forecast_demand_48h=20.0,
            lead_time_hours=24,
        )
        result = calc.evaluate(inp)
        assert 0.0 <= result.probability <= 1.0


# ─── 3. SpoilageCalculator ────────────────────────────────────────────────

def test_spoilage_no_risk_when_expiry_distant():
    """Product expiring in 3 days with low inventory → no spoilage risk."""
    calc = SpoilageCalculator()
    inp = SpoilageInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        at_risk_quantity=5, total_quantity=50,
        min_hours_to_expiry=72.0,
        forecast_demand_before_expiry=60.0,
        shelf_life_hours=72,
    )
    result = calc.evaluate(inp)
    assert result.severity == RiskSeverityLevel.LOW
    assert result.probability < 0.2


def test_spoilage_critical_when_expiry_imminent_excess_stock():
    """Large stock, expiry in 4h, demand won't cover it → critical spoilage."""
    calc = SpoilageCalculator()
    inp = SpoilageInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        at_risk_quantity=80, total_quantity=100,
        min_hours_to_expiry=4.0,
        forecast_demand_before_expiry=10.0,
        shelf_life_hours=72,
    )
    result = calc.evaluate(inp)
    assert result.severity == RiskSeverityLevel.CRITICAL
    assert result.probability >= 0.7


def test_spoilage_probability_in_unit_interval():
    """Probability always in [0.0, 1.0]."""
    calc = SpoilageCalculator()
    for hrs in [2, 6, 12, 24, 72]:
        inp = SpoilageInput(
            store_id=uuid.uuid4(), product_id=uuid.uuid4(),
            at_risk_quantity=40, total_quantity=80,
            min_hours_to_expiry=float(hrs),
            forecast_demand_before_expiry=20.0,
            shelf_life_hours=72,
        )
        result = calc.evaluate(inp)
        assert 0.0 <= result.probability <= 1.0


def test_spoilage_discount_tier_by_hours():
    """Discount tier matches spec §14.3 policy tiers."""
    calc = SpoilageCalculator()

    def tier(hrs):
        inp = SpoilageInput(
            store_id=uuid.uuid4(), product_id=uuid.uuid4(),
            at_risk_quantity=50, total_quantity=50,
            min_hours_to_expiry=hrs,
            forecast_demand_before_expiry=5.0,
            shelf_life_hours=72,
        )
        return calc.evaluate(inp).discount_tier

    # Spec §14.3: >24h → 0%, 12-24h → 10%, 6-12h → 20%, <6h → 30%
    assert tier(30.0) == DiscountTier.NONE
    assert tier(18.0) == DiscountTier.TEN_PCT
    assert tier(9.0) == DiscountTier.TWENTY_PCT
    assert tier(3.0) == DiscountTier.THIRTY_PCT


def test_spoilage_at_risk_quantity_correctly_computed():
    """at_risk_quantity is quantity that will not sell through before expiry."""
    calc = SpoilageCalculator()
    inp = SpoilageInput(
        store_id=uuid.uuid4(), product_id=uuid.uuid4(),
        at_risk_quantity=70,  # 70 units at risk
        total_quantity=100,
        min_hours_to_expiry=5.0,
        forecast_demand_before_expiry=20.0,  # only 20 will sell
        shelf_life_hours=72,
    )
    result = calc.evaluate(inp)
    # At-risk: 70 units, expected sell-through: 20 → net at risk ≈ 50
    assert result.net_spoilage_quantity > 0


# ─── 4. RiskResult ────────────────────────────────────────────────────────

def test_risk_result_has_required_fields():
    """RiskResult dataclass exposes all required output fields."""
    result = RiskResult(
        store_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        risk_type="stockout",
        probability=0.8,
        severity=RiskSeverityLevel.CRITICAL,
        expected_hours_to_event=10.0,
        discount_tier=DiscountTier.NONE,
        net_spoilage_quantity=0,
    )
    assert hasattr(result, "probability")
    assert hasattr(result, "severity")
    assert hasattr(result, "expected_hours_to_event")
    assert hasattr(result, "discount_tier")


# ─── 5. RiskEngine integration ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_engine_generates_risks(db_session):
    """RiskEngine.run() detects risks after seeding simulator data."""
    from sqlalchemy import select
    from backend.models.core import Risk
    from backend.services.risk.engine import RiskEngine
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.forecasting.engine import ForecastingEngine

    # Seed simulation (7 days) and generate forecasts
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    # Run risk engine
    risk_engine = RiskEngine()
    count = await risk_engine.run(db_session)
    await db_session.commit()

    assert count >= 0  # may be 0 if all inventory is healthy

    rows = (await db_session.execute(select(Risk))).scalars().all()
    assert len(rows) == count


@pytest.mark.asyncio
async def test_risk_engine_only_creates_active_risks(db_session):
    """All Risk rows created by RiskEngine have status=ACTIVE."""
    from sqlalchemy import select
    from backend.models.core import Risk
    from backend.services.risk.engine import RiskEngine
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.forecasting.engine import ForecastingEngine
    from backend.models.enums import RiskStatus

    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(Risk))).scalars().all()
    for row in rows:
        assert row.status == RiskStatus.ACTIVE


@pytest.mark.asyncio
async def test_risk_engine_emits_risk_detected_events(db_session):
    """RiskEngine emits one RISK_DETECTED event per risk created."""
    from sqlalchemy import select
    from backend.models.core import Risk, Event
    from backend.services.risk.engine import RiskEngine
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.forecasting.engine import ForecastingEngine

    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    risk_engine = RiskEngine()
    count = await risk_engine.run(db_session)
    await db_session.commit()

    events = (await db_session.execute(
        select(Event).where(Event.event_type == "RISK_DETECTED")
    )).scalars().all()

    assert len(events) == count


@pytest.mark.asyncio
async def test_risk_engine_detects_stockout_in_depleted_scenario(db_session):
    """Forcing a near-zero inventory scenario → stockout risk is detected."""
    from sqlalchemy import select, update
    from backend.models.core import Inventory, Risk
    from backend.models.enums import RiskType
    from backend.services.risk.engine import RiskEngine
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.forecasting.engine import ForecastingEngine

    # Seed then force inventory to near-zero for all products in store 1
    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    # Force all inventory quantities to 1 (near stockout)
    await db_session.execute(update(Inventory).values(quantity=1))
    await db_session.commit()

    risk_engine = RiskEngine()
    count = await risk_engine.run(db_session)
    await db_session.commit()

    # With qty=1 and normal demand, many products should be at risk
    stockout_risks = (await db_session.execute(
        select(Risk).where(Risk.risk_type == RiskType.STOCKOUT)
    )).scalars().all()

    assert len(stockout_risks) > 0


@pytest.mark.asyncio
async def test_risk_engine_resolve_marks_risk_resolved(db_session):
    """RiskEngine.resolve(risk_id) transitions risk status to RESOLVED."""
    from sqlalchemy import select
    from backend.models.core import Risk
    from backend.models.enums import RiskStatus
    from backend.services.risk.engine import RiskEngine
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.forecasting.engine import ForecastingEngine

    sim = SimulationEngine(seed=42, historical_days=7)
    await sim.initialize(db_session)
    await db_session.commit()

    fc_engine = ForecastingEngine()
    await fc_engine.run(db_session, horizon_hours=24)
    await db_session.commit()

    # Force near-stockout so risks are created
    from sqlalchemy import update
    from backend.models.core import Inventory
    await db_session.execute(update(Inventory).values(quantity=1))
    await db_session.commit()

    risk_engine = RiskEngine()
    await risk_engine.run(db_session)
    await db_session.commit()

    risks = (await db_session.execute(select(Risk))).scalars().all()
    if not risks:
        pytest.skip("No risks created — cannot test resolution")

    # Resolve the first risk
    risk_id = risks[0].risk_id
    await risk_engine.resolve(db_session, risk_id)
    await db_session.commit()

    resolved = await db_session.get(Risk, risk_id)
    assert resolved.status == RiskStatus.RESOLVED
