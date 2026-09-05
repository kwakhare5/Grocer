import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.database import Base, get_db
from backend.main import create_app

from sqlalchemy import event
from sqlalchemy.pool import NullPool

# Use a test database URL (SQLite async for fast isolated tests)
TEST_DATABASE_URL = 'sqlite+aiosqlite:///./test.db'

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=60000")
    cursor.close()


@pytest.fixture(scope='session')
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()



@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)



@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API testing."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
    ) as ac:
        yield ac
