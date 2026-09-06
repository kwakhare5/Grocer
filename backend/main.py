from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.health import router as health_router
from backend.api.intent_chat import router as intent_chat_router


def create_app() -> FastAPI:
    """Build the GROCER API application without hidden database/runtime side effects."""
    app = FastAPI(
        title="GROCER",
        description="WhatsApp-first intent-preserving grocery commerce assistant",
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(intent_chat_router)

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
