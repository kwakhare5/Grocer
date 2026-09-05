from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://grocer:grocer@localhost:5432/grocer"
    APP_NAME: str = "GROCER v2"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    COMMERCE_ADAPTER_TYPE: str = "mock"
    SWIGGY_MCP_BASE_URL: str = "https://mcp.swiggy.com/im"
    SWIGGY_AUTH_TOKEN: str | None = None

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
