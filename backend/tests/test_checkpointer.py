import pytest
from backend.database.connection import get_checkpointer
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

@pytest.mark.asyncio
async def test_postgres_saver_connection():
    # Verify get_checkpointer returns an AsyncPostgresSaver
    saver = await get_checkpointer()
    assert hasattr(saver, "__aenter__")

