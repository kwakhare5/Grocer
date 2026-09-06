"""Intent Contract canonical domain model (Spec §5).

Encodes user shopping intent as a structured, verifiable contract that separates
hard constraints from soft preferences, enforces authorization invariants, and
tracks ambiguities and precedence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.intent.enums import (
    AmbiguitySeverity,
    BrandTolerance,
    ConstraintType,
    PreferenceType,
    SubstitutionTolerance,
)


class IntentItem(BaseModel):
    """An individual item requested within an intent."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, description="Product query or standard name")
    quantity: float = Field(default=1.0, gt=0, description="Requested numerical quantity")
    unit: str = Field(default="units", description="Measurement unit (e.g., L, kg, pcs, pack)")
    brand_preference: Optional[str] = Field(default=None, description="Preferred brand if specified")
    is_essential: bool = Field(default=True, description="True if item is required; False if optional")
    pack_size_preference: Optional[str] = Field(default=None, description="e.g. '1L', '500g'")
    category: Optional[str] = Field(default=None, description="Product category (dairy, bakery, etc.)")
    max_price: Optional[float] = Field(default=None, gt=0, description="Price cap for this item")
    notes: Optional[str] = None


class HardConstraint(BaseModel):
    """Non-negotiable rule that cannot be silently violated (Spec §5.4)."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    constraint_type: ConstraintType
    target: str = Field(..., description="Scope/target of rule, e.g. 'total_budget', 'item:milk'")
    rule: str = Field(..., description="Rule expression, e.g. '<= 2000', 'vegetarian'")
    description: str = Field(..., description="Human-readable explanation of constraint")
    is_hard: Literal[True] = True


class SoftPreference(BaseModel):
    """Influences ranking and can be relaxed with user policy or confirmation (Spec §5.4)."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    preference_type: PreferenceType
    target: str = Field(..., description="Scope/target, e.g. 'brand:milk', 'pack_size:bread'")
    preference: str = Field(..., description="Preferred attribute value, e.g. 'Amul', '1L'")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Preference strength 0.0-1.0")
    can_relax: Literal[True] = True


class BudgetConstraint(BaseModel):
    """Budget boundary for the shopping task."""
    model_config = ConfigDict(extra="ignore")

    max_budget: Optional[float] = Field(default=None, gt=0, description="Maximum total spend in currency")
    currency: str = Field(default="INR", description="Currency code")
    is_hard: bool = Field(default=True, description="Whether budget cap is a hard constraint")
    max_deviation: float = Field(
        default=0.0,
        ge=0.0,
        description="Allowed price overrun without user confirmation (default: ₹0.0)",
    )


class QuantityRules(BaseModel):
    """Rules governing quantity resolution and basket completeness."""
    model_config = ConfigDict(extra="ignore")

    strict_count: bool = Field(default=False, description="Disallow multiple smaller packs to satisfy quantity")
    allow_partial_basket: bool = Field(default=False, description="Allow completing order if some items missing")
    min_items: Optional[int] = Field(default=None, ge=1)
    max_items: Optional[int] = Field(default=None, ge=1)


class PackSizeRules(BaseModel):
    """Rules governing pack size substitutions."""
    model_config = ConfigDict(extra="ignore")

    tolerance: SubstitutionTolerance = Field(
        default=SubstitutionTolerance.REASONABLE,
        description="Pack size matching tolerance",
    )
    preferred_multiples: bool = Field(
        default=True,
        description="Allow multiple smaller packs (e.g., 2x500ml for 1L) if primary is OOS",
    )


class BrandPreference(BaseModel):
    """Brand affinity for a specific product or category."""
    model_config = ConfigDict(extra="ignore")

    product_or_category: str = Field(..., description="e.g. 'milk' or 'dairy'")
    preferred_brand: str = Field(..., description="e.g. 'Amul'")
    is_hard: bool = Field(default=False, description="True if brand cannot be substituted at all")
    alternative_brands: list[str] = Field(default_factory=list, description="Ordered acceptable substitutes")


class SubstitutionPolicy(BaseModel):
    """Policy governing automatic and human-directed substitutions (Spec §5.2)."""
    model_config = ConfigDict(extra="ignore")

    category_tolerance: str = Field(default="same_category", description="Category boundary for substitution")
    pack_size_tolerance: SubstitutionTolerance = Field(default=SubstitutionTolerance.REASONABLE)
    brand_tolerance: BrandTolerance = Field(default=BrandTolerance.USUAL_BRANDS)
    max_budget_deviation: float = Field(
        default=0.0,
        ge=0.0,
        description="Maximum budget deviation allowed during auto-substitution",
    )
    allow_substitutions: bool = Field(default=True, description="Whether any substitutions are allowed")


