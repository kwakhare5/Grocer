"""Stage 2: Address Stage.

Handles preliminary background address selection for catalog querying,
single-address auto-selection, multi-address interactive prompts, and durable storage.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from backend.integrations.commerce.models import DeliveryAddress
from backend.intent.stages.confirm_stage import _display_address

_ADDRESS_STORAGE_FILE = Path(os.environ.get("GROCER_ADDRESS_CACHE", "/tmp/grocer_customer_addresses.json"))


class AddressStageManager:
    """Manages address discovery, selection, and durability."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            if _ADDRESS_STORAGE_FILE.exists():
                with open(_ADDRESS_STORAGE_FILE, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            _ADDRESS_STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_ADDRESS_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)
        except Exception:
            pass

    def get_saved_address(self, customer_id: str) -> Optional[str]:
        return self._cache.get(customer_id)

    def save_address(self, customer_id: str, address_id: str) -> None:
        self._cache[customer_id] = address_id
        self._save_cache()

    @staticmethod
    def pick_preliminary_address(addresses: list[DeliveryAddress]) -> Optional[DeliveryAddress]:
        """Pick a sensible background address to query store catalog availability.

        Prefers 'Home' address category; falls back to the first saved address.
        """
        if not addresses:
            return None
        return next(
            (a for a in addresses if (a.label or "").casefold() == "home"),
            addresses[0],
        )

    @staticmethod
    def format_address_prompt(addresses: list[DeliveryAddress]) -> str:
        """Render a readable address selection prompt."""
        options_text = "\n".join(
            f"{index}. {candidate.label}: "
            f"{candidate.street or candidate.city or 'Saved Address'}"
            for index, candidate in enumerate(addresses, 1)
        )
        return (
            "Which address would you like to use for delivery?\n"
            f"{options_text}\n"
            "Reply with the number or label of your choice."
        )


default_address_manager = AddressStageManager()
