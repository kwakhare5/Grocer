"""Orchestrator session state — conversational shopping loop state machine (Spec §13).

Tracks the full lifecycle of a user's conversational grocery task:
    READY → BUILDING → AWAITING_CONFIRMATION → ORDERED (or FAILED / NEEDS_DECISION)

ConversationState is the authoritative routing signal used by GrocerOrchestrator.
OrchestratorSession is the per-session data bag persisted across turns.
OrchestratorSessionStore is the thread-safe in-memory store keyed by session_id.

LLM DOES NOT control state transitions — all routing is deterministic (Spec §12.3).
"""
from __future__ import annotations

import threading
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.intent.models import IntentContract
from backend.intent.verifier import VerificationResult
from backend.intent.recovery import RecoveryOutcome, RecoveryCandidate


# ---------------------------------------------------------------------------
# Conversation state enum  (Spec §13.1 + §11)
# ---------------------------------------------------------------------------

class ConversationState(str, Enum):
    """Session lifecycle state for the WhatsApp commerce loop.

    Used by the frontend to render compact UI state labels (Spec §11):
        READY               — idle, no active intent
        BUILDING            — parsing + building cart
        RECOVERING          — recovery engine active
        NEEDS_DECISION      — user must choose between candidates
        AWAITING_CONFIRMATION — basket ready, waiting for explicit confirm
        ORDERED             — checkout succeeded (terminal)
        FAILED              — unrecoverable failure (terminal)
    """

    READY = "READY"
    BUILDING = "BUILDING"
    RECOVERING = "RECOVERING"
    NEEDS_DECISION = "NEEDS_DECISION"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ORDERED = "ORDERED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

class ClarificationOption(BaseModel):
    """A candidate the user must choose between during NEEDS_DECISION state."""

    model_config = ConfigDict(extra="ignore")

    index: int = Field(..., description="1-based choice index for user reply")
    spin_id: str
    name: str
    pack_size: str
    price: float
    brand: Optional[str] = None
    score: float = Field(default=0.0, description="Internal ranking score")


class BasketItem(BaseModel):
    """Summary of one item in the resolved basket."""

    model_config = ConfigDict(extra="ignore")

    spin_id: str
    name: str
    pack_size: str
    quantity: int
    unit_price: float
    line_total: float
    brand: Optional[str] = None
    substituted: bool = Field(default=False, description="True if auto-substituted during recovery")


class BasketSummary(BaseModel):
    """Summary of the verified cart presented to the user before checkout."""

    model_config = ConfigDict(extra="ignore")

    cart_id: str
    items: list[BasketItem] = Field(default_factory=list)
    item_total: float
    delivery_fee: float
    grand_total: float
    budget: Optional[float] = None
    within_budget: bool = Field(default=True)
    recovery_notes: list[str] = Field(default_factory=list)


class PendingClarification(BaseModel):
    """Stored state for an open NEEDS_DECISION turn."""

    model_config = ConfigDict(extra="ignore")

    item_name: str = Field(..., description="Name of the item requiring user decision")
    candidates: list[RecoveryCandidate] = Field(default_factory=list)
    clarification_question: str


# ---------------------------------------------------------------------------
# Session model  (Spec §13.1)
# ---------------------------------------------------------------------------

class OrchestratorSession(BaseModel):
    """Full per-session conversational commerce state.

    Created on first turn for a session_id, persisted across turns.
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    session_id: str
    customer_id: str
    conversation_state: ConversationState = ConversationState.READY
    cart_id: Optional[str] = None
    address_id: Optional[str] = None

    # Intent
    intent_contract: Optional[IntentContract] = None

    # Pending states
    pending_clarification: Optional[PendingClarification] = None

    # Last verification/recovery for audit
    last_verification: Optional[dict[str, Any]] = None
    last_recovery_state: Optional[str] = None

    # Turn counter — monotonically increasing
    turn_count: int = 0

    # Audit trail — list of event strings for the current session
    events: list[str] = Field(default_factory=list)

    # Settled order (terminal)
    order_id: Optional[str] = None
    order_total: Optional[float] = None


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

class OrchestratorSessionStore:
    """Thread-safe in-memory store for OrchestratorSession objects.

    Keyed by session_id (str). Compatible with per-request async usage
    since all critical mutations use a threading.RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, OrchestratorSession] = {}

    def get_or_create(self, session_id: str, customer_id: str) -> OrchestratorSession:
        """Return existing session or create a fresh READY session."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = OrchestratorSession(
                    session_id=session_id,
                    customer_id=customer_id,
                )
            return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[OrchestratorSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, session: OrchestratorSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def all_sessions(self) -> list[OrchestratorSession]:
        with self._lock:
            return list(self._sessions.values())


# Module-level singleton used by orchestrator and API layer
default_session_store = OrchestratorSessionStore()
