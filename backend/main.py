from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from dotenv import load_dotenv

# Explicitly load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import create_postgres_pool
from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.swiggy_oauth import (
    PostgresPendingAuthFlowStore,
    default_oauth_manager,
)
from backend.integrations.commerce.token_vault import default_token_vault
from backend.integrations.commerce.connect_tickets import default_connect_tickets
from backend.channels.message_store import PostgresMessageStore
from backend.api.whatsapp import drain_message_queue
from backend.api.health import router as health_router
from backend.api.whatsapp import router as whatsapp_router
from backend.api.oauth import router as oauth_router

logger = logging.getLogger("grocer.main")


async def _message_worker(app: FastAPI) -> None:
    next_cleanup = 0.0
    while True:
        try:
            if time.monotonic() >= next_cleanup:
                next_cleanup = time.monotonic() + 86400
                await app.state.agent_engine.state_store.delete_expired()
                await app.state.message_store.delete_expired()
            await app.state.message_store.process_deletions(app.state.agent_engine)
            await drain_message_queue(app.state.message_store, app.state.agent_engine)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Durable WhatsApp worker failed; it will retry pending intake.")
        await asyncio.sleep(2)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Attach optional durable state without hiding database startup failures."""
    pool = None
    worker = None
    is_live_swiggy = settings.COMMERCE_ADAPTER_TYPE.lower() == "swiggy_mcp"
    if settings.CHECKOUT_MODE == "live" and not settings.LIVE_CHECKOUT_ENABLED:
        raise RuntimeError("Live checkout is release-gated. Keep CHECKOUT_MODE=review.")
    if is_live_swiggy and not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for customer-scoped Swiggy commerce.")
    if settings.DATABASE_URL and not settings.DATA_ENCRYPTION_KEY:
        raise RuntimeError(
            "DATA_ENCRYPTION_KEY is required when DATABASE_URL is configured."
        )
    if settings.DATABASE_URL:
        pool = await create_postgres_pool(
            settings.DATABASE_URL, max_size=settings.DATABASE_POOL_MAX_SIZE
        )
        try:
            required_tables = ("oauth_tokens", "oauth_pending_flows", "connect_tickets",
                               "inbound_messages", "outbound_messages", "checkout_attempts",
                               "task_state", "privacy_deletions")
            for table in required_tables:
                if await pool.fetchval("SELECT to_regclass($1)", f"grocer_internal.{table}") is None:
                    raise RuntimeError(f"Missing database table grocer_internal.{table}; apply migrations first.")
            default_connect_tickets.configure_postgres(pool)
            app.state.message_store = PostgresMessageStore(pool)
            app.state.database_pool = pool
            await default_token_vault.configure_postgres(pool, settings.DATA_ENCRYPTION_KEY)
            default_oauth_manager.configure_flow_store(
                PostgresPendingAuthFlowStore(pool, settings.DATA_ENCRYPTION_KEY)
            )
        except Exception:
            await pool.close()
            raise
    if settings.AGENT_ROUTE_ENABLED:
        from backend.agent.engine import GroceryAgentEngine
        from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
        from backend.agent.task_state import PostgresTaskStateStore
        app.state.agent_engine = GroceryAgentEngine(
            get_commerce_adapter(),
            attempt_store=PostgresCheckoutAttemptStore(pool) if pool is not None else None,
            state_store=PostgresTaskStateStore(pool, settings.DATA_ENCRYPTION_KEY) if pool is not None else None,
        )
        if pool is not None:
            worker = asyncio.create_task(_message_worker(app))
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        engine = getattr(app.state, "agent_engine", None)
        if engine is not None:
            await engine.close()
            client = getattr(engine.commerce, "_client", None)
            if client is not None and hasattr(client, "close"):
                await client.close()
        if pool is not None:
            await pool.close()


def create_app() -> FastAPI:
    """Build the GROCER API application without hidden database/runtime side effects."""
    app = FastAPI(
        title="GROCER",
        description="WhatsApp-first intent-preserving grocery commerce assistant",
        version="2.0.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(health_router)
    app.include_router(whatsapp_router)
    app.include_router(oauth_router, prefix="/api")
    app.include_router(oauth_router)

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {
            "service": "grocer",
            "version": "2.0.0",
            "status": "ok",
            "product": "intent-preserving conversational commerce",
        }

    return app


app = create_app()
