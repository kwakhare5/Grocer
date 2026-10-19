"""Agent model configuration constants."""
from __future__ import annotations

import os

BRAIN_MODEL: str = os.getenv("GROCER_BRAIN_MODEL", "gemini-3.5-flash")
SMALL_CHECK_MODEL: str = os.getenv("GROCER_SMALL_CHECK_MODEL", "gemini-3.5-flash-lite")
BRAIN_FALLBACK_MODEL: str = os.getenv("GROCER_BRAIN_FALLBACK_MODEL", "gemini-3-flash-preview")
