from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central settings object — all values loaded from .env (or env vars in production).

    Every key here MUST also appear in .env and .env.example.
    Config drift (key in code but not in .env, or vice versa) is a bug — fix it immediately.

    Precedence: environment variables > .env file > defaults below.
    """
    DATABASE_URL: str
    MCP_BASE_URL: str = 'http://localhost:8001'   # Mock Swiggy MCP server
    ANTHROPIC_API_KEY: str = ''                    # Required for LangGraph agent
    TWILIO_ACCOUNT_SID: str = ''                   # Required for WhatsApp (Task 3.1+)
    TWILIO_AUTH_TOKEN: str = ''
    TWILIO_WHATSAPP_FROM: str = 'whatsapp:+14155238886'  # Twilio sandbox number
    ALERT_THRESHOLD_DAYS: int = 7                  # Items depleting within N days trigger alerts
    MIN_CONFIDENCE: float = 0.50                   # Minimum Prophet confidence to surface a prediction

    class Config:
        env_file = '.env'


settings = Settings()
