"""Post-extraction validation and invariant enforcement for IntentContract (Spec Section 12.2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.intent.enums import (
    AmbiguitySeverity,
    BrandTolerance,
    PreferenceType,
    SubstitutionTolerance,
)
from backend.intent.models import (
    Ambiguity,
    AuthorizationScope,
    BrandPreference,
    BudgetConstraint,
    DietaryConstraint,
    IntentContract,
    IntentItem,
    SoftPreference,
    SourceContext,
    SubstitutionPolicy,
)


class DeterministicValidator:
    """Post-extraction validation and invariant enforcement (Spec Section 12.2)."""

    def validate(self, raw: dict, text: str, session_id: str, customer_id: Optional[str]) -> IntentContract:
        """Build and validate an IntentContract from raw extraction output."""
        now = datetime.now(timezone.utc)

        # Build model instances from raw dicts
        items = [IntentItem(**item) for item in raw.get("items", [])]

        budget = None
        if raw.get("budget"):
            budget = BudgetConstraint(**raw["budget"])

        dietary = [DietaryConstraint(**dc) for dc in raw.get("dietary_constraints", [])]

        brand_prefs = []
        for bp in raw.get("brand_preferences", []):
            brand_prefs.append(BrandPreference(**bp))

        sub_policy_raw = raw.get("substitution_policy")
        sub_policy = SubstitutionPolicy()
        if sub_policy_raw:
            sub_policy = SubstitutionPolicy(
                allow_substitutions=sub_policy_raw.get("allow_substitutions", True),
                brand_tolerance=BrandTolerance(sub_policy_raw.get("brand_tolerance", "usual_brands")),
                pack_size_tolerance=SubstitutionTolerance(sub_policy_raw.get("pack_size_tolerance", "reasonable")),
            )

        soft_prefs = []
        for sp in raw.get("soft_preferences", []):
            soft_prefs.append(SoftPreference(
                preference_type=PreferenceType(sp["preference_type"]),
                target=sp["target"],
                preference=sp["preference"],
                weight=sp.get("weight", 1.0),
            ))

        ambiguities = []
        for amb in raw.get("ambiguities", []):
            ambiguities.append(Ambiguity(
                field=amb["field"],
                description=amb["description"],
                severity=AmbiguitySeverity(amb["severity"]),
                candidate_options=amb.get("candidate_options", []),
                suggested_clarification=amb.get("suggested_clarification"),
            ))

        # Compute confidence: start at 1.0, deduct for ambiguities
        confidence = 1.0
        for amb in ambiguities:
            if amb.severity == AmbiguitySeverity.HIGH:
                confidence -= 0.3
            elif amb.severity == AmbiguitySeverity.MEDIUM:
                confidence -= 0.15
            elif amb.severity == AmbiguitySeverity.LOW:
                confidence -= 0.05
        confidence = max(0.0, min(1.0, confidence))

        is_greeting = bool(raw.get("is_greeting", False))

        # Flag missing critical info
        if not items and not raw.get("goal", "").strip() and not is_greeting:
            ambiguities.append(Ambiguity(
                field="goal",
                description="No specific items or clear goal could be extracted from the request",
                severity=AmbiguitySeverity.HIGH,
                suggested_clarification="Could you tell me what groceries you need?",
            ))
            confidence = max(0.0, confidence - 0.3)

        source_context = SourceContext(
            channel="whatsapp",
            raw_text=text,
            customer_id=customer_id,
            received_at=now,
        )

        # Build contract — Pydantic model_validator handles invariant sync
        contract = IntentContract(
            intent_id=str(uuid.uuid4()),
            session_id=session_id,
            goal=raw.get("goal", "greeting" if is_greeting else "grocery request"),
            is_greeting=is_greeting,
            items=items,
            budget=budget,
            dietary_constraints=dietary,
            brand_preferences=brand_prefs,
            substitution_policy=sub_policy,
            soft_preferences=soft_prefs,
            ambiguities=ambiguities,
            confidence=confidence,
            source_context=source_context,
            authorization_scope=AuthorizationScope(),
            created_at=now,
            updated_at=now,
            version=1,
        )

        return contract
