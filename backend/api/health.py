from datetime import datetime, timezone
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """Liveness only; dependency status belongs to /ready."""
    return {
        "status": "alive",
        "service": "GROCER",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check(request: Request) -> JSONResponse:
    """State whether this instance can accept signed WhatsApp traffic safely."""
    missing: list[str] = []
    if not settings.GEMINI_API_KEY:
        missing.append("gemini_key")
    if not settings.DATABASE_URL or getattr(request.app.state, "database_pool", None) is None:
        missing.append("database")
    if not settings.DATA_ENCRYPTION_KEY:
        missing.append("encryption_key")
    if getattr(request.app.state, "message_store", None) is None:
        missing.append("message_store")
    if not settings.WHATSAPP_APP_SECRET or not settings.WHATSAPP_VERIFY_TOKEN:
        missing.append("whatsapp_ingress")
    if not settings.WHATSAPP_PHONE_NUMBER_ID or not settings.WHATSAPP_ACCESS_TOKEN:
        missing.append("whatsapp_delivery")
    if getattr(request.app.state, "agent_engine", None) is None:
        missing.append("agent_engine")
    pool = getattr(request.app.state, "database_pool", None)
    if pool is not None:
        try:
            if await pool.fetchval("SELECT 1") != 1:
                missing.append("database_ping")
        except Exception:
            missing.append("database_ping")
    revision = os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("VERCEL_GIT_COMMIT_SHA")
    return JSONResponse(
        status_code=503 if missing else 200,
        content={"status": "unready" if missing else "ready", "missing": missing,
                 "checkout_mode": settings.CHECKOUT_MODE,
                 "revision": revision[:12] if revision else None},
    )
