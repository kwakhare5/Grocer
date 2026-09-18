from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SHOPPING_TASK_ROUTE: bool = False
    COMMERCE_ADAPTER_TYPE: str = "mock"
    CHECKOUT_MODE: Literal["review", "live"] = "review"
    SWIGGY_MCP_BASE_URL: str = "https://mcp.swiggy.com/im"
    SWIGGY_AUTH_TOKEN: str | None = None
    SWIGGY_CUSTOMER_ID: str | None = None
    SWIGGY_CLIENT_ID: str | None = None
    SWIGGY_REDIRECT_URI: str = "https://grocerr.vercel.app/"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,https://grocerr.vercel.app"
    GEMINI_API_KEY: str | None = None
    WHATSAPP_VERIFY_TOKEN: str | None = None
    WHATSAPP_APP_SECRET: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_ACCESS_TOKEN: str | None = None
    DATABASE_URL: str | None = None
    DATABASE_POOL_MAX_SIZE: int = 5
    DATA_ENCRYPTION_KEY: str | None = None

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
