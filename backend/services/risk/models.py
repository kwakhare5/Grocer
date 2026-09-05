"""GROCER v2 Risk Engine — Pure deterministic risk models.

Implements spec §5 (availability + waste loops), §13 (batch-aware inventory),
§14.3 (discount tiers), §29.10 (Risk ORM schema).

Risk Types:
  STOCKOUT — expected demand will exhaust inventory before resupply (§5.1)
  SPOILAGE — perishable batch will expire before it can be sold (§5.2)

All logic is pure Python — no async, no DB. Easily unit-tested.
The RiskEngine (engine.py) orchestrates DB I/O and event emission.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------

class RiskSeverityLevel(str, enum.Enum):
    LOW      = "low"
    WARNING  = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Discount tiers (spec §14.3)
# ---------------------------------------------------------------------------

class DiscountTier(str, enum.Enum):
    NONE        = "none"       # > 24h remaining
    TEN_PCT     = "10%"        # 12–24h
    TWENTY_PCT  = "20%"        # 6–12h
    THIRTY_PCT  = "30%"        # < 6h


def discount_tier_for_hours(hours_remaining: float) -> DiscountTier:
    """Map hours-to-expiry to the correct discount tier per spec §14.3."""
    if hours_remaining > 24:
        return DiscountTier.NONE
    elif hours_remaining > 12:
        return DiscountTier.TEN_PCT
    elif hours_remaining > 6:
        return DiscountTier.TWENTY_PCT
    else:
        return DiscountTier.THIRTY_PCT


# ---------------------------------------------------------------------------
# Risk Configuration & Thresholds
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskConfig:
    """Configurable thresholds and weights for the Risk Engine."""
    stockout_critical_threshold: float = 0.7
    stockout_warning_threshold: float = 0.3
    safety_headroom_factor: float = 1.5
    uncertainty_weight: float = 0.5
    spoilage_critical_threshold: float = 0.65
    spoilage_warning_threshold: float = 0.25
    spoilage_urgency_weight: float = 0.4
    spoilage_fraction_weight: float = 0.6


# ---------------------------------------------------------------------------
# Input data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StockoutInput:
    """All information needed to evaluate stockout risk for one (store, product)."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    current_quantity: int
    forecast_demand_24h: float      # predicted demand in next 24 hours
    forecast_demand_48h: float      # predicted demand in next 48 hours
    lead_time_hours: int            # supplier lead time
    safety_stock: int = 0           # configurable floor (default 0)
    forecast_confidence: float = 1.0  # [0.0, 1.0] from Phase 3 forecasting
    hourly_demand: Optional[float] = None


@dataclass(frozen=True)
class BatchInfo:
    """Represents one physical batch for multi-batch spoilage analysis."""
    batch_id: uuid.UUID
    quantity: int
    hours_to_expiry: float


@dataclass(frozen=True)
class MultiBatchSpoilageInput:
    """Information needed to evaluate multi-batch spoilage risk for one (store, product)."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    batches: list[BatchInfo]
    hourly_demand: float
    shelf_life_hours: int
    forecast_confidence: float = 1.0


@dataclass(frozen=True)
class SpoilageInput:
    """All information needed to evaluate spoilage risk for one (store, product)."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    at_risk_quantity: int           # quantity in the soonest-expiring batch
    total_quantity: int             # total on-hand quantity
    min_hours_to_expiry: float      # hours until the soonest batch expires
    forecast_demand_before_expiry: float  # predicted demand before that batch expires
    shelf_life_hours: int           # product shelf life (for context)


# ---------------------------------------------------------------------------
# Output container
# ---------------------------------------------------------------------------

@dataclass
class RiskResult:
    """Computed risk assessment for one (store, product, risk_type) combination."""
    store_id: uuid.UUID
    product_id: uuid.UUID
    risk_type: str                        # "stockout" | "spoilage"
    probability: float                    # [0.0, 1.0]
    severity: RiskSeverityLevel
    expected_hours_to_event: float        # hours until stockout / expiry
    discount_tier: DiscountTier           # only meaningful for SPOILAGE
    net_spoilage_quantity: int = 0        # units expected to spoil (SPOILAGE only)


