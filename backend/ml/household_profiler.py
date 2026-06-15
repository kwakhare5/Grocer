"""
Household Profiler — Task 2.4
Infers household composition (solo/couple/family_small/family_large) by
comparing observed daily consumption rates against pre-defined benchmarks.

Why benchmark-based vs ML-based?
  With only 4 months of data and a small number of households, a lookup
  table approach is more reliable than a classifier. The benchmarks are
  sourced from CLAUDE.md and reflect typical Indian household consumption.

How it's used:
  Called after every model rebuild to update Household.composition and
  Household.composition_confidence in the DB.
"""

import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ConsumptionModel, Household

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Benchmark daily consumption rates (in standard units per day)
# Source: IMPLEMENTATION_PLAN.md Task 2.4 + CLAUDE.md Feature 5
# Keys = item_ids from unified catalog (backend/seed/catalog.py)
# ------------------------------------------------------------------
BENCHMARKS: dict[str, dict[str, float]] = {
    "solo": {
        "INS_001": 0.25,   # Milk: 250ml/day
        "INS_002": 0.07,   # Atta: 70g/day
        "INS_005": 0.70,   # Eggs: 0.7/day
        "INS_003": 0.020,  # Oil: 20ml/day
    },
    "couple": {
        "INS_001": 0.50,
        "INS_002": 0.15,
        "INS_005": 1.50,
        "INS_003": 0.040,
    },
    "family_small": {
        "INS_001": 1.00,   # Milk: 1L/day — 3-4 people
        "INS_002": 0.30,   # Atta: 300g/day
        "INS_005": 2.50,   # Eggs: 2.5/day
        "INS_003": 0.068,  # Oil: 68ml/day
    },
    "family_large": {
        "INS_001": 2.00,
        "INS_002": 0.60,
        "INS_005": 5.00,
        "INS_003": 0.130,
    },
}

DISPLAY_NAMES: dict[str, str] = {
    "solo":         "Solo (1 person)",
    "couple":       "Couple (2 people)",
    "family_small": "Family (3-4 people)",
    "family_large": "Large Family (5+)",
}


async def infer_composition(household_id: str, db: AsyncSession) -> dict:
    """
    Compare household's observed consumption rates to benchmark profiles.
    Returns the best-matching profile with a confidence score.

    Score per profile: average of per-item match scores (1.0 = perfect match).
    A match score of 0.80 means the household's usage is within 20% of the benchmark.

    Returns:
        {
            "composition": "family_small",
            "display_name": "Family (3-4 people)",
            "confidence": 0.84,
            "all_scores": {"solo": 0.12, "couple": 0.45, "family_small": 0.84, ...}
        }
    """
    result = await db.execute(
        select(ConsumptionModel.item_id, ConsumptionModel.avg_daily_consumption)
        .where(ConsumptionModel.household_id == household_id)
    )
    models = result.all()

    if not models:
        logger.warning(f"No consumption models found for household {household_id}. Cannot infer composition.")
        return {"composition": None, "confidence": 0.0, "display_name": "Unknown", "all_scores": {}}

    # Build lookup: item_id → observed daily consumption
    observed: dict[str, float] = {row.item_id: row.avg_daily_consumption for row in models}

    scores: dict[str, float] = {}
    for hh_type, bench in BENCHMARKS.items():
        match_parts = []
        for item_id, expected in bench.items():
            if item_id in observed and expected > 0:
                ratio = observed[item_id] / expected
                # Score: 1.0 at perfect match, 0.0 if consumption is 2x off in either direction
                match_parts.append(max(0.0, 1.0 - abs(1.0 - ratio)))
        # Average over items that were found; 0 if no matching items
        scores[hh_type] = sum(match_parts) / max(len(match_parts), 1) if match_parts else 0.0

    best = max(scores, key=lambda k: scores[k])
    confidence = round(scores[best], 2)

    logger.info(
        f"Household {household_id} inferred as '{best}' "
        f"({DISPLAY_NAMES[best]}) with {confidence*100:.0f}% confidence. "
        f"Scores: {scores}"
    )

    return {
        "composition":  best,
        "display_name": DISPLAY_NAMES[best],
        "confidence":   confidence,
        "all_scores":   {k: round(v, 2) for k, v in scores.items()},
    }


async def update_household_profile(household_id: str, db: AsyncSession) -> dict:
    """
    Run `infer_composition` and persist the result to the Household table.
    Called after every `rebuild_all_models` to keep the profile fresh.

    Returns the inference result dict.
    """
    result = await infer_composition(household_id, db)

    if result["composition"] is not None:
        await db.execute(
            update(Household)
            .where(Household.id == household_id)
            .values(
                composition=result["composition"],
                composition_confidence=result["confidence"],
            )
        )
        await db.commit()
        logger.info(f"Updated household {household_id} profile in DB: {result['composition']}")

    return result
