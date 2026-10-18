"""Deterministic safety guards, phrase matchers, and receipt post-processing for GROCER."""
from __future__ import annotations

import re

_NEGATION_CONFIRM_REGEX = re.compile(
    r"(?i)\b(don'?t|do not|never|stop|wait|hold|cancel|not now|not yet|no|nope|nah|pause|clear cart|start over)\b"
)
