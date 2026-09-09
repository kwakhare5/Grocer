"""Orchestrator session state — conversational shopping loop state machine (Spec §13).

Tracks the full lifecycle of a user's conversational grocery task:
    READY → BUILDING → AWAITING_CONFIRMATION → ORDERED (or FAILED / NEEDS_DECISION)

ConversationState is the authoritative routing signal used by GrocerOrchestrator.
OrchestratorSession is the per-session data bag persisted across turns.
OrchestratorSessionStore is the thread-safe in-memory store keyed by session_id.

LLM DOES NOT control state transitions — all routing is deterministic (Spec §12.3).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.intent.models import IntentContract
from backend.intent.verifier import VerificationResult
from backend.intent.recovery import RecoveryOutcome, RecoveryCandidate
from backend.intent.semantics import normalize_pack_quantity
from backend.integrations.commerce.models import CommerceCart, DeliveryAddress, PaymentOption


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
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PARTIAL_ORDER = "PARTIAL_ORDER"
    ORDER_STATE_UNKNOWN = "ORDER_STATE_UNKNOWN"
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
    packaging_fee: float = 0.0
    discount: float = 0.0
    grand_total: float
    address_id: Optional[str] = None
    address_display: Optional[str] = None
    budget: Optional[float] = None
    within_budget: bool = Field(default=True)
    recovery_notes: list[str] = Field(default_factory=list)
    payment_options: list[PaymentOption] = Field(default_factory=list)
    selected_payment_method: str
    selected_payment_option_id: Optional[str] = None
    selected_payment_option_kind: Optional[str] = None
    selected_payment_option_label: Optional[str] = None
    confirmation_nonce: str
    confirmation_expires_at: datetime


class ConfirmationSnapshot(BaseModel):
    """One-time approval bound to the material basket the user saw."""

    model_config = ConfigDict(extra="forbid")

    nonce: str
    fingerprint: str
    payment_method: str
    payment_option_id: Optional[str] = None
    payment_option_kind: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    consumed_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


def confirmation_fingerprint(
    cart: CommerceCart,
    contract: IntentContract,
    address_id: Optional[str],
    payment_method: str,
    payment_option_id: Optional[str],
    payment_option_kind: Optional[str],
) -> str:
    """Hash every material field that requires renewed user approval."""

    items: list[dict[str, Any]] = []
    for item in sorted(cart.items, key=lambda current: (current.spin_id, current.sku_id or "")):
        normalized = normalize_pack_quantity(item.pack_size)
        items.append(
            {
                "spin_id": item.spin_id,
                "sku_id": item.sku_id,
                "product_id": item.product_id,
                "name": item.name,
                "pack_size": item.pack_size,
                "normalized_dimension": normalized.dimension if normalized else None,
                "normalized_amount": normalized.amount if normalized else None,
                "quantity": item.quantity,
                "unit_price": f"{item.unit_price:.2f}",
                "total_price": f"{item.total_price:.2f}",
            }
        )

    material = {
        "cart_id": cart.cart_id,
        "address_id": address_id or cart.address_id,
        "intent_id": contract.intent_id,
        "intent_version": contract.version,
        "payment_method": payment_method,
        "payment_option_id": payment_option_id,
        "payment_option_kind": payment_option_kind,
        "items": items,
        "item_total": f"{cart.item_total:.2f}",
        "delivery_fee": f"{cart.delivery_fee:.2f}",
        "packaging_fee": f"{cart.packaging_fee:.2f}",
        "discount": f"{cart.discount:.2f}",
        "grand_total": f"{cart.grand_total:.2f}",
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_confirmation_snapshot(
    cart: CommerceCart,
    contract: IntentContract,
    address_id: Optional[str],
    payment_method: str,
    payment_option_id: Optional[str],
    payment_option_kind: Optional[str],
    *,
    ttl: timedelta = timedelta(minutes=10),
) -> ConfirmationSnapshot:
    now = datetime.now(timezone.utc)
    return ConfirmationSnapshot(
        nonce=secrets.token_urlsafe(24),
        fingerprint=confirmation_fingerprint(
            cart,
            contract,
            address_id,
            payment_method,
            payment_option_id,
            payment_option_kind,
        ),
        payment_method=payment_method,
        payment_option_id=payment_option_id,
        payment_option_kind=payment_option_kind,
        created_at=now,
        expires_at=now + ttl,
    )


class PendingClarification(BaseModel):
    """Stored state for an open NEEDS_DECISION turn."""

    model_config = ConfigDict(extra="ignore")

    nonce: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    item_name: str = Field(..., description="Name of the item requiring user decision")
    candidates: list[RecoveryCandidate] = Field(default_factory=list)
    clarification_question: str
    removes_spin_id: Optional[str] = Field(
        default=None, description="Spin ID of cart item being replaced, if any"
    )
    intended_quantity: int = Field(
        default=1, description="Intended quantity to add/substitute"
    )


class PendingAddressChoice(BaseModel):
    """Saved provider addresses awaiting an explicit user selection."""

    model_config = ConfigDict(extra="forbid")

    addresses: list[DeliveryAddress]
    request_message: str


class PendingPaymentChoice(BaseModel):
    """Live provider payment methods awaiting an explicit user selection."""

    model_config = ConfigDict(extra="forbid")

    nonce: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    options: list[PaymentOption]
    recovery_notes: list[str] = Field(default_factory=list)



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
    capability_digest: Optional[str] = Field(default=None, exclude=True, repr=False)
    conversation_state: ConversationState = ConversationState.READY
    cart_id: Optional[str] = None
    address_id: Optional[str] = None
    address_display: Optional[str] = None

    # Intent
    intent_contract: Optional[IntentContract] = None

    # Pending states
    pending_clarification: Optional[PendingClarification] = None
    pending_address_choice: Optional[PendingAddressChoice] = None
    pending_payment_choice: Optional[PendingPaymentChoice] = None
    pending_confirmation: Optional[ConfirmationSnapshot] = None

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
    payment_status: Optional[str] = None
    payment_paas_id: Optional[str] = None
    payment_transaction_id: Optional[str] = None
    payment_url: Optional[str] = None
    payment_polling_interval_ms: Optional[int] = None
    payment_max_time_ms: Optional[int] = None
    payment_next_poll_at: Optional[datetime] = None
    payment_poll_deadline: Optional[datetime] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    child_orders: list[dict[str, Any]] = Field(default_factory=list)


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
        self._session_locks: dict[str, asyncio.Lock] = {}

    def get_or_create(self, session_id: str, customer_id: str) -> OrchestratorSession:
        """Return existing session or create a fresh READY session."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = OrchestratorSession(
                    session_id=session_id,
                    customer_id=customer_id,
                )
            elif self._sessions[session_id].customer_id != customer_id:
                raise ValueError("Session belongs to a different customer.")
            return self._sessions[session_id]

    def create_capability_session(self) -> tuple[OrchestratorSession, str]:
        """Create an opaque browser identity/session and return its capability once."""

        session_id = f"sess_{secrets.token_urlsafe(24)}"
        customer_id = f"cust_web_{secrets.token_urlsafe(24)}"
        capability = secrets.token_urlsafe(32)
        session = OrchestratorSession(
            session_id=session_id,
            customer_id=customer_id,
            capability_digest=hashlib.sha256(capability.encode("utf-8")).hexdigest(),
        )
        with self._lock:
            self._sessions[session_id] = session
        return session, capability

    def verify_capability(self, session_id: str, capability: Optional[str]) -> bool:
        """Constant-time verification for a browser session capability."""

        if not capability:
            return False
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.capability_digest is None:
                return False
            supplied = hashlib.sha256(capability.encode("utf-8")).hexdigest()
            return secrets.compare_digest(session.capability_digest, supplied)

    def get(self, session_id: str) -> Optional[OrchestratorSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, session: OrchestratorSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._session_locks.pop(session_id, None)

    def lock_for(self, session_id: str) -> asyncio.Lock:
        """Return the local async lock serializing one session transaction."""

        with self._lock:
            return self._session_locks.setdefault(session_id, asyncio.Lock())

    def all_sessions(self) -> list[OrchestratorSession]:
        with self._lock:
            return list(self._sessions.values())


# Module-level singleton used by orchestrator and API layer
default_session_store = OrchestratorSessionStore()
