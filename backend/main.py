from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api.health import router as health_router
from backend.api.simulations import router as simulations_router
from backend.api.forecasting import router as forecasting_router
from backend.api.stores import router as stores_router
from backend.api.products import router as products_router
from backend.api.risks import router as risks_router
from backend.api.recommendations import router as recommendations_router
from backend.api.agent import router as agent_router
from backend.api.customers import router as customers_router

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
    application.include_router(health_router, prefix=settings.API_PREFIX)
    application.include_router(simulations_router, prefix=settings.API_PREFIX)
    application.include_router(forecasting_router)
    application.include_router(stores_router)
    application.include_router(products_router)
    application.include_router(risks_router)
    application.include_router(recommendations_router)
    application.include_router(agent_router)
    application.include_router(customers_router)
    return application

app = create_app()
