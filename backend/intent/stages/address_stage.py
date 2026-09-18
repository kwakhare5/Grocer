"""Stage 2: Address Stage.

Handles preliminary background address selection for catalog querying,
single-address auto-selection, multi-address interactive prompts, and durable storage.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional

from backend.integrations.commerce.models import DeliveryAddress
from backend.intent.formatters import format_address_prompt as _format_address_prompt
from backend.intent.stages.confirm_stage import _display_address

def _get_address_storage_file() -> Path:
    return Path(os.environ.get("GROCER_ADDRESS_CACHE", "/tmp/grocer_customer_addresses.json"))


class AddressStageManager:
    """Manages address discovery, selection, and durability."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            storage_file = _get_address_storage_file()
            if storage_file.exists():
                with open(storage_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        """Persist address cache atomically in a background thread to prevent event loop blocking."""
        cache_snapshot = dict(self._cache)

        def _write() -> None:
            try:
                storage_file = _get_address_storage_file()
                storage_file.parent.mkdir(parents=True, exist_ok=True)
                tmp_file = storage_file.with_suffix(".tmp")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(cache_snapshot, f)
                tmp_file.replace(storage_file)
            except Exception:
                pass

        threading.Thread(target=_write, daemon=True).start()

    def reset(self) -> None:
        """Clear cache in memory and on disk."""
        self._cache.clear()
        try:
            storage_file = _get_address_storage_file()
            if storage_file.exists():
                storage_file.unlink(missing_ok=True)
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
    def resolve_session_address(
        customer_id: str,
        explicit_address_id: Optional[str],
        session_address_id: Optional[str],
        swiggy_addresses: list[DeliveryAddress],
    ) -> tuple[str, Optional[str], bool]:
        """Resolve effective address_id, address_display, and address_confirmed flag.

        Returns:
            (effective_address_id, address_display, address_confirmed)
        """
        if explicit_address_id:
            display = None
            if swiggy_addresses:
                match = next((a for a in swiggy_addresses if a.id == explicit_address_id), None)
                if match:
                    display = _display_address(match)
            return explicit_address_id, display, True

        target_id = session_address_id or default_address_manager.get_saved_address(customer_id)
        if target_id and swiggy_addresses:
            match = next((a for a in swiggy_addresses if a.id == target_id), None)
            if match:
                return target_id, _display_address(match), False

        prelim = AddressStageManager.pick_preliminary_address(swiggy_addresses)
        if prelim:
            return prelim.id, _display_address(prelim), False

        fallback_id = target_id or (swiggy_addresses[0].id if swiggy_addresses else f"addr-{customer_id}")
        return fallback_id, None, False

    @staticmethod
    def format_address_prompt(
        addresses: list[DeliveryAddress],
        basket_prefix: Optional[str] = None,
    ) -> str:
        """Render a clean, well-spaced address selection prompt for WhatsApp."""
        return _format_address_prompt(addresses, basket_summary=basket_prefix)

    @staticmethod
    def match_address_choice(
        choice: str,
        addresses: list[DeliveryAddress],
    ) -> Optional[DeliveryAddress]:
        """Match user input against available delivery addresses.

        Supports 1-based index ('1', '2'), exact ID/label, and partial label/street matches.
        """
        cleaned = choice.strip().lower()
        if cleaned.isdigit():
            idx = int(cleaned) - 1
            if 0 <= idx < len(addresses):
                return addresses[idx]
        for addr in addresses:
            if addr.id.lower() == cleaned or (addr.label and addr.label.lower() == cleaned):
                return addr
        for addr in addresses:
            if cleaned in (addr.label or "").lower() or cleaned in (addr.street or "").lower():
                return addr
        return None


default_address_manager = AddressStageManager()
