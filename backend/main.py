from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api.health import router as health_router
from backend.api.agent import router as agent_router
from backend.api.customers import router as customers_router
from backend.api.intent_chat import router as intent_chat_router

# ---------------------------------------------------------------------------
# OPERATIONS RESIDUE — DECOUPLED FROM GROCER v2
# The following routers belong to the companion dark-store operations product.
# They are NOT part of the consumer WhatsApp replenishment boundary.
# Source: GROCER_V2_MASTER_SPEC.md §19 / Phase 0 boundary cleanup.
#   from backend.api.simulations import router as simulations_router
#   from backend.api.forecasting import router as forecasting_router
#   from backend.api.stores import router as stores_router
#   from backend.api.products import router as products_router
#   from backend.api.risks import router as risks_router
#   from backend.api.recommendations import router as recommendations_router
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    from backend.database import async_engine
    await async_engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version='2.0.0',
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    # Consumer-facing routes only
    application.include_router(health_router, prefix=settings.API_PREFIX)
    application.include_router(agent_router)
    application.include_router(customers_router)
    application.include_router(intent_chat_router)
    return application


app = create_app()

