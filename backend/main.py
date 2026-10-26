"""Grocer v1.0 — FastAPI Application Setup & Channel Routing."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.channels.swiggy_auth import router as swiggy_auth_router
from backend.channels.whatsapp import router as whatsapp_router
from backend.config import settings
from backend.database import check_db_health, close_db_pool, get_db_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    await get_db_pool()
    yield
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
