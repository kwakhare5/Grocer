# OPERATIONS RESIDUE — DECOUPLED FROM GROCER v2
# Dark-store risk detection engine (spoilage/stockout). Belongs in kwakhare5/Dark-store-operator.

from backend.services.risk.engine import RiskEngine
from backend.services.risk.models import (
    DiscountTier,
    RiskResult,
    RiskSeverityLevel,
    SpoilageCalculator,
    SpoilageInput,
    StockoutCalculator,
    StockoutInput,
    discount_tier_for_hours,
)

__all__ = [
    "RiskEngine",
    "StockoutInput",
    "SpoilageInput",
    "StockoutCalculator",
    "SpoilageCalculator",
    "RiskResult",
    "RiskSeverityLevel",
    "DiscountTier",
    "discount_tier_for_hours",
]
