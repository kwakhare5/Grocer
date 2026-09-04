from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db

router = APIRouter()

@router.get('/health')
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Health check endpoint. Verifies API and database connectivity."""
    try:
        await db.execute(text('SELECT 1'))
        db_status = 'connected'
    except Exception:
        db_status = 'disconnected'
    return {
        'status': 'healthy',
        'database': db_status,
        'service': 'GROCER v2',
    }