# ---------------------------------------------------------------------------
# Stockout Calculator
# ---------------------------------------------------------------------------

class StockoutCalculator:
    """Evaluates stockout risk from current inventory vs forecast demand.

    Algorithm:
    1. Compute hours-to-stockout from daily demand rate.
    2. Compare to supplier lead_time_hours + safety headroom (scaled by forecast uncertainty).
    3. Calculate probability based on how far below lead time we are.
    4. Map probability to severity tier using configurable thresholds.
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()

    def evaluate(self, inp: StockoutInput) -> RiskResult:
        if inp.hourly_demand is not None and inp.hourly_demand >= 0:
            hourly_demand = inp.hourly_demand
        else:
            hourly_demand = inp.forecast_demand_24h / 24.0

        # Avoid division by zero — zero demand means no stockout risk
        if hourly_demand <= 0:
            return RiskResult(
                store_id=inp.store_id,
                product_id=inp.product_id,
                risk_type="stockout",
                probability=0.0,
                severity=RiskSeverityLevel.LOW,
                expected_hours_to_event=float("inf"),
                discount_tier=DiscountTier.NONE,
            )

        # Hours of stock remaining at current demand rate
        effective_qty = max(0, inp.current_quantity - inp.safety_stock)
        hours_of_stock = effective_qty / hourly_demand

        # Risk window: need stock to last through lead time + safety headroom,
        # expanded when forecast uncertainty is elevated (low confidence).
        confidence = max(0.0, min(1.0, inp.forecast_confidence))
        uncertainty = 1.0 - confidence
        uncertainty_multiplier = 1.0 + (uncertainty * self.config.uncertainty_weight)
        safe_window = inp.lead_time_hours * self.config.safety_headroom_factor * uncertainty_multiplier

        if hours_of_stock <= 0:
            probability = 1.0
        elif hours_of_stock >= safe_window:
            # Plenty of stock — safe
            probability = 0.0
        else:
            # Linear ramp: 0 at safe_window, 1 at hours_of_stock=0
            probability = 1.0 - (hours_of_stock / safe_window)

        probability = max(0.0, min(1.0, probability))

        if probability >= self.config.stockout_critical_threshold:
            severity = RiskSeverityLevel.CRITICAL
        elif probability >= self.config.stockout_warning_threshold:
            severity = RiskSeverityLevel.WARNING
        else:
            severity = RiskSeverityLevel.LOW

        return RiskResult(
            store_id=inp.store_id,
            product_id=inp.product_id,
            risk_type="stockout",
            probability=round(probability, 4),
            severity=severity,
            expected_hours_to_event=round(hours_of_stock, 2),
            discount_tier=DiscountTier.NONE,
        )


# ---------------------------------------------------------------------------
# Spoilage Calculator
# ---------------------------------------------------------------------------

class SpoilageCalculator:
    """Evaluates spoilage risk for expiring batches.

    Supports both single-batch legacy input and FIFO multi-batch cumulative evaluation.
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()

    def evaluate(self, inp: SpoilageInput) -> RiskResult:
        """Evaluate single-batch spoilage input."""
        batch_info = BatchInfo(
            batch_id=uuid.uuid4(),
            quantity=inp.at_risk_quantity,
            hours_to_expiry=inp.min_hours_to_expiry,
        )
        hourly_demand = inp.forecast_demand_before_expiry / max(0.001, inp.min_hours_to_expiry)
        multi_inp = MultiBatchSpoilageInput(
            store_id=inp.store_id,
            product_id=inp.product_id,
            batches=[batch_info],
            hourly_demand=hourly_demand,
            shelf_life_hours=inp.shelf_life_hours,
        )
        return self.evaluate_batches(multi_inp)

    def evaluate_batches(self, inp: MultiBatchSpoilageInput) -> RiskResult:
        """Evaluate multiple batches under FIFO cumulative depletion."""
        active_batches = [b for b in inp.batches if b.quantity > 0 and b.hours_to_expiry > 0]
        total_quantity = sum(b.quantity for b in active_batches)

        if not active_batches or total_quantity <= 0:
            return RiskResult(
                store_id=inp.store_id,
                product_id=inp.product_id,
                risk_type="spoilage",
                probability=0.0,
                severity=RiskSeverityLevel.LOW,
                expected_hours_to_event=float("inf"),
                discount_tier=DiscountTier.NONE,
                net_spoilage_quantity=0,
            )

        # Sort batches by expiry ascending (FIFO consumption)
        sorted_batches = sorted(active_batches, key=lambda b: b.hours_to_expiry)
        earliest_hours = sorted_batches[0].hours_to_expiry

        hourly_demand = max(0.0, inp.hourly_demand)

        # Zero demand special case: 100% of stock spoils
        if hourly_demand <= 0:
            net_spoilage = total_quantity
            urgency = max(0.0, 1.0 - (earliest_hours / max(1.0, float(inp.shelf_life_hours))))
            probability = min(
                1.0,
                1.0 * self.config.spoilage_fraction_weight + urgency * self.config.spoilage_urgency_weight
            )
            severity = (
                RiskSeverityLevel.CRITICAL
                if probability >= self.config.spoilage_critical_threshold
                else RiskSeverityLevel.WARNING
            )
            return RiskResult(
                store_id=inp.store_id,
                product_id=inp.product_id,
                risk_type="spoilage",
                probability=round(probability, 4),
                severity=severity,
                expected_hours_to_event=round(earliest_hours, 2),
                discount_tier=discount_tier_for_hours(earliest_hours),
                net_spoilage_quantity=net_spoilage,
            )

        # FIFO cumulative consumption calculation
        cum_qty = 0
        max_spoilage = 0
        earliest_at_risk_hours = earliest_hours
        found_at_risk = False

        for b in sorted_batches:
            cum_qty += b.quantity
            cum_demand = hourly_demand * b.hours_to_expiry
            at_risk = max(0, cum_qty - int(cum_demand))
            if at_risk > 0:
                if not found_at_risk:
                    earliest_at_risk_hours = b.hours_to_expiry
                    found_at_risk = True
                if at_risk > max_spoilage:
                    max_spoilage = at_risk

        net_spoilage = max_spoilage

        if net_spoilage <= 0:
            return RiskResult(
                store_id=inp.store_id,
                product_id=inp.product_id,
                risk_type="spoilage",
                probability=0.0,
                severity=RiskSeverityLevel.LOW,
                expected_hours_to_event=round(earliest_hours, 2),
                discount_tier=DiscountTier.NONE,
                net_spoilage_quantity=0,
            )

        spoilage_fraction = net_spoilage / total_quantity
        urgency = max(0.0, 1.0 - (earliest_at_risk_hours / max(1.0, float(inp.shelf_life_hours))))
        probability = min(
            1.0,
            spoilage_fraction * self.config.spoilage_fraction_weight
            + urgency * self.config.spoilage_urgency_weight
        )

        if probability >= self.config.spoilage_critical_threshold:
            severity = RiskSeverityLevel.CRITICAL
        elif probability >= self.config.spoilage_warning_threshold:
            severity = RiskSeverityLevel.WARNING
        else:
            severity = RiskSeverityLevel.LOW

        tier = discount_tier_for_hours(earliest_at_risk_hours)

        return RiskResult(
            store_id=inp.store_id,
            product_id=inp.product_id,
            risk_type="spoilage",
            probability=round(probability, 4),
            severity=severity,
            expected_hours_to_event=round(earliest_at_risk_hours, 2),
            discount_tier=tier,
            net_spoilage_quantity=net_spoilage,
        )

