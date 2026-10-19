"""Agent model configuration constants re-exported from settings."""
from __future__ import annotations

from backend.config import settings

BRAIN_MODEL: str = settings.GEMINI_MODEL
SMALL_CHECK_MODEL: str = settings.GEMINI_SMALL_CHECK_MODEL
BRAIN_FALLBACK_MODEL: str = settings.GEMINI_FALLBACK_MODEL
