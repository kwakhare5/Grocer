"""Preference Store — durable per-customer memory (Spec §7).

Stores normalized preference information (brands, pack sizes, substitution
history, recurring patterns) to reduce repetitive conversation. Preferences
never override an explicit current request — precedence is enforced by
IntentContract.apply_memory() (Phase 1).

Rules (Spec §7.2):
    Do not store as permanent preference:
    - old prices
    - stale availability
    - one-off substitutions without evidence
    - inferred preferences without meaningful evidence
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.intent.enums import PreferenceType
from backend.intent.models import BrandPreference, SoftPreference


# ---------------------------------------------------------------------------
# Stored preference model
# ---------------------------------------------------------------------------

class StoredPreference(BaseModel):
    """A single durable customer preference with evidence tracking."""
    model_config = ConfigDict(extra="ignore")

    customer_id: str
    preference_type: PreferenceType
    product_or_category: str = Field(..., description="Product or category key")
    value: str = Field(..., description="The preference value (brand name, pack size, etc.)")
    evidence_count: int = Field(default=1, description="How many times this preference was observed")
    last_used_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_durable: bool = Field(default=True, description="False for one-off observations")

    @property
    def is_established(self) -> bool:
        """A preference is established when observed at least twice."""
        return self.evidence_count >= 2 and self.is_durable


# Categories that should NOT be stored as permanent preferences (Spec §7.2)
_NON_STORABLE_TYPES: set[str] = {
    "price",           # old prices
    "availability",    # stale availability
    "one_off",         # one-off substitutions without evidence
}


# ---------------------------------------------------------------------------
# PreferenceStore
# ---------------------------------------------------------------------------

class PreferenceStore:
    """Per-customer durable preference memory (Spec §7).

    Thread-safe in-memory store. In production this would be backed by a
    database, but the interface remains the same.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # customer_id → { "type:product" → StoredPreference }
        self._store: dict[str, dict[str, StoredPreference]] = {}

    def _make_key(self, pref: StoredPreference) -> str:
        return f"{pref.preference_type.value}:{pref.product_or_category.lower()}"

    def record_preference(self, preference: StoredPreference) -> StoredPreference:
        """Record or update a customer preference.

        If the preference already exists, increments evidence_count and updates
        last_used_at. Rejects non-storable types (Spec §7.2).

        Returns the stored preference (may have updated evidence_count).
        """
        if self.should_not_store(preference):
            return preference

        key = self._make_key(preference)

        with self._lock:
            customer_prefs = self._store.setdefault(preference.customer_id, {})
            existing = customer_prefs.get(key)
            if existing:
                existing.evidence_count += 1
                existing.last_used_at = datetime.now(timezone.utc)
                existing.value = preference.value
                return existing
            else:
                customer_prefs[key] = preference
                return preference

    def get_preferences(self, customer_id: str) -> list[StoredPreference]:
        """Get all durable preferences for a customer."""
        with self._lock:
            customer_prefs = self._store.get(customer_id, {})
            return [p for p in customer_prefs.values() if p.is_durable]

    def get_brand_preferences(self, customer_id: str) -> list[BrandPreference]:
        """Convert stored brand preferences to domain BrandPreference models.

        Only returns established preferences (evidence_count >= 2).
        These can be fed into IntentContract.apply_memory().
        """
        prefs = self.get_preferences(customer_id)
        result: list[BrandPreference] = []
        for p in prefs:
            if p.preference_type == PreferenceType.BRAND and p.is_established:
                result.append(BrandPreference(
                    product_or_category=p.product_or_category,
                    preferred_brand=p.value,
                    is_hard=False,  # Stored preferences are always soft
                ))
        return result

    def get_soft_preferences(self, customer_id: str) -> list[SoftPreference]:
        """Convert stored non-brand preferences to domain SoftPreference models.

        Only returns established preferences (evidence_count >= 2).
        """
        prefs = self.get_preferences(customer_id)
        result: list[SoftPreference] = []
        for p in prefs:
            if p.preference_type != PreferenceType.BRAND and p.is_established:
                result.append(SoftPreference(
                    preference_type=p.preference_type,
                    target=f"{p.preference_type.value}:{p.product_or_category}",
                    preference=p.value,
                    weight=min(0.5 + (p.evidence_count * 0.1), 1.0),
                ))
        return result

    def clear_stale(self, customer_id: str, max_age_days: int = 90) -> int:
        """Remove preferences older than the threshold (Spec §7.2).

        Returns the number of preferences removed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        removed = 0

        with self._lock:
            customer_prefs = self._store.get(customer_id, {})
            stale_keys = [
                key for key, pref in customer_prefs.items()
                if pref.last_used_at < cutoff
            ]
            for key in stale_keys:
                del customer_prefs[key]
                removed += 1

        return removed

    @staticmethod
    def should_not_store(preference: StoredPreference) -> bool:
        """Check if a preference should be rejected per Spec §7.2.

        Rejects:
            - price-type preferences (old prices)
            - availability-type preferences (stale availability)
            - one-off observations (is_durable=False)
        """
        if not preference.is_durable:
            return True
        if preference.preference_type.value in _NON_STORABLE_TYPES:
            return True
        return False

    def clear(self, customer_id: str) -> None:
        """Remove all preferences for a customer."""
        with self._lock:
            self._store.pop(customer_id, None)


# Module-level default instance
default_preference_store = PreferenceStore()
