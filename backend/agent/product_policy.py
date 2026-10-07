"""Conservative WhatsApp grocery eligibility checks for medical products."""
from __future__ import annotations

import re


_MEDICAL_CATEGORY = re.compile(r"\b(?:pharmacy|medicine|medicines|medical|drug|drugs|otc|first aid)\b", re.I)
_MEDICAL_NAME = re.compile(
    r"\b(?:vicks|honitus|vaporub|paracetamol|ibuprofen|antibiotic|"
    r"cough syrup|cold relief|pain relief|painkiller|antacid)\b", re.I,
)
_SYMPTOM = re.compile(r"\b(?:headache|sore throat|fever|cough|(?:a|the) cold)\b", re.I)
_EXPLICIT_ADD = re.compile(r"\b(?:add|buy|order|put in (?:my |the )?cart|get me)\b", re.I)


def is_restricted_medical_product(name: str, category: str | None = None) -> bool:
    return bool(_MEDICAL_CATEGORY.search(category or "") or _MEDICAL_NAME.search(name))


def is_symptom_suggestion_request(text: str) -> bool:
    return bool(_SYMPTOM.search(text) and not _EXPLICIT_ADD.search(text))
