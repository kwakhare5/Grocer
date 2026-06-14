from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.config import settings

# Why: echo=False — suppress SQL logs in production; NullPool avoids connection leaks with alembic
engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
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

