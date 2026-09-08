from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    COMMERCE_ADAPTER_TYPE: str = "mock"
    SWIGGY_MCP_BASE_URL: str = "https://mcp.swiggy.com/im"
    SWIGGY_AUTH_TOKEN: str | None = None
    SWIGGY_CUSTOMER_ID: str | None = None
    SWIGGY_CLIENT_ID: str | None = None
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
