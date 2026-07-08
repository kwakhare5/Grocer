import os
# ruff: noqa: E402
import pytest
import asyncio
from sqlalchemy.pool import StaticPool
import sqlalchemy.ext.asyncio

# Configure DATABASE_URL for sqlite in-memory shared cache before importing other files
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"

# Monkeypatch SQLiteTypeCompiler to handle PostgreSQL JSONB and UUID types in SQLite
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
setattr(SQLiteTypeCompiler, "visit_JSONB", lambda self, type_, **kw: "JSON")
setattr(SQLiteTypeCompiler, "visit_UUID", lambda self, type_, **kw: "TEXT")

# Monkeypatch SQLAlchemy UUID column bind processors to accept strings gracefully
import sqlalchemy.dialects.postgresql
import sqlalchemy.sql.sqltypes

for uuid_cls in [sqlalchemy.dialects.postgresql.UUID, sqlalchemy.sql.sqltypes.UUID]:
    original_bind_processor = uuid_cls.bind_processor
    def make_mock_bind(orig_bind):
        def mock_bind(self, dialect):
            proc = orig_bind(self, dialect)
            if proc is None:
                return proc
            def safe_proc(value):
                if isinstance(value, str):
                    return value
                try:
                    return proc(value)
                except AttributeError:
                    return value
            return safe_proc
        return mock_bind
    uuid_cls.bind_processor = make_mock_bind(original_bind_processor)

# Force all async engines in tests to use StaticPool
original_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine

def mock_create_async_engine(*args, **kwargs):
    kwargs["poolclass"] = StaticPool
    kwargs.pop("pool_size", None)
    kwargs.pop("max_overflow", None)
    kwargs.pop("pool_pre_ping", None)
    return original_create_async_engine(*args, **kwargs)

sqlalchemy.ext.asyncio.create_async_engine = mock_create_async_engine

# Mock PreFillMCPClient methods to avoid network requests during tests
from backend.seed.catalog import CATALOG as MOCK_CATALOG

async def mock_search_platform_items(self, query: str) -> dict:
    query_str = query.lower()
    results = [item for item in MOCK_CATALOG if query_str in str(item.get("name") or "").lower() or query_str in str(item.get("category") or "").lower()]
    return {"items": results if results else MOCK_CATALOG[:3]}

async def mock_get_platform_orders(self, user_id: str, limit: int = 200) -> dict:
    import json
    # Determine the seed file location relative to this test file
    seed_file = os.path.join(os.path.dirname(__file__), "..", "seed", "generated_orders.json")
    orders = []
    if os.path.exists(seed_file):
        with open(seed_file) as f:
            orders = json.load(f)
    return {
        "success": True,
        "user_id": user_id,
        "total_orders": len(orders),
        "orders": orders[-limit:]
    }

async def mock_update_platform_cart(self, items: list) -> dict:
    import uuid
    cart_id = f"CART_{str(uuid.uuid4())[:8]}"
    total = sum(item.get("price", 50) * item.get("quantity", 1) for item in items)
    return {"success": True, "cart_id": cart_id, "items": items, "total": total}

async def mock_place_platform_order(self, cart_id: str) -> dict:
    import random
    order_id = f"INS_{random.randint(10000, 99999)}"
    return {
        "success": True,
        "order_id": order_id,
        "cart_id": cart_id,
        "status": "placed",
        "platform": "instamart",
        "placed_at": "2026-06-15T00:00:00"
    }

from backend.mcp.client import PreFillMCPClient
PreFillMCPClient.search_platform_items = mock_search_platform_items
PreFillMCPClient.get_platform_orders = mock_get_platform_orders
PreFillMCPClient.update_platform_cart = mock_update_platform_cart
PreFillMCPClient.place_platform_order = mock_place_platform_order

# Mock get_checkpointer to prevent it from connecting to PostgreSQL
from langgraph.checkpoint.memory import MemorySaver

class MockCheckpointerCtx:
    def __init__(self, saver):
        self.saver = saver
    async def __aenter__(self):
        if not hasattr(self.saver, "setup"):
            async def dummy_setup():
                pass
            self.saver.setup = dummy_setup
        return self.saver
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

shared_saver = MemorySaver()

async def mock_get_checkpointer():
    return MockCheckpointerCtx(shared_saver)

import backend.database.connection
backend.database.connection.get_checkpointer = mock_get_checkpointer  # type: ignore

# Mock LLM Client to avoid actual network calls
from langchain_core.messages import AIMessage
import json

class MockLLM:
    def with_structured_output(self, schema):
        self._schema = schema
        return self
        
    def with_config(self, config):
        return self
        
    async def ainvoke(self, messages, *args, **kwargs):
        # Determine behavior based on the prompt content
        content = ""
        if messages and len(messages) > 0:
            prompt = messages[0].content.lower()
            if "recipe" in prompt:
                # Return dummy recipe ingredients
                if hasattr(self, '_schema'):
                    # Using Pydantic structured output
                    return self._schema(ingredients=[
                        {"name": "mock ingredient 1", "quantity": 1.0, "unit": "kg"},
                        {"name": "mock ingredient 2", "quantity": 500, "unit": "g"}
                    ])
                else:
                    content = json.dumps([
                        {"name": "mock ingredient 1", "quantity": 1.0, "unit": "kg"},
                        {"name": "mock ingredient 2", "quantity": 500, "unit": "g"}
                    ])
            elif "analyze their reply" in prompt:
                # Mock restock agent parsing
                content = json.dumps({"wanted": [], "unrecognized": False})
            elif "extract" in prompt and "order" in prompt:
                # Mock order intent parsing
                content = json.dumps({"items": [], "not_an_order": False})
            else:
                content = "Mocked LLM response"
                
        return AIMessage(content=content)

def mock_get_llm():
    return MockLLM()

import backend.agents.llm_client
import backend.agents.restock_agent
import backend.agents.recipe_agent

backend.agents.llm_client.get_llm = mock_get_llm
backend.agents.restock_agent.get_llm = mock_get_llm
backend.agents.recipe_agent.get_llm = mock_get_llm


from backend.database.connection import engine, init_db

@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Keep one connection alive for the session so the memory DB is not wiped
@pytest.fixture(scope="session", autouse=True)
async def setup_test_db(event_loop):
    async with engine.connect() as conn:
        # Create all tables
        await init_db()
        
        # Seed basic demo user household
        from backend.database.models import Household
        from sqlalchemy.ext.asyncio import async_sessionmaker
        
        async_session = async_sessionmaker(
            engine, expire_on_commit=False
        )
        async with async_session() as session:
            # Check if demo_user_001 already exists
            from sqlalchemy import select
            res = await session.execute(select(Household).where(Household.user_id == 'demo_user_001'))
            if not res.scalar_one_or_none():
                hh = Household(
                    user_id='demo_user_001', 
                    phone_number='+919999999999', 
                    composition='family_small', 
                    intelligence_consent=True
                )
                session.add(hh)
                await session.commit()
        
        yield conn  # keep connection open during the session

@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    # Bypassed engine.dispose() to prevent in-memory SQLite wipe
    pass
