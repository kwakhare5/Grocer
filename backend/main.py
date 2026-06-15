import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from backend.api.routes import household, predictions, restock, recipes, prices
from backend.notifications import whatsapp
from backend.database.connection import init_db
from backend.notifications.scheduler import start_scheduler, stop_scheduler
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI lifespan handler — replaces deprecated @app.on_event.

    Startup sequence:
      1. init_db   — ensure all tables exist (idempotent via create_all)
      2. get_checkpointer — ensure checkpoints table exists
      3. start_scheduler — register APScheduler cron jobs and start the loop

    Shutdown sequence:
      1. stop_scheduler — graceful shutdown (no in-flight jobs interrupted)
    """
    await init_db()
    # Auto-initialize checkpoints tables
    try:
        from backend.database.connection import get_checkpointer
        async with await get_checkpointer() as cp:
            await cp.setup()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not connect DB to run checkpointer setup (DB likely offline): {e}")

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Instamart Intelligence API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(household.router)
app.include_router(predictions.router)
app.include_router(restock.router)
app.include_router(recipes.router)
app.include_router(prices.router)
app.include_router(whatsapp.router)



@app.get("/health")
async def health():
    """Health check — also reports scheduler job count."""
    from backend.notifications.scheduler import scheduler
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    return {"status": "ok", "version": "1.0.0", "scheduled_jobs": jobs}


@app.get("/")
async def root():
    return {"message": "Welcome to Instamart Intelligence API"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
