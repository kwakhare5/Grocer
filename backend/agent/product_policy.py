"""Conservative WhatsApp grocery eligibility checks for medical products."""
from __future__ import annotations

import re


_MEDICAL_CATEGORY = re.compile(r"\b(?:pharmacy|prescription|rx drugs?)\b", re.I)
_MEDICAL_NAME = re.compile(
    r"\b(?:dolo\s*650|paracetamol|ibuprofen|antibiotic|crocin|"
    r"cough syrup|painkiller|prescription)\b", re.I,
)
_ALLOWED_FIRST_AID = re.compile(
    r"\b(?:band[\s-]?aid|bandage|cotton|ors|electral|antiseptic|dettol liquid|savlon liquid|thermometer|gauze|sanitizer|"
    r"eno|pudina hara|digene|moov|iodex|balm|amrutanjan|volini|soframycin)\b",
    re.I,
)
_NEGATED_SYMPTOM = re.compile(
    r"\b(?:not|don't|dont|do\s+not|no|never)\s+(?:have\s+|feel\s+)?(?:a\s+|the\s+)?(?:cold|cough|headache|fever|flu|bukhar|sirdard|khansi)\b",
    re.I,
)
_SYMPTOM = re.compile(
    r"\b(?:headache|sore throat|fever|cough|(?:a|the) cold|bukhar|sirdard|khansi|gala kharab|pet dard|nausea|indigestion)\b",
    re.I,
)
_EXPLICIT_ADD = re.compile(
    r"\b(?:add|buy|order|put in (?:my |the )?cart|get me|bring|send|deliver|pick up)\b",
    re.I,
)


def is_restricted_medical_product(name: str, category: str | None = None) -> bool:
    if _ALLOWED_FIRST_AID.search(name):
        return False
    return bool(_MEDICAL_CATEGORY.search(category or "") or _MEDICAL_NAME.search(name))


def is_symptom_suggestion_request(text: str) -> bool:
    if not text or _NEGATED_SYMPTOM.search(text):
        return False
    return bool(_SYMPTOM.search(text) and not _EXPLICIT_ADD.search(text))
