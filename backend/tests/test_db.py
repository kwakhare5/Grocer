"""
DB Integration Tests — pytest
Run with: pytest backend/tests/test_db.py -v

Tests:
  - ConsumptionModel table is readable and returns expected columns
  - RestockAlert table columns match the SQLAlchemy model definition
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from backend.database.connection import AsyncSessionLocal, init_db
from backend.database.models import ConsumptionModel, RestockAlert
from sqlalchemy import select


@pytest.fixture(scope='module')
async def db():
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_consumption_model_readable():
    """Verify ConsumptionModel table can be queried without errors."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ConsumptionModel.item_name, ConsumptionModel.confidence_score))
        rows = result.mappings().all()
    # Table should exist and be queryable (may be empty in fresh env)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_restock_alert_schema():
    """Verify RestockAlert model columns match actual DB columns."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'restock_alerts'
            ORDER BY ordinal_position
        """))
        db_columns = {row[0] for row in result}

    expected_columns = {'id', 'household_id', 'item_ids', 'message_sent', 'sent_at', 'status', 'acted_at', 'order_id_placed'}
    assert expected_columns.issubset(db_columns), (
        f'Missing columns in DB: {expected_columns - db_columns}'
    )


@pytest.mark.asyncio
async def test_price_history_schema():
    """Verify price_history hypertable columns exist."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'price_history'
        """))
        db_columns = {row[0] for row in result}

    assert 'item_id' in db_columns
    assert 'recorded_at' in db_columns
    assert 'price' in db_columns
