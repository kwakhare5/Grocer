from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Report API health without depending on the retired operations database."""
    return {
        "status": "healthy",
        "service": "GROCER v2",
        "database": "not_required",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
