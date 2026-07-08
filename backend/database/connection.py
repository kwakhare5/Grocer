from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.config import settings

# Explicit pool sizing + pre-ping for a long-running API process.
# (Previous comment claimed NullPool but never actually passed poolclass —
# NullPool is correct for Alembic's short-lived env.py, not for this engine.)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # avoids stale-connection errors after DB idle periods
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False
)



async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from backend.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_checkpointer():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return AsyncPostgresSaver.from_conn_string(db_url)

