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

# Severity thresholds for stockout
_STOCKOUT_CRITICAL_THRESHOLD = 0.7
_STOCKOUT_WARNING_THRESHOLD  = 0.3

# Hours headroom to consider "safe" (relative to lead time)
_SAFETY_HEADROOM_FACTOR = 1.5


class StockoutCalculator:
    """Evaluates stockout risk from current inventory vs forecast demand.

    Algorithm:
    1. Compute hours-to-stockout from daily demand rate.
    2. Compare to supplier lead_time_hours.
    3. Calculate probability based on how far below lead time we are.
    4. Map probability to severity tier.
    """

    def evaluate(self, inp: StockoutInput) -> RiskResult:
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

        # Risk window: need stock to last through the full lead time + safety headroom
        safe_window = inp.lead_time_hours * _SAFETY_HEADROOM_FACTOR

        if hours_of_stock <= 0:
            probability = 1.0
        elif hours_of_stock >= safe_window:
            # Plenty of stock — scale probability smoothly from near-safe to safe
            probability = 0.0
        else:
            # Linear ramp: 0 at safe_window, 1 at hours_of_stock=0
            probability = 1.0 - (hours_of_stock / safe_window)

        probability = max(0.0, min(1.0, probability))

        if probability >= _STOCKOUT_CRITICAL_THRESHOLD:
            severity = RiskSeverityLevel.CRITICAL
        elif probability >= _STOCKOUT_WARNING_THRESHOLD:
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

# Severity thresholds for spoilage
_SPOILAGE_CRITICAL_THRESHOLD = 0.65
_SPOILAGE_WARNING_THRESHOLD  = 0.25


class SpoilageCalculator:
    """Evaluates spoilage risk for a batch about to expire.

    Algorithm:
    1. Compute net_spoilage_quantity = max(0, at_risk_quantity - forecast_sell_through).
    2. Probability scales with (net_spoilage / at_risk_quantity) and urgency (hours to expiry).
    3. Assign discount tier per spec §14.3.
    4. Map probability to severity tier.
    """

    def evaluate(self, inp: SpoilageInput) -> RiskResult:
        net_spoilage = max(
            0,
            inp.at_risk_quantity - int(inp.forecast_demand_before_expiry)
        )

        # No at-risk stock at all
        if inp.at_risk_quantity <= 0 or inp.total_quantity <= 0:
            return RiskResult(
                store_id=inp.store_id,
                product_id=inp.product_id,
                risk_type="spoilage",
                probability=0.0,
                severity=RiskSeverityLevel.LOW,
                expected_hours_to_event=inp.min_hours_to_expiry,
                discount_tier=DiscountTier.NONE,
                net_spoilage_quantity=0,
            )

        # Fraction of at-risk stock that will spoil
        spoilage_fraction = net_spoilage / inp.at_risk_quantity

        # Urgency factor: expiry closer → higher urgency
        # Normalised to shelf life: 0h → urgency=1, shelf_life_hours → urgency=0
        urgency = max(0.0, 1.0 - (inp.min_hours_to_expiry / inp.shelf_life_hours))

        # Probability: blend of spoilage fraction and urgency
        probability = min(1.0, spoilage_fraction * 0.6 + urgency * 0.4)

        if probability >= _SPOILAGE_CRITICAL_THRESHOLD:
            severity = RiskSeverityLevel.CRITICAL
        elif probability >= _SPOILAGE_WARNING_THRESHOLD:
            severity = RiskSeverityLevel.WARNING
        else:
            severity = RiskSeverityLevel.LOW

        tier = discount_tier_for_hours(inp.min_hours_to_expiry)

        return RiskResult(
            store_id=inp.store_id,
            product_id=inp.product_id,
            risk_type="spoilage",
            probability=round(probability, 4),
            severity=severity,
            expected_hours_to_event=round(inp.min_hours_to_expiry, 2),
            discount_tier=tier,
            net_spoilage_quantity=net_spoilage,
        )
