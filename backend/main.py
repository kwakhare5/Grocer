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
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.api.whatsapp import drain_message_queue
from backend.api.health import router as health_router
from backend.api.whatsapp import router as whatsapp_router
from backend.api.oauth import router as oauth_router
from backend.api.simulator import router as simulator_router

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


async def _replenishment_worker(app: FastAPI) -> None:
    """Refresh consented purchase patterns without delaying inbound WhatsApp turns."""
    while True:
        try:
            await app.state.agent_engine.replenishment_store.refresh_due(
                app.state.agent_engine.commerce
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Consented purchase history refresh failed; it will retry.")
        await asyncio.sleep(60)


async def _payment_worker(app: FastAPI) -> None:
    """Resume pending UPI payments from PostgreSQL after process restarts."""
    while True:
        try:
            await app.state.agent_engine.attempt_store.reconcile_due_payment(
                app.state.agent_engine.commerce
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Pending payment reconciliation failed; it will retry.")
        await asyncio.sleep(2)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Attach optional durable state without hiding database startup failures."""
    pool = None
    worker = None
    replenishment_worker = None
    payment_worker = None
    is_live_swiggy = settings.COMMERCE_ADAPTER_TYPE.lower() == "swiggy_mcp"
    if settings.CHECKOUT_MODE == "live" and not settings.LIVE_CHECKOUT_ENABLED:
        raise RuntimeError("Live checkout is release-gated. Keep CHECKOUT_MODE=review.")
    if settings.SIMULATOR_ENABLED and (not settings.DATABASE_URL or settings.CHECKOUT_MODE != "review"):
        raise RuntimeError("Local simulator requires PostgreSQL and review-only checkout.")
    force_mock = False
    if is_live_swiggy and not settings.DATABASE_URL:
        logger.warning("DATABASE_URL is not configured; using MockCommerceAdapter for local simulation.")
        force_mock = True
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
                               "task_state", "privacy_deletions", "replenishment")
            for table in required_tables:
                if await pool.fetchval("SELECT to_regclass($1)", f"grocer_internal.{table}") is None:
                    raise RuntimeError(f"Missing database table grocer_internal.{table}; apply migrations first.")
            required_columns = {
                "inbound_messages": ("claimed_at",),
                "outbound_messages": ("sending_started_at", "payment_attempt_id"),
                "checkout_attempts": ("next_payment_check_at", "payment_deadline_at"),
                "replenishment": ("next_sync_at", "paused"),
            }
            for table, columns in required_columns.items():
                for column in columns:
                    present = await pool.fetchval(
                        """SELECT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_schema='grocer_internal' AND table_name=$1 AND column_name=$2)""",
                        table, column,
                    )
                    if not present:
                        raise RuntimeError(f"Missing grocer_internal.{table}.{column}; apply migrations first.")
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
    previous_record_only = default_whatsapp_adapter.record_only
    if settings.SIMULATOR_ENABLED:
        default_whatsapp_adapter.record_only = True
    if settings.AGENT_ROUTE_ENABLED:
        from backend.agent.engine import GroceryAgentEngine
        from backend.agent.checkout_attempts import PostgresCheckoutAttemptStore
        from backend.agent.task_state import PostgresTaskStateStore
        from backend.agent.replenishment import PostgresReplenishmentStore
        app.state.agent_engine = GroceryAgentEngine(
            get_commerce_adapter(force_mock=force_mock),
            attempt_store=PostgresCheckoutAttemptStore(pool) if pool is not None else None,
            state_store=PostgresTaskStateStore(pool, settings.DATA_ENCRYPTION_KEY) if pool is not None else None,
            replenishment_store=PostgresReplenishmentStore(pool, settings.DATA_ENCRYPTION_KEY) if pool is not None else None,
        )
        if pool is not None:
            worker = asyncio.create_task(_message_worker(app))
            replenishment_worker = asyncio.create_task(_replenishment_worker(app))
            if settings.CHECKOUT_MODE == "live":
                payment_worker = asyncio.create_task(_payment_worker(app))
    try:
        yield
    finally:
        default_whatsapp_adapter.record_only = previous_record_only
        if worker is not None:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        if replenishment_worker is not None:
            replenishment_worker.cancel()
            try:
                await replenishment_worker
            except asyncio.CancelledError:
                pass
        if payment_worker is not None:
            payment_worker.cancel()
            try:
                await payment_worker
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
    if settings.SIMULATOR_ENABLED:
        if (not settings.SIMULATOR_ACCESS_TOKEN or len(settings.SIMULATOR_ACCESS_TOKEN) < 16
                or not settings.SIMULATOR_SENDER_ID):
            raise RuntimeError("Local simulator requires a private access token and fixed sender ID.")
        app.include_router(simulator_router)

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
