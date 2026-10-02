from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """Report API availability and system diagnostics."""
    engine = getattr(request.app.state, "agent_engine", None)
    groq_key = settings.GROQ_API_KEY
    openrouter_key = settings.OPENROUTER_API_KEY
    return {
        "status": "healthy",
        "service": "GROCER",
        "database": "not_checked",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diagnostics": {
            "ai_provider": settings.AI_PROVIDER,
            "groq_configured": bool(groq_key),
            "groq_model": settings.GROQ_MODEL,
            "openrouter_configured": bool(openrouter_key),
            "openrouter_model": settings.OPENROUTER_MODEL,
            "commerce_adapter": settings.COMMERCE_ADAPTER_TYPE,
            "last_llm_error": getattr(engine, "last_llm_error", None) if engine else None,
            "last_turn_latency_ms": getattr(engine, "last_turn_latency_ms", None) if engine else None,
        },
    }
