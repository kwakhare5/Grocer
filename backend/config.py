from typing import Literal

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
    AI_PROVIDER: Literal["gemini", "groq", "openrouter"] = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.5-flash-lite"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    WHATSAPP_VERIFY_TOKEN: str | None = None
    WHATSAPP_APP_SECRET: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_PUBLIC_NUMBER: str | None = None
    WHATSAPP_ACCESS_TOKEN: str | None = None
    DATABASE_URL: str | None = None
    DATABASE_POOL_MAX_SIZE: int = 5
    DATA_ENCRYPTION_KEY: str | None = None

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
