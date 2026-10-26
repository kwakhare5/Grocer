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

from backend.channels.swiggy_auth import router as swiggy_auth_router
from backend.channels.whatsapp import router as whatsapp_router
from backend.config import settings
from backend.database import check_db_health, close_db_pool, get_db_pool

logger = logging.getLogger("grocer.main")


async def _run_delivery_poller_loop() -> None:
    """Periodically poll in-flight deliveries across dark stores and push milestone updates."""
    from backend.agent.checkout_executor import poll_in_flight_deliveries_batch
    from backend.channels.whatsapp_client import WhatsAppClient
    from backend.integrations.commerce.swiggy_client import SwiggyClient

    swiggy = SwiggyClient()
    wa_client = WhatsAppClient()
    while True:
        try:
            await asyncio.sleep(30)
            pool = await get_db_pool()
            notes = await poll_in_flight_deliveries_batch(pool=pool, swiggy_client=swiggy)
            for note in notes:
                async with pool.acquire() as conn:
                    wa_id = await conn.fetchval(
                        """
                        SELECT u.wa_id
                        FROM grocer.checkouts c
                        JOIN grocer.users u ON c.user_id = u.id
                        WHERE c.swiggy_order_id = $1;
                        """,
                        note.order_id,
                    )
                    if wa_id:
                        await wa_client.send_text_message(to_wa_id=wa_id, text=note.message)
        except asyncio.CancelledError:
            break
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError, asyncpg.PostgresError, OSError) as exc:
            logger.warning("Background delivery poller error: %s", exc)


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
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError, asyncpg.PostgresError, OSError) as exc:
            logger.warning("Background DPDP scrubber error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    await get_db_pool()
    poller_task = asyncio.create_task(_run_delivery_poller_loop())
    dpdp_task = asyncio.create_task(_run_dpdp_scrubber_loop())
    yield
    poller_task.cancel()
    dpdp_task.cancel()
    await asyncio.gather(poller_task, dpdp_task, return_exceptions=True)
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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint confirming API and PostgreSQL availability."""
    db_ok = await check_db_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }
