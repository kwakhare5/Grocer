from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Explicitly load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.intent.task_repository import (
    PostgresShoppingTaskRepository,
    create_postgres_pool,
)
from backend.intent.task_service import ShoppingTaskApplicationService
from backend.intent.message_understanding import MessageUnderstandingService
from backend.intent.model_understanding import GeminiMessageUnderstandingService
from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.swiggy_oauth import (
    PostgresPendingAuthFlowStore,
    default_oauth_manager,
)
from backend.integrations.commerce.token_vault import default_token_vault
from backend.api.health import router as health_router
from backend.api.whatsapp import router as whatsapp_router
from backend.api.oauth import router as oauth_router


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Attach optional durable state without hiding database startup failures."""
    pool = None
    is_live_swiggy = settings.COMMERCE_ADAPTER_TYPE.lower() == "swiggy_mcp"
    if is_live_swiggy and not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for the Swiggy commerce adapter.")
    if is_live_swiggy and not settings.DATA_ENCRYPTION_KEY:
        raise RuntimeError(
            "DATA_ENCRYPTION_KEY is required for the Swiggy commerce adapter."
        )
    if settings.DATABASE_URL:
        pool = await create_postgres_pool(
            settings.DATABASE_URL, max_size=settings.DATABASE_POOL_MAX_SIZE
        )
        app.state.shopping_task_repository = PostgresShoppingTaskRepository(pool)
        if settings.DATA_ENCRYPTION_KEY:
            await default_token_vault.configure_postgres(pool, settings.DATA_ENCRYPTION_KEY)
            default_oauth_manager.configure_flow_store(
                PostgresPendingAuthFlowStore(pool, settings.DATA_ENCRYPTION_KEY)
            )
    if settings.SHOPPING_TASK_ROUTE:
        if not pool:
            raise RuntimeError(
                "DATABASE_URL is required when SHOPPING_TASK_ROUTE is enabled."
            )
        if settings.UNDERSTANDING_MODEL_ENABLED and not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is required when model understanding is enabled."
            )
        model_understanding = (
            GeminiMessageUnderstandingService(
                settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
            )
            if settings.UNDERSTANDING_MODEL_ENABLED
            else None
        )
        app.state.shopping_task_service = ShoppingTaskApplicationService(
            app.state.shopping_task_repository,
            get_commerce_adapter(),
            checkout_mode=settings.CHECKOUT_MODE,
            understanding=MessageUnderstandingService(model_understanding),
        )
    try:
        yield
    finally:
        if pool is not None:
            await pool.close()


def create_app() -> FastAPI:
    """Build the GROCER API application without hidden database/runtime side effects."""
    app = FastAPI(
        title="GROCER",
        description="WhatsApp-first intent-preserving grocery commerce assistant",
        version="2.0.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ],
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(health_router)
    app.include_router(whatsapp_router)
    app.include_router(oauth_router, prefix="/api")

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {
            "service": "grocer",
            "version": "2.0.0",
            "status": "ok",
            "product": "intent-preserving conversational commerce",
        }

    return app


app = create_app()
