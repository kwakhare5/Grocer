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

    # Google Gemini AI (optional; Groq is primary)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.5-flash-lite"

    # LLM Adapter (ADR 0012). The provider never calls Swiggy.
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    LLM_TIMEOUT_SECONDS: float = 8.0  # One interactive turn budget; no 60s dead air
    ROUTER_CONFIDENCE_FLOOR: float = 0.70

    # Database (Supabase PostgreSQL with SSL)
    DATABASE_URL: str = Field(
        ..., description="PostgreSQL connection string with sslmode=require"
    )
    # Same Supabase project until launch. Must point at the grocer_test database.
    TEST_DATABASE_URL: str | None = None
    DATABASE_POOL_MIN_SIZE: int = 1
    DATABASE_POOL_MAX_SIZE: int = 5

    # Security & Encryption (AES-256-GCM Token Vault)
    DATA_ENCRYPTION_KEY: str = Field(
        ..., description="32-byte Base64 key for AES-256-GCM token encryption"
    )

    # Swiggy MCP & OAuth
    SWIGGY_REDIRECT_URI: str = "https://grocerr.vercel.app/"
    SWIGGY_MCP_BASE_URL: str = "https://mcp.swiggy.com"

    # Safety Caps (Integer Paise strictly: ₹1 = 100 paise)
    LIVE_CHECKOUT_ENABLED: bool = False  # Deploy lock: no real order unless explicitly enabled
    DEFAULT_BUDGET_CAP_PAISE: int = 100000  # ₹1,000 launch safety cap

    # Deployment
    CORS_ALLOWED_ORIGINS: str = "https://grocerr.vercel.app"


# Authoritative settings singleton
settings = Settings()
