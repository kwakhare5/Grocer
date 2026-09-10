from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.health import router as health_router
from backend.api.intent_chat import router as intent_chat_router
from backend.api.whatsapp import router as whatsapp_router
from backend.api.oauth import router as oauth_router


def create_app() -> FastAPI:
    """Build the GROCER API application without hidden database/runtime side effects."""
    app = FastAPI(
        title="GROCER",
        description="WhatsApp-first intent-preserving grocery commerce assistant",
        version="2.0.0",
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
    app.include_router(intent_chat_router)
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
