from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    AGENT_ROUTE_ENABLED: bool = True
    COMMERCE_ADAPTER_TYPE: str = "mock"
    CHECKOUT_MODE: Literal["review", "live"] = "review"
    LIVE_CHECKOUT_ENABLED: bool = False
    SIMULATOR_ENABLED: bool = False
    SIMULATOR_ACCESS_TOKEN: str | None = None
    SIMULATOR_SENDER_ID: str | None = None
    SWIGGY_MCP_BASE_URL: str = "https://mcp.swiggy.com/im"
    SWIGGY_AUTH_TOKEN: str | None = None
    SWIGGY_CUSTOMER_ID: str | None = None
    SWIGGY_CLIENT_ID: str | None = None
    SWIGGY_REDIRECT_URI: str = "https://grocerr.vercel.app/"
    CONNECT_BASE_URL: str = "https://grocerr.vercel.app"
    CORS_ALLOWED_ORIGINS: str = "https://grocerr.vercel.app"
    AI_PROVIDER: Literal["gemini"] = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.5-flash-lite"
    WHATSAPP_VERIFY_TOKEN: str | None = None
    WHATSAPP_APP_SECRET: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_PUBLIC_NUMBER: str | None = None
    WHATSAPP_ACCESS_TOKEN: str | None = None
    DATABASE_URL: str | None = None
    DATABASE_POOL_MAX_SIZE: int = 10
    DATA_ENCRYPTION_KEY: str | None = None

    @field_validator("GEMINI_MODEL", "GEMINI_FALLBACK_MODEL", mode="before")
    @classmethod
    def sanitize_model(cls, v: str | None) -> str:
        if not v:
            return "gemini-3.5-flash-lite"
        return v

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