class DietaryConstraint(BaseModel):
    """Dietary restriction applying to the entire basket or tagged items."""
    model_config = ConfigDict(extra="ignore")

    tag: str = Field(..., description="Normalized dietary tag, e.g. 'vegetarian', 'vegan', 'halal'")
    is_hard: bool = Field(default=True, description="Dietary constraints are hard by default")
    description: Optional[str] = None


class DeliveryPreferences(BaseModel):
    """Customer preferences regarding delivery parameters."""
    model_config = ConfigDict(extra="ignore")

    max_eta_minutes: Optional[int] = Field(default=None, gt=0)
    preferred_slot: Optional[str] = None
    address_id: Optional[str] = None
    instructions: Optional[str] = None


class AuthorizationScope(BaseModel):
    """Server-enforced boundaries on autonomous agent action (Spec §6 & §8.3).
    
    Invariants:
    - checkout_requires_explicit_confirmation is structurally locked to True.
    """
    model_config = ConfigDict(extra="ignore")

    checkout_requires_explicit_confirmation: Literal[True] = Field(
        default=True,
        description="LOCKED INVARIANT: Consequential checkout always requires explicit human confirmation",
    )
    max_auto_spend_deviation: float = Field(
        default=0.0,
        ge=0.0,
        description="Max deviation spend before human clarification required",
    )
    can_auto_replace: bool = Field(
        default=True,
        description="Whether agent can auto-replace items matching substitution policy",
    )
    requires_approval_for_price_increase: bool = Field(
        default=True,
        description="Require approval if a substitution increases item price",
    )


