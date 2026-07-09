from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object — all values loaded from .env (or env vars in production).

    Every key here MUST also appear in .env and .env.example.
    Config drift (key in code but not in .env, or vice versa) is a bug — fix it immediately.

    Precedence: environment variables > .env file > defaults below.
    """
    DATABASE_URL: str
    MCP_BASE_URL: str = 'http://localhost:8001'   # Mock MCP server
    TWILIO_ACCOUNT_SID: str = ''                   # Required for WhatsApp (Task 3.1+)
    TWILIO_AUTH_TOKEN: str = ''
    TWILIO_WHATSAPP_FROM: str = 'whatsapp:+14155238886'  # Twilio sandbox number
    ALERT_THRESHOLD_DAYS: int = 7                  # Items depleting within N days trigger alerts
    MIN_CONFIDENCE: float = 0.50                   # Minimum Prophet confidence to surface a prediction
    GROQ_API_KEY: str = ''                         # Free tier Groq API key
    NVIDIA_API_KEY: str = ''                       # Free tier NVIDIA NIM API key

    # NEW settings
    ENVIRONMENT: str = 'development'          # 'development' | 'staging' | 'production'
    CORS_ALLOWED_ORIGINS: str = 'http://localhost:3000'  # comma-separated
    REDIS_URL: str = ''                        # optional — enables caching + webhook idempotency

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(',') if o.strip()]

    def is_twilio_configured(self) -> bool:
        token = self.TWILIO_AUTH_TOKEN
        return bool(token and token.strip() and "your_token" not in token)


settings = Settings()  # type: ignore
