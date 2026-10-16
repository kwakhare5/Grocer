"""Conservative WhatsApp grocery eligibility checks for medical products."""
from __future__ import annotations

import re


_MEDICAL_CATEGORY = re.compile(r"\b(?:pharmacy|prescription|rx drugs?)\b", re.I)
_MEDICAL_NAME = re.compile(
    r"\b(?:dolo\s*650|paracetamol|ibuprofen|antibiotic|crocin|"
    r"cough syrup|painkiller|prescription)\b", re.I,
)
_ALLOWED_FIRST_AID = re.compile(
    r"\b(?:band[\s-]?aid|bandage|cotton|ors|electral|antiseptic|dettol liquid|savlon liquid|thermometer|gauze|sanitizer)\b",
    re.I,
)
_SYMPTOM = re.compile(r"\b(?:headache|sore throat|fever|cough|(?:a|the) cold)\b", re.I)
_EXPLICIT_ADD = re.compile(r"\b(?:add|buy|order|put in (?:my |the )?cart|get me|get|bring|send|deliver|need|want|pick up)\b", re.I)


def is_restricted_medical_product(name: str, category: str | None = None) -> bool:
    if _ALLOWED_FIRST_AID.search(name):
        return False
    return bool(_MEDICAL_CATEGORY.search(category or "") or _MEDICAL_NAME.search(name))


def is_symptom_suggestion_request(text: str) -> bool:
    return bool(_SYMPTOM.search(text) and not _EXPLICIT_ADD.search(text))
