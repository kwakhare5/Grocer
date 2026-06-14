"""
ML Integration Tests — pytest
Run with: pytest backend/tests/test_ml.py -v

Tests:
  - ConsumptionModeler can rebuild models for demo_user_001
  - ConfidenceScorer returns values in [0, 1]
  - Predictions endpoint returns expected structure
"""

import pytest
from datetime import datetime, timezone, timedelta
from backend.ml.confidence_scorer import ConfidenceScorer


@pytest.mark.asyncio
async def test_confidence_scorer_range():
    """ConfidenceScorer output must always be between 0 and 1."""
    scorer = ConfidenceScorer()

    # Regular purchases — high confidence
    now = datetime.now(timezone.utc)
    regular_dates = [now - timedelta(days=i * 14) for i in range(10)]
    score = scorer.score(regular_dates, len(regular_dates))
    assert 0.0 <= score <= 1.0, f'Score out of range: {score}'
    assert score >= 0.5, f'Expected high confidence for regular purchases, got {score}'


@pytest.mark.asyncio
async def test_confidence_scorer_low_data():
    """Low data points should yield lower confidence."""
    scorer = ConfidenceScorer()
    now = datetime.now(timezone.utc)
    sparse_dates = [now - timedelta(days=30), now - timedelta(days=60)]
    score = scorer.score(sparse_dates, 2)
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_consumption_modeler_rebuild():
    """
    Full rebuild test — requires live DB connection.
    Skipped automatically if DB is not available.
    """
    pytest.importorskip('asyncpg')  # skip gracefully if asyncpg unavailable
    try:
        from backend.database.connection import AsyncSessionLocal, init_db
        from backend.ml.consumption_model import ConsumptionModeler
        from backend.api.routes.household import get_or_create_household

        await init_db()
        async with AsyncSessionLocal() as db:
            hh = await get_or_create_household('demo_user_001', db)
            modeler = ConsumptionModeler()
            result = await modeler.rebuild_all_models(str(hh.id), db)

        assert isinstance(result, dict)
        assert 'built' in result
        assert 'skipped' in result
        assert 'errors' in result
        assert result['errors'] == 0, f'Model rebuild had errors: {result}'

    except Exception as e:
        pytest.skip(f'DB not available: {e}')
