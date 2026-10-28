"""Grocer v1.0 — FastAPI Application Setup & Channel Routing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.channels.swiggy_auth import router as swiggy_auth_router
from backend.channels.whatsapp import router as whatsapp_router
from backend.config import settings
from backend.database import (
    apply_migrations,
    check_db_health,
    close_db_pool,
    get_db_pool,
)
from backend.integrations.commerce.swiggy_client import SwiggyAuthExpiredError

logger = logging.getLogger("grocer.main")


async def _run_delivery_poller_loop() -> None:
    """Periodically poll in-flight deliveries across dark stores and push milestone updates."""
    from backend.agent.checkout_executor import poll_in_flight_deliveries_batch
    from backend.channels.whatsapp_client import WhatsAppClient

    wa_client = WhatsAppClient()
    while True:
        try:
            await asyncio.sleep(30)
            pool = await get_db_pool()
            notes = await poll_in_flight_deliveries_batch(pool=pool)
            for note in notes:
                async with pool.acquire() as conn:
                    wa_id = await conn.fetchval(
                        """
                        SELECT u.wa_id
                        FROM grocer.checkouts c
                        JOIN grocer.users u ON c.user_id = u.id
                        WHERE c.swiggy_order_id = $1 OR c.swiggy_order_ids ? $1
                        LIMIT 1;
                        """,
                        note.order_id,
                    )
                    if wa_id:
                        await wa_client.send_text_message(to_wa_id=wa_id, text=note.message)
        except asyncio.CancelledError:
            break
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            RuntimeError,
            asyncpg.PostgresError,
            OSError,
            SwiggyAuthExpiredError,
        ) as exc:
            logger.warning("Background delivery poller error: %s", exc)


async def _run_payment_poller_loop() -> None:
    """Settle paid checkouts by polling Swiggy with each customer's own token."""
    from backend.agent.checkout_executor import poll_pending_checkouts_batch
    from backend.channels.whatsapp_client import WhatsAppClient

    wa_client = WhatsAppClient()
    while True:
        try:
            await asyncio.sleep(15)
            pool = await get_db_pool()
            results = await poll_pending_checkouts_batch(pool=pool)
            for res in results:
                if not res.confirmed or not res.message:
                    continue
                wa_id = await pool.fetchval(
                    """
                    SELECT u.wa_id
                    FROM grocer.checkouts c
                    JOIN grocer.users u ON c.user_id = u.id
                    WHERE c.swiggy_order_id = $1
                    LIMIT 1;
                    """,
                    res.order_id,
                )
                if wa_id:
                    await wa_client.send_text_message(to_wa_id=wa_id, text=res.message)
        except asyncio.CancelledError:
            break
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            RuntimeError,
            asyncpg.PostgresError,
            OSError,
            SwiggyAuthExpiredError,
        ) as exc:
            logger.warning("Background payment poller error: %s", exc)


async def _run_dpdp_scrubber_loop() -> None:
    """Periodically run 24-hour DPDP compliance data scrubber."""
    from backend.agent.dpdp import run_24h_dpdp_scrubber

    while True:
        try:
            await asyncio.sleep(3600)  # Hourly
            pool = await get_db_pool()
            await run_24h_dpdp_scrubber(pool)
        except asyncio.CancelledError:
            break
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            RuntimeError,
            asyncpg.PostgresError,
            OSError,
            SwiggyAuthExpiredError,
        ) as exc:
            logger.warning("Background DPDP scrubber error: %s", exc)


async def _prepare_database() -> None:
    """Apply migrations first, then open the restricted app pool."""
    applied = await apply_migrations()
    if applied:
        logger.info("Applied migrations: %s", ", ".join(applied))
    await get_db_pool()


async def _retry_schema_when_ready() -> None:
    """Retry startup migrations with backoff until the database is ready."""
    delay = 30
    while True:
        await asyncio.sleep(delay)
        try:
            await _prepare_database()
            return
        except asyncio.CancelledError:
            raise
        except (
            asyncpg.PostgresError,
            OSError,
            TimeoutError,
            ValueError,
            RuntimeError,
        ) as exc:
            logger.warning(
                "Database still not ready for migrations: %s; retrying in %ss",
                exc,
                min(delay * 2, 300),
            )
            delay = min(delay * 2, 300)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    schema_task: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(_prepare_database(), timeout=5.0)
    except TimeoutError:
        logger.error(
            "Database not ready within 5s; serving with /health reporting down."
        )
        schema_task = asyncio.create_task(_retry_schema_when_ready())
    except (
        asyncpg.PostgresError,
        OSError,
        ValueError,
        RuntimeError,
    ) as exc:
        # Serve anyway so /health can report the truth and recover on wake.
        logger.error("Database unavailable at startup; /health will report down: %s", exc)
        schema_task = asyncio.create_task(_retry_schema_when_ready())

    poller_task = asyncio.create_task(_run_delivery_poller_loop())
    payment_task = asyncio.create_task(_run_payment_poller_loop())
    dpdp_task = asyncio.create_task(_run_dpdp_scrubber_loop())
    yield
    poller_task.cancel()
    payment_task.cancel()
    dpdp_task.cancel()
    if schema_task is not None:
        schema_task.cancel()
    await asyncio.gather(
        poller_task,
        payment_task,
        dpdp_task,
        *([schema_task] if schema_task is not None else []),
        return_exceptions=True,
    )
    await close_db_pool()


app = FastAPI(
    title=settings.APP_NAME,
    description="WhatsApp Swiggy Instamart Concierge & Account Manager",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route Mounts
app.include_router(whatsapp_router)
app.include_router(swiggy_auth_router)


def health_response(db_ok: bool) -> JSONResponse:
    """Healthy means the API can reach PostgreSQL, not just that the process is up."""
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": "healthy" if db_ok else "down",
            "database": "connected" if db_ok else "unreachable",
            "app": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
        },
    )


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint confirming API and PostgreSQL availability."""
    return health_response(await check_db_health())