class Ambiguity(BaseModel):
    """An unresolved aspect of the intent that may require user clarification (Spec §6)."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    field: str = Field(..., description="Path or name of ambiguous attribute")
    description: str = Field(..., description="Explanation of why this is ambiguous")
    severity: AmbiguitySeverity = Field(default=AmbiguitySeverity.MEDIUM)
    candidate_options: list[str] = Field(default_factory=list)
    suggested_clarification: Optional[str] = None


class SourceContext(BaseModel):
    """Provenance of the intent request."""
    model_config = ConfigDict(extra="ignore")

    channel: str = Field(default="whatsapp")
    raw_text: Optional[str] = None
    sender_id: Optional[str] = None
    customer_id: Optional[str] = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntentContract(BaseModel):
    """The canonical structured representation of user shopping intent (Spec §5).
    
    The cart is NOT the source of truth for intent. The IntentContract is the
    governing specification against which all commerce actions are verified.
    """
    model_config = ConfigDict(extra="ignore")

    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1, description="High-level goal, e.g. 'weekly grocery replenishment'")
    items: list[IntentItem] = Field(default_factory=list)
    hard_constraints: list[HardConstraint] = Field(default_factory=list)
    soft_preferences: list[SoftPreference] = Field(default_factory=list)
    budget: Optional[BudgetConstraint] = None
    quantity_rules: QuantityRules = Field(default_factory=QuantityRules)
    pack_size_rules: PackSizeRules = Field(default_factory=PackSizeRules)
    brand_preferences: list[BrandPreference] = Field(default_factory=list)
    substitution_policy: SubstitutionPolicy = Field(default_factory=SubstitutionPolicy)
    dietary_constraints: list[DietaryConstraint] = Field(default_factory=list)
    delivery_preferences: Optional[DeliveryPreferences] = None
    authorization_scope: AuthorizationScope = Field(default_factory=AuthorizationScope)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    source_context: Optional[SourceContext] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_contract_invariants(self) -> IntentContract:
        """Validate critical domain invariants across the contract."""
        # 1. Dietary constraints matching hard_constraints
        for diet in self.dietary_constraints:
            if diet.is_hard:
                existing = any(
                    hc.constraint_type == ConstraintType.DIETARY and hc.rule.lower() == diet.tag.lower()
                    for hc in self.hard_constraints
                )
                if not existing:
                    self.hard_constraints.append(
                        HardConstraint(
                            constraint_type=ConstraintType.DIETARY,
                            target="dietary",
                            rule=diet.tag.lower(),
                            description=f"Must be {diet.tag}",
                        )
                    )

        # 2. Budget constraint sync with hard constraints
        if self.budget and self.budget.is_hard and self.budget.max_budget is not None:
            existing_budget_hc = any(
                hc.constraint_type == ConstraintType.BUDGET for hc in self.hard_constraints
            )
            if not existing_budget_hc:
                self.hard_constraints.append(
                    HardConstraint(
                        constraint_type=ConstraintType.BUDGET,
                        target="total_budget",
                        rule=f"<= {self.budget.max_budget}",
                        description=f"Total basket spend must not exceed {self.budget.currency} {self.budget.max_budget}",
                    )
                )

        # 3. Hard brand locks sync with hard constraints
        for bp in self.brand_preferences:
            if bp.is_hard:
                existing_bp_hc = any(
                    hc.constraint_type == ConstraintType.BRAND_LOCK
                    and hc.target.lower() == f"brand:{bp.product_or_category.lower()}"
                    for hc in self.hard_constraints
                )
                if not existing_bp_hc:
                    self.hard_constraints.append(
                        HardConstraint(
                            constraint_type=ConstraintType.BRAND_LOCK,
                            target=f"brand:{bp.product_or_category.lower()}",
                            rule=bp.preferred_brand,
                            description=f"Only brand '{bp.preferred_brand}' allowed for '{bp.product_or_category}'",
                        )
                    )

        return self

    # --- Domain Query Methods ---

    def has_dietary_constraint(self, tag: str) -> bool:
        """Check whether a specific dietary constraint applies."""
        target = tag.strip().lower()
        return any(d.tag.strip().lower() == target for d in self.dietary_constraints)

    def is_hard_constraint(self, target: str) -> bool:
        """Check if target attribute is governed by a hard constraint."""
        target_lower = target.strip().lower()
        return any(hc.target.strip().lower() == target_lower for hc in self.hard_constraints)

    def get_brand_preference(self, product_or_category: str) -> Optional[BrandPreference]:
        """Get brand preference for a product or category."""
        target = product_or_category.strip().lower()
        for bp in self.brand_preferences:
            if bp.product_or_category.strip().lower() == target:
                return bp
        return None

    def has_critical_ambiguities(self) -> bool:
        """Return True if any ambiguity blocks safe deterministic execution."""
        return any(a.severity == AmbiguitySeverity.HIGH for a in self.ambiguities)

    def is_checkout_authorized(self, explicit_confirmation: bool = False) -> bool:
        """Authoritative checkout authorization check (Spec §8.3).
        
        Always requires explicit user confirmation.
        """
        if not explicit_confirmation:
            return False
        return True

    # --- Precedence Engine (Spec §5.3) ---

    def apply_memory(
        self,
        stored_preferences: list[SoftPreference | BrandPreference],
        durable_dietary: Optional[list[str]] = None,
    ) -> IntentContract:
        """Merge historical soft memory without overriding explicit request (Spec §5.3).
        
        Precedence:
        CURRENT EXPLICIT USER REQUEST > HARD CONSTRAINTS > STORED SOFT PREFERENCES > DEFAULTS.
        """
        updated = self.model_copy(deep=True)
        updated.intent_id = str(uuid.uuid4())
        updated.updated_at = datetime.now(timezone.utc)
        updated.version += 1


        # 1. Merge soft preferences if not already explicitly specified
        existing_targets = {sp.target.lower() for sp in updated.soft_preferences}
        for pref in stored_preferences:
            if isinstance(pref, SoftPreference):
                if pref.target.lower() not in existing_targets and not updated.is_hard_constraint(pref.target):
                    updated.soft_preferences.append(pref)
                    existing_targets.add(pref.target.lower())
            elif isinstance(pref, BrandPreference):
                # Only add if user didn't explicitly specify brand for this product
                existing_item_brands = {
                    item.name.lower(): item.brand_preference
                    for item in updated.items
                    if item.brand_preference
                }
                product_key = pref.product_or_category.lower()
                if product_key not in existing_item_brands and updated.get_brand_preference(product_key) is None:
                    updated.brand_preferences.append(pref)

        # 2. Add durable dietary restrictions if not conflicting
        if durable_dietary:
            for tag in durable_dietary:
                if not updated.has_dietary_constraint(tag):
                    updated.dietary_constraints.append(
                        DietaryConstraint(tag=tag, is_hard=True, description="From customer saved profile")
                    )

        # Re-run invariant validator
        return updated.validate_contract_invariants()

    def to_summary_dict(self) -> dict[str, Any]:
        """User-facing compact summary of the active contract."""
        return {
            "intent_id": self.intent_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "item_count": len(self.items),
            "items": [{"name": i.name, "quantity": i.quantity, "unit": i.unit} for i in self.items],
            "max_budget": self.budget.max_budget if self.budget else None,
            "dietary": [d.tag for d in self.dietary_constraints],
            "hard_constraints_count": len(self.hard_constraints),
            "soft_preferences_count": len(self.soft_preferences),
            "has_ambiguities": len(self.ambiguities) > 0,
            "version": self.version,
        }
