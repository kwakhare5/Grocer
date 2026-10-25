"""Grocer v1.0 — Strict Configuration & Safety Caps.

Loads environment variables from .env and enforces hard validation invariants.
Secrets live strictly in environment variables; zero hardcoding.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    APP_NAME: str = "Grocer"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Meta WhatsApp Cloud API
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        ..., description="WhatsApp Business Phone Number ID"
    )
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = Field(..., description="Meta WABA ID")
    WHATSAPP_ACCESS_TOKEN: str = Field(..., description="Meta System User Access Token")
    WHATSAPP_APP_SECRET: str = Field(
        ..., description="Meta App Secret for HMAC-SHA256 signature verification"
    )
    WHATSAPP_VERIFY_TOKEN: str = Field(
        ..., description="Meta Webhook Verification Token"
    )

    # Google Gemini AI
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.5-flash-lite"

    # Database (Supabase PostgreSQL with SSL)
    DATABASE_URL: str = Field(
        ..., description="PostgreSQL connection string with sslmode=require"
    )
    DATABASE_POOL_MIN_SIZE: int = 1
    DATABASE_POOL_MAX_SIZE: int = 5

    # Security & Encryption (AES-256-GCM Token Vault)
    DATA_ENCRYPTION_KEY: str = Field(
        ..., description="32-byte Base64 key for AES-256-GCM token encryption"
    )

    # Swiggy MCP & OAuth
    COMMERCE_ADAPTER_TYPE: str = "swiggy_mcp"
    SWIGGY_REDIRECT_URI: str = "https://grocerr.vercel.app/"
    SWIGGY_MCP_BASE_URL: str = "https://mcp.swiggy.com"

    # Safety Caps (Integer Paise strictly: ₹1 = 100 paise)
    DEFAULT_BUDGET_CAP_PAISE: int = 100000  # ₹1,000 launch safety cap
    PRICE_DRIFT_THRESHOLD_PAISE: int = 100  # ₹1 price drift abort latch
    APPROVAL_EXPIRY_SECONDS: int = 600  # 10-minute approval TTL
    DPDP_RETENTION_HOURS: int = 24  # 24h data minimization

    # Deployment
    INTENT_BACKEND_URL: str = "https://grocer-backend-qwk4.onrender.com"
    CORS_ALLOWED_ORIGINS: str = "https://grocerr.vercel.app"
    RENDER_API_KEY: str | None = None


# Authoritative settings singleton
settings = Settings()
