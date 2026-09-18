from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Report API availability; it does not prove provider or database readiness."""
    return {
        "status": "healthy",
        "service": "GROCER",
        "database": "not_checked",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
