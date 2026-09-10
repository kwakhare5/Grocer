"""Developer-only live-debug telemetry router (read-only inspection).

Surfaces real-time session, intent, cart fulfillment, recovery, and verification data
for live WhatsApp tests without modifying core commerce/intent logic or exposing PII.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.intent.models import IntentContract, IntentItem
from backend.intent.semantics import (
    normalize_pack_quantity,
    normalize_requested_quantity,
    required_pack_count,
)
from backend.intent.session import (
    ConversationState,
    OrchestratorSession,
    default_session_store,
)


router = APIRouter(prefix="/api/debug", tags=["developer-debug"])


# ---------------------------------------------------------------------------
# Sanitization Helpers
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_RAW_DIGITS_RE = re.compile(r"\d{7,}")


def sanitize_phone_text(text: Optional[str]) -> Optional[str]:
    """Mask phone numbers in strings so full phone numbers never leak."""
    if not text:
        return text

    def _mask(match: re.Match[str]) -> str:
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        tail = digits[-4:] if len(digits) >= 4 else digits
        return f"+91 ••••• ••{tail}"

    cleaned = _PHONE_RE.sub(_mask, text)
    return _RAW_DIGITS_RE.sub(_mask, cleaned)


def mask_customer_id(customer_id: str) -> str:
    """Mask customer identity while preserving prefix for developer debugging."""
    if not customer_id:
        return "anonymous"
    if customer_id.startswith("cust_wa_"):
        raw = customer_id[len("cust_wa_"):]
        tail = raw[-4:] if len(raw) >= 4 else raw
        return f"cust_wa_••••••{tail}"
    if customer_id.startswith("cust_web_"):
        raw = customer_id[len("cust_web_"):]
        tail = raw[-4:] if len(raw) >= 4 else raw
        return f"cust_web_••••••{tail}"
    return f"cust_••••••{customer_id[-4:]}" if len(customer_id) > 4 else "cust_••••"


def sanitize_address_display(display: Optional[str]) -> Optional[str]:
    """Sanitize address to show only general area/city without flat, house, or street numbers."""
    if not display:
        return None
    cleaned = sanitize_phone_text(display) or ""
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    # Filter out parts that contain house/flat/door numbers or digits
    non_house_parts = [
        p for p in parts
        if not re.search(r"\b(?:flat|house|apt|apartment|door|plot|no\.?|#)\b|\b\d+\b", p, re.IGNORECASE)
    ]
    if non_house_parts:
        return ", ".join(non_house_parts[-2:])
    return parts[-1] if parts else "Saved Address"


# ---------------------------------------------------------------------------
# Telemetry Schemas
# ---------------------------------------------------------------------------

class DebugItemTelemetry(BaseModel):
    item_id: str
    name: str
    original_requested_quantity: str
    interpreted_meaning: str
    dimension: Optional[str] = None
    canonical_amount: Optional[float] = None
    quantity_is_explicit: bool = False
    pack_size_preference: Optional[str] = None

    # Provider & Cart
    selected_provider_product: Optional[str] = None
    selected_spin_id: Optional[str] = None
    provider_pack_size: Optional[str] = None
    planned_cart_quantity: Optional[int] = None
    expected_fulfillment: str
    actual_canonical_cart_quantity: Optional[int] = None
    actual_fulfillment: str
    provider_max_quantity: Optional[int] = None

    # Integration flags
    is_mock: bool = False
    integration_note: Optional[str] = None


class DebugSessionSummary(BaseModel):
    session_id: str
    customer_id: str
    conversation_state: str
    turn_count: int
    original_user_request: str
    event_count: int
    has_cart: bool
    is_active: bool


class DebugLiveInspectionResponse(BaseModel):
    has_session: bool
    session_id: str
    masked_customer_id: str
    conversation_state: str
    turn_count: int
    original_user_request: str
    sanitized_address: Optional[str] = None
    cart_id: Optional[str] = None
    order_id: Optional[str] = None

    # Items matrix
    items: list[DebugItemTelemetry] = Field(default_factory=list)

    # Verification & Recovery
    verification_result: dict[str, Any] = Field(default_factory=dict)
    recovery_classification: dict[str, Any] = Field(default_factory=dict)
    clarification_required: bool = False
    clarification_details: Optional[dict[str, Any]] = None

    # Safe events
    relevant_safe_event_names: list[str] = Field(default_factory=list)

    # Diagnostics
    is_mock: bool = False
    integration_points: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_item_telemetry(
    item: IntentItem,
    session: OrchestratorSession,
    cart_items_by_spin: dict[str, Any],
) -> DebugItemTelemetry:
    """Build telemetry row for one IntentItem against live session state."""
    norm_req = normalize_requested_quantity(
        item.quantity,
        item.unit,
        item.name,
        quantity_is_explicit=item.quantity_is_explicit,
        pack_size_preference=item.pack_size_preference,
    )

    interpreted = (
        f"{norm_req.dimension}: {norm_req.amount:g} (explicit={item.quantity_is_explicit})"
        if norm_req
        else f"{item.quantity:g} {item.unit} (unnormalized)"
    )

    expected_desc = (
        f"{norm_req.amount:g} {norm_req.dimension}"
        if norm_req
        else f"{item.quantity:g} {item.unit}"
    )

    # Find matching cart item if available
    matched_cart_item = None
    for ci in cart_items_by_spin.values():
        ci_name = getattr(ci, "name", "")
        ci_spin = getattr(ci, "spin_id", "")
        if item.name.lower() in ci_name.lower() or ci_name.lower() in item.name.lower():
            matched_cart_item = ci
            break

    selected_name = getattr(matched_cart_item, "name", None) if matched_cart_item else None
    selected_spin = getattr(matched_cart_item, "spin_id", None) if matched_cart_item else None
    pack_size = getattr(matched_cart_item, "pack_size", None) if matched_cart_item else None
    cart_qty = getattr(matched_cart_item, "quantity", None) if matched_cart_item else None
    max_qty = getattr(matched_cart_item, "max_quantity", None) if matched_cart_item else None

    # If pack size is available, calculate actual fulfillment
    actual_fulfill_desc = "Pending cart resolution"
    planned_qty = cart_qty
    is_mock = False
    integration_note = None

    if matched_cart_item and pack_size:
        norm_pack = normalize_pack_quantity(pack_size)
        if norm_pack and norm_req and norm_pack.dimension == norm_req.dimension:
            actual_amount = norm_pack.amount * (cart_qty or 0)
            pct = (actual_amount / norm_req.amount * 100) if norm_req.amount > 0 else 100
            actual_fulfill_desc = f"{actual_amount:g} ({pct:.0f}%)"
            planned_qty = required_pack_count(norm_req, norm_pack)
        elif cart_qty is not None:
            actual_fulfill_desc = f"{cart_qty} packs"
    else:
        is_mock = True
        integration_note = (
            "INTEGRATION POINT: Cart item matching uses live session cart. "
            "If session is still resolving or needs address selection, cart item is null."
        )

    return DebugItemTelemetry(
        item_id=item.id,
        name=item.name,
        original_requested_quantity=f"{item.quantity:g} {item.unit}",
        interpreted_meaning=interpreted,
        dimension=norm_req.dimension if norm_req else None,
        canonical_amount=norm_req.amount if norm_req else None,
        quantity_is_explicit=item.quantity_is_explicit,
        pack_size_preference=item.pack_size_preference,
        selected_provider_product=selected_name,
        selected_spin_id=selected_spin,
        provider_pack_size=pack_size,
        planned_cart_quantity=planned_qty,
        expected_fulfillment=expected_desc,
        actual_canonical_cart_quantity=cart_qty,
        actual_fulfillment=actual_fulfill_desc,
        provider_max_quantity=max_qty,
        is_mock=is_mock,
        integration_note=integration_note,
    )


def _build_telemetry_for_session(session: OrchestratorSession) -> DebugLiveInspectionResponse:
    """Build sanitized debug inspection response for an existing OrchestratorSession."""
    contract = session.intent_contract
    raw_text = (
        contract.source_context.raw_text
        if contract and contract.source_context and contract.source_context.raw_text
        else (session.pending_address_choice.request_message if session.pending_address_choice else "(none)")
    )

    # Verification snapshot
    verification = session.last_verification or {"status": "NOT_RUN", "violations": [], "deviations": []}

    # Recovery snapshot
    recovery_dict = {
        "state": session.last_recovery_state or "none",
        "has_recovery": session.last_recovery_state is not None,
    }

    # Clarification
    clarification_required = (
        session.pending_clarification is not None
        or session.conversation_state == ConversationState.NEEDS_DECISION
    )
    clarification_details = None
    if session.pending_clarification:
        clarification_details = {
            "item_name": session.pending_clarification.item_name,
            "question": session.pending_clarification.clarification_question,
            "candidate_count": len(session.pending_clarification.candidates),
            "candidates": [
                {
                    "spin_id": c.spin_id,
                    "name": c.name,
                    "pack_size": c.pack_size,
                    "price": c.price,
                    "score": c.score,
                }
                for c in session.pending_clarification.candidates
            ],
        }

    # Build items
    items: list[DebugItemTelemetry] = []
    integration_points: list[str] = []

    if contract and contract.items:
        for item in contract.items:
            items.append(_build_item_telemetry(item, session, {}))
    else:
        integration_points.append(
            "INTEGRATION POINT: No active IntentContract in session. Showing fallback mock item shape."
        )
        items.append(
            DebugItemTelemetry(
                item_id="mock-1",
                name="toned milk",
                original_requested_quantity="1.0 L",
                interpreted_meaning="volume: 1000 ml (explicit=True)",
                dimension="volume",
                canonical_amount=1000.0,
                quantity_is_explicit=True,
                pack_size_preference="500ml",
                selected_provider_product="Amul Taaza Homogenised Toned Milk",
                selected_spin_id="spin_amul_500",
                provider_pack_size="500 ml",
                planned_cart_quantity=2,
                expected_fulfillment="1000 ml",
                actual_canonical_cart_quantity=2,
                actual_fulfillment="1000 ml (100%)",
                provider_max_quantity=6,
                is_mock=True,
                integration_note="INTEGRATION POINT: Example mock shape when session has not parsed items yet.",
            )
        )

    # Safe events
    safe_events = [ev for ev in session.events if not any(kw in ev.lower() for kw in ("token", "secret", "bearer", "cookie"))]

    return DebugLiveInspectionResponse(
        has_session=True,
        session_id=session.session_id,
        masked_customer_id=mask_customer_id(session.customer_id),
        conversation_state=session.conversation_state.value if hasattr(session.conversation_state, "value") else str(session.conversation_state),
        turn_count=session.turn_count,
        original_user_request=sanitize_phone_text(raw_text) or "(none)",
        sanitized_address=sanitize_address_display(session.address_display),
        cart_id=session.cart_id,
        order_id=session.order_id,
        items=items,
        verification_result=verification,
        recovery_classification=recovery_dict,
        clarification_required=clarification_required,
        clarification_details=clarification_details,
        relevant_safe_event_names=safe_events,
        is_mock=False,
        integration_points=integration_points,
    )


def _build_fallback_mock_response() -> DebugLiveInspectionResponse:
    """Fallback telemetry when no sessions exist on the backend yet."""
    return DebugLiveInspectionResponse(
        has_session=False,
        session_id="sess_mock_waiting",
        masked_customer_id="cust_wa_••••••1234",
        conversation_state="READY",
        turn_count=0,
        original_user_request="get 1L toned milk under ₹100",
        sanitized_address="Saved Address, Indiranagar",
        cart_id=None,
        order_id=None,
        items=[
            DebugItemTelemetry(
                item_id="mock_item_1",
                name="toned milk",
                original_requested_quantity="1.0 L",
                interpreted_meaning="volume: 1000 ml (explicit=True)",
                dimension="volume",
                canonical_amount=1000.0,
                quantity_is_explicit=True,
                pack_size_preference="500ml",
                selected_provider_product="Nandini Toned Fresh Milk",
                selected_spin_id="spin_nan_500",
                provider_pack_size="500 ml",
                planned_cart_quantity=2,
                expected_fulfillment="1000 ml",
                actual_canonical_cart_quantity=2,
                actual_fulfillment="1000 ml (100%)",
                provider_max_quantity=6,
                is_mock=True,
                integration_note="INTEGRATION POINT: Mock shape shown because no live sessions exist in backend memory.",
            )
        ],
        verification_result={"status": "PASS", "violations": [], "deviations": []},
        recovery_classification={"state": "none", "has_recovery": False},
        clarification_required=False,
        clarification_details=None,
        relevant_safe_event_names=[
            "INTENT_PARSED items=1",
            "ITEM_RESOLVED name='toned milk' spin_id=spin_nan_500",
            "CART_BUILT total=₹54",
            "VERIFICATION_PASS",
            "AWAITING_CONFIRMATION",
        ],
        is_mock=True,
        integration_points=[
            "INTEGRATION POINT: Backend currently has 0 in-memory sessions. Run a WhatsApp test to observe real live state."
        ],
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/latest", response_model=DebugLiveInspectionResponse)
async def get_latest_debug_telemetry() -> DebugLiveInspectionResponse:
    """Return sanitized debug telemetry for the most recent session or fallback mock."""
    sessions = default_session_store.all_sessions()
    if not sessions:
        return _build_fallback_mock_response()

    # Pick session with highest turn count or last created
    latest = max(sessions, key=lambda s: (s.turn_count, len(s.events)))
    return _build_telemetry_for_session(latest)


@router.get("/sessions", response_model=list[DebugSessionSummary])
async def list_debug_sessions() -> list[DebugSessionSummary]:
    """List all in-memory sessions with masked customer IDs."""
    sessions = default_session_store.all_sessions()
    summaries: list[DebugSessionSummary] = []
    for s in sessions:
        raw_req = (
            s.intent_contract.source_context.raw_text
            if s.intent_contract and s.intent_contract.source_context and s.intent_contract.source_context.raw_text
            else (s.pending_address_choice.request_message if s.pending_address_choice else "(none)")
        )
        state_val = s.conversation_state.value if hasattr(s.conversation_state, "value") else str(s.conversation_state)
        summaries.append(
            DebugSessionSummary(
                session_id=s.session_id,
                customer_id=mask_customer_id(s.customer_id),
                conversation_state=state_val,
                turn_count=s.turn_count,
                original_user_request=sanitize_phone_text(raw_req) or "(none)",
                event_count=len(s.events),
                has_cart=s.cart_id is not None,
                is_active=state_val not in ("ORDERED", "FAILED"),
            )
        )
    return summaries


@router.get("/sessions/{session_id}", response_model=DebugLiveInspectionResponse)
async def get_debug_session(session_id: str) -> DebugLiveInspectionResponse:
    """Inspect one specific session by session_id."""
    session = default_session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debug session not found")
    return _build_telemetry_for_session(session)
