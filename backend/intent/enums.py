"""Domain enums for GROCER Intent Contract (Spec Section 5).

Encodes explicit vocabulary for constraint types, preference classification,
substitution tolerances, ambiguity levels, and deterministic precedence.
"""
from __future__ import annotations

from enum import Enum


class ConstraintType(str, Enum):
    """Categorization for hard non-negotiable boundaries."""
    BUDGET = "budget"
    DIETARY = "dietary"
    BRAND_LOCK = "brand_lock"
    EXACT_QUANTITY = "exact_quantity"
    NO_SUBSTITUTION = "no_substitution"
    CUSTOM = "custom"


class PreferenceType(str, Enum):
    """Categorization for soft, relaxable user preferences."""
    BRAND = "brand"
    PACK_SIZE = "pack_size"
    PRODUCT_VARIANT = "product_variant"
    PRICE_SENSITIVITY = "price_sensitivity"
    MERCHANT = "merchant"


class SubstitutionTolerance(str, Enum):
    """Tolerance levels for pack size and attribute substitutions."""
    STRICT = "strict"          # Exact match only
    REASONABLE = "reasonable"  # Close pack size / variant within safe bounds
    FLEXIBLE = "flexible"      # Any reasonable equivalent


class BrandTolerance(str, Enum):
    """Tolerance levels for brand replacement."""
    SAME_BRAND = "same_brand"      # Same brand only
    USUAL_BRANDS = "usual_brands"  # Switch among user's known/trusted brands
    ANY = "any"                    # Any reliable brand


class AmbiguitySeverity(str, Enum):
    """Impact of unresolved intent ambiguity."""
    LOW = "low"        # Minor detail, default assumption is safe
    MEDIUM = "medium"  # May affect cost or item choice, confirmation helpful
    HIGH = "high"      # Critical requirement missing, blocks safe execution


class PrecedenceLevel(int, Enum):
    """Strict evaluation order for conflicting instructions (Spec Section 5.3).
    
    1. CURRENT_EXPLICIT_REQUEST: What the user explicitly typed right now.
    2. HARD_CONSTRAINTS: Absolute boundaries that cannot be relaxed silently.
    3. CURRENT_SESSION_CHOICES: Selections made earlier in this active session.
    4. STORED_SOFT_PREFERENCES: Historical preferences from customer profile.
    5. AGENT_DEFAULTS: Fallback system assumptions.
    """
    CURRENT_EXPLICIT_REQUEST = 1
    HARD_CONSTRAINTS = 2
    CURRENT_SESSION_CHOICES = 3
    STORED_SOFT_PREFERENCES = 4
    AGENT_DEFAULTS = 5
