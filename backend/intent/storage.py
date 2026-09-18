"""Session storage and snapshot history for Intent Contracts (Spec Section 5 & Section 7).

Maintains versioned snapshots of active user intents across session turns.
Allows inspecting historical revisions and guarantees that the current active
contract is deterministically retrievable.
"""
from __future__ import annotations

import threading
from typing import Optional

from backend.intent.models import IntentContract


class IntentSessionStore:
    """In-memory session store providing snapshot versioning for IntentContracts."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # session_id -> list of IntentContract ordered by version asc
        self._sessions: dict[str, list[IntentContract]] = {}
        # intent_id -> IntentContract index
        self._by_id: dict[str, IntentContract] = {}

    def save(self, contract: IntentContract) -> IntentContract:
        """Save an intent contract snapshot into session history."""
        with self._lock:
            session_id = contract.session_id
            if session_id not in self._sessions:
                self._sessions[session_id] = []

            # If a snapshot with this exact version exists, update it; otherwise record new snapshot
            existing_idx = next(
                (i for i, c in enumerate(self._sessions[session_id]) if c.version == contract.version),
                None,
            )

            if existing_idx is not None:
                self._sessions[session_id][existing_idx] = contract
            else:
                self._sessions[session_id].append(contract)

            self._by_id[contract.intent_id] = contract
            return contract


    def get_active(self, session_id: str) -> Optional[IntentContract]:
        """Get the latest (highest version) IntentContract for a session."""
        with self._lock:
            history = self._sessions.get(session_id)
            if not history:
                return None
            # Return contract with highest version
            return max(history, key=lambda c: c.version)

    def get_by_id(self, intent_id: str) -> Optional[IntentContract]:
        """Retrieve an IntentContract by its unique intent_id."""
        with self._lock:
            return self._by_id.get(intent_id)

    def get_version(self, session_id: str, version: int) -> Optional[IntentContract]:
        """Retrieve a specific version of the IntentContract for a session."""
        with self._lock:
            history = self._sessions.get(session_id)
            if not history:
                return None
            for c in history:
                if c.version == version:
                    return c
            return None

    def list_versions(self, session_id: str) -> list[IntentContract]:
        """List all version snapshots for a session in ascending order."""
        with self._lock:
            history = self._sessions.get(session_id)
            if not history:
                return []
            return sorted(history, key=lambda c: c.version)

    def clear_session(self, session_id: str) -> None:
        """Clear all intent history for a session."""
        with self._lock:
            if session_id in self._sessions:
                for c in self._sessions[session_id]:
                    self._by_id.pop(c.intent_id, None)
                del self._sessions[session_id]


# Global default store instance
default_intent_store = IntentSessionStore()
