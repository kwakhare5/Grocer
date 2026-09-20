from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """Report API availability and system diagnostics."""
    engine = getattr(request.app.state, "agent_engine", None)
    gemini_key = settings.GEMINI_API_KEY
    return {
        "status": "healthy",
        "service": "GROCER",
        "database": "not_checked",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diagnostics": {
            "gemini_configured": bool(gemini_key),
            "gemini_prefix": f"{gemini_key[:8]}..." if gemini_key else None,
            "gemini_model": settings.GEMINI_MODEL,
            "commerce_adapter": settings.COMMERCE_ADAPTER_TYPE,
            "last_gemini_error": getattr(engine, "last_gemini_error", None) if engine else None,
            "last_turn_latency_ms": getattr(engine, "last_turn_latency_ms", None) if engine else None,
        },
    }
