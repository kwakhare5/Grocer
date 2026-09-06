"""GrocerOrchestrator — end-to-end conversational commerce loop (Spec §12, §20 Phase 6).

Connects:
    IntentParser → PolicyEngine → CommercePort → IntentVerifier → RecoveryEngine

Architecture rule (Spec §12.3):
    LLM interprets and proposes. Deterministic code enforces and verifies.
    All state transitions in this module are deterministic.

Entry points:
    handle_turn()    — main message handler: parse → build → verify → recover
    handle_choice()  — resolve a NEEDS_DECISION clarification
    handle_confirm() — explicit checkout confirmation (AWAITING_CONFIRMATION → ORDERED)
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.models import CartItemUpdate, CommerceProductItem
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError

from backend.intent.enums import PreferenceType
from backend.intent.models import IntentContract, IntentItem
from backend.intent.parser import IntentParser
from backend.intent.policy import PolicyEngine
from backend.intent.preferences import default_preference_store
from backend.intent.recovery import RecoveryCandidate, RecoveryEngine, RecoveryState
from backend.intent.storage import default_intent_store
from backend.intent.verifier import IntentVerifier, VerificationStatus
from backend.intent.session import (
    BasketItem,
    BasketSummary,
    ClarificationOption,
    ConversationState,
    OrchestratorSession,
    OrchestratorSessionStore,
    PendingClarification,
    default_session_store,
)


# ---------------------------------------------------------------------------
# Turn result model
# ---------------------------------------------------------------------------

class OrchestratorTurnResult(BaseModel):
    """Output of a single conversational turn through GrocerOrchestrator."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    conversation_state: ConversationState
    user_message: str = Field(..., description="WhatsApp-style reply to the user")
    basket_summary: Optional[BasketSummary] = None
    clarification_options: Optional[list[ClarificationOption]] = None
    requires_confirmation: bool = False
    order_id: Optional[str] = None
    order_total: Optional[float] = None
    events: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Message templates  (Spec §11)
# ---------------------------------------------------------------------------

def _msg_basket_ready(total: float, budget: Optional[float], recovery_notes: list[str]) -> str:
    budget_note = f" under ₹{budget:,.0f}" if budget else ""
    base = f"Your basket is ready — ₹{total:,.0f}{budget_note}."
    if recovery_notes:
        changes = "; ".join(recovery_notes)
        base += f" ({changes})"
    base += " Confirm to place the order."
    return base


def _msg_auto_recovered(notes: list[str], total: float) -> str:
    changes = "; ".join(notes) if notes else "some items changed"
    return (
        f"I made a few adjustments: {changes}. "
        f"The basket is ready — ₹{total:,.0f}. Confirm to place the order."
    )


def _msg_clarification(question: str, options: list[ClarificationOption]) -> str:
    lines = [question]
    for opt in options:
        lines.append(f"  {opt.index}. {opt.name} — ₹{opt.price:,.0f}")
    lines.append("Reply with the number of your choice.")
    return "\n".join(lines)


def _msg_failed(reason: str) -> str:
    return (
        f"I couldn't complete your basket: {reason}. "
        "Please adjust your request or try again."
    )


def _msg_ordered(order_id: str, total: float) -> str:
    return f"Order placed! ₹{total:,.0f}. Your order ID is {order_id}. Delivering soon. 🛵"


# ---------------------------------------------------------------------------
# Product resolution helpers
# ---------------------------------------------------------------------------

async def _search_and_pick(
    port: CommercePort,
    address_id: str,
    item: IntentItem,
) -> Optional[CartItemUpdate]:
    """Search commerce for an IntentItem and pick the best matching variant.

    Strategy:
        1. Search by item name.
        2. Prefer variant whose pack_size matches item.pack_size_preference.
        3. Prefer variant whose product name contains brand_preference.
        4. Fall back to cheapest available variant.
    Returns None if no available variants found.
    """
    try:
        results: list[CommerceProductItem] = await port.search_products(address_id, item.name)
    except Exception:
        return None

    if not results:
        return None

    # Flatten all variants across results, keeping only available ones
    all_variants = [
        (product, variant)
        for product in results
        for variant in product.variants
        if variant.in_stock
    ]
    if not all_variants:
        return None

    # Brand filter (soft preference — won't exclude if no match)
    if item.brand_preference:
        branded = [
            (p, v) for p, v in all_variants
            if item.brand_preference.lower() in p.name.lower()
        ]
        candidates = branded if branded else all_variants
    else:
        candidates = all_variants

    # Pack size preference
    if item.pack_size_preference:
        pref = item.pack_size_preference.lower()
        size_match = [(p, v) for p, v in candidates if pref in v.pack_size.lower()]
        if size_match:
            candidates = size_match

    # Pick cheapest among remaining
    _best_product, best_variant = min(candidates, key=lambda pv: pv[1].price)
    quantity = max(1, int(item.quantity))

    return CartItemUpdate(spin_id=best_variant.spin_id, quantity=quantity)


def _build_basket_summary(
    cart: Any,
    contract: IntentContract,
    recovery_notes: list[str],
) -> BasketSummary:
    """Convert a CommerceCart + contract into a BasketSummary."""
    items: list[BasketItem] = []
    for ci in cart.items:
        items.append(
            BasketItem(
                spin_id=ci.spin_id,
                name=ci.name,
                pack_size=getattr(ci, "pack_size", ""),
                quantity=ci.quantity,
                unit_price=ci.unit_price,
                line_total=ci.quantity * ci.unit_price,
                substituted=bool(recovery_notes),
            )
        )
    budget = contract.budget.max_budget if contract.budget else None
    grand_total = cart.grand_total
    return BasketSummary(
        cart_id=cart.cart_id,
        items=items,
        item_total=cart.item_total,
        delivery_fee=cart.delivery_fee,
        grand_total=grand_total,
        budget=budget,
        within_budget=(budget is None or grand_total <= budget),
        recovery_notes=recovery_notes,
    )


def _candidates_to_options(candidates: list[RecoveryCandidate]) -> list[ClarificationOption]:
    return [
        ClarificationOption(
            index=i + 1,
            spin_id=c.spin_id,
            name=c.name,
            pack_size=c.pack_size,
            price=c.price,
            score=c.score,
        )
        for i, c in enumerate(candidates)
    ]


# ---------------------------------------------------------------------------
# GrocerOrchestrator
# ---------------------------------------------------------------------------

class GrocerOrchestrator:
    """Stateless conversational commerce orchestrator (Spec §12, Phase 6).

    Reads/writes OrchestratorSession via OrchestratorSessionStore.
    All routing decisions are deterministic — no LLM control flow.
    """

    def __init__(
        self,
        commerce_adapter: Optional[CommercePort] = None,
        session_store: Optional[OrchestratorSessionStore] = None,
    ) -> None:
        self._port: CommercePort = commerce_adapter or get_commerce_adapter()
        self._store: OrchestratorSessionStore = session_store or default_session_store
        self._parser = IntentParser()
        self._verifier = IntentVerifier()
        self._policy = PolicyEngine()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def handle_turn(
        self,
        session_id: str,
        customer_id: str,
        message: str,
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Process one conversational message through the full commerce loop.

        Flow: parse → preferences → resolve products → build cart
              → verify → recover if needed → return result.
        """
        session = self._store.get_or_create(session_id, customer_id)
        session.turn_count += 1
        events: list[str] = []

        if address_id:
            session.address_id = address_id
        effective_address = session.address_id or f"addr-{customer_id}"

        # 1. Parse intent
        session.conversation_state = ConversationState.BUILDING
        contract = self._parse_intent(message, session, events)
        session.intent_contract = contract
        default_intent_store.save(contract)

        # 2. Apply stored soft preferences (Spec §7 — memory does NOT override current request)
        self._apply_preferences(contract, customer_id, events)

        # 3. Resolve products → CartItemUpdate list
        cart_id = session.cart_id or f"cart-{session_id}"
        session.cart_id = cart_id

        resolved_items = await self._resolve_items(contract, effective_address, events)
        if not resolved_items:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("no matching products found for your request"),
                events=events,
            )

        # 4. Build cart
        try:
            cart = await self._port.update_cart(
                items=resolved_items, cart_id=cart_id, address_id=effective_address
            )
        except Exception as exc:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(str(exc)),
                events=events,
            )

        events.append(f"CART_BUILT cart_id={cart_id} total=₹{cart.grand_total}")

        # 5. Verify intent vs cart (Spec §9)
        verification = self._verifier.verify(contract, cart)
        session.last_verification = {"status": verification.status.value}
        events.append(f"VERIFICATION_{verification.status.value.upper()}")

        if verification.status == VerificationStatus.PASS:
            return self._make_awaiting_confirmation(session, contract, cart, [], events)

        # 6. Recovery (Spec §10)
        events.append("RECOVERY_STARTED")
        session.conversation_state = ConversationState.RECOVERING

        try:
            available: list[CommerceProductItem] = await self._port.get_go_to_items(effective_address)
        except Exception:
            available = []

        engine = RecoveryEngine(policy_engine=self._policy)
        updated_cart, new_verification, outcome = await engine.execute_recovery(
            contract=contract,
            cart_id=cart_id,
            commerce_port=self._port,
            verifier=self._verifier,
            available_products=available,
            verification_result=verification,
            address_id=effective_address,
        )

        session.last_recovery_state = outcome.state.value
        events.append(f"RECOVERY_{outcome.state.value.upper()}")

        if outcome.state == RecoveryState.RECOVERED:
            recovery_notes = [a.reason for a in outcome.recovery_actions]
            return self._make_awaiting_confirmation(
                session, contract, updated_cart, recovery_notes, events
            )

        elif outcome.state == RecoveryState.NEEDS_USER_DECISION:
            candidates = outcome.candidates_for_user or []
            options = _candidates_to_options(candidates)
            item_name = (
                verification.violations[0].target
                if verification.violations
                else "an item"
            )
            question = outcome.message or (
                f"Your usual {item_name} is unavailable. Which alternative would you prefer?"
            )
            session.pending_clarification = PendingClarification(
                item_name=item_name,
                candidates=candidates,
                clarification_question=question,
            )
            session.conversation_state = ConversationState.NEEDS_DECISION
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.NEEDS_DECISION,
                user_message=_msg_clarification(question, options),
                clarification_options=options,
                events=events,
            )

        else:
            # BLOCKED or FAILED
            reason = (
                verification.violations[0].detail
                if verification.violations
                else "a constraint could not be satisfied"
            )
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(reason),
                events=events,
            )

    async def handle_choice(
        self,
        session_id: str,
        chosen_spin_id: str,
    ) -> OrchestratorTurnResult:
        """Resolve a NEEDS_DECISION clarification with the user's chosen spin_id."""
        session = self._store.get(session_id)
        if session is None:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("session not found"),
                events=["SESSION_NOT_FOUND"],
            )

        if session.conversation_state != ConversationState.NEEDS_DECISION:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message="No pending decision. Please send a new grocery request.",
                events=["NO_PENDING_DECISION"],
            )

        events: list[str] = [f"USER_CHOICE spin_id={chosen_spin_id}"]
        contract = session.intent_contract
        effective_address = session.address_id or f"addr-{session.customer_id}"
        cart_id = session.cart_id or f"cart-{session_id}"

        # Update cart with the chosen variant
        try:
            cart = await self._port.update_cart(
                items=[CartItemUpdate(spin_id=chosen_spin_id, quantity=1)],
                cart_id=cart_id,
                address_id=effective_address,
            )
        except Exception as exc:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(str(exc)),
                events=events,
            )

        session.pending_clarification = None
        events.append(f"CART_UPDATED cart_id={cart_id}")

        if contract is None:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("no active intent contract"),
                events=events,
            )

        # Re-verify after user choice
        verification = self._verifier.verify(contract, cart)
        events.append(f"VERIFICATION_{verification.status.value.upper()}")

        if verification.status == VerificationStatus.PASS:
            return self._make_awaiting_confirmation(
                session, contract, cart, ["Applied your choice."], events
            )

        reason = (
            verification.violations[0].detail if verification.violations else "constraint violation"
        )
        session.conversation_state = ConversationState.FAILED
        self._store.save(session)
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed(reason),
            events=events,
        )

    async def handle_confirm(
        self,
        session_id: str,
        payment_method: str = "UPI",
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Execute checkout after explicit user confirmation (Spec §6, §8.3).

        CRITICAL: Raises UnconfirmedCheckoutError if session is not in
        AWAITING_CONFIRMATION state. Checkout is always server-side gated.
        """
        session = self._store.get(session_id)
        if session is None:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("session not found"),
                events=["SESSION_NOT_FOUND"],
            )

        if session.conversation_state != ConversationState.AWAITING_CONFIRMATION:
            raise UnconfirmedCheckoutError(
                f"Checkout requires session in AWAITING_CONFIRMATION state, "
                f"current: {session.conversation_state.value}"
            )

        contract = session.intent_contract
        cart_id = session.cart_id or f"cart-{session_id}"
        effective_address = address_id or session.address_id or f"addr-{session.customer_id}"
        events: list[str] = ["CHECKOUT_INITIATED"]

        # Re-fetch cart for pre-checkout verification (Spec §9.3)
        try:
            cart = await self._port.get_cart(cart_id)
        except Exception as exc:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(f"cart fetch failed: {exc}"),
                events=events,
            )

        # Pre-checkout verification (mandatory — Spec §9.3, §17.5)
        if contract is not None:
            pre_check = self._verifier.verify_checkout(
                contract=contract,
                cart=cart,
                explicit_confirmation=True,
            )
            events.append(f"PRE_CHECKOUT_VERIFY_{pre_check.status.value.upper()}")
            if pre_check.status != VerificationStatus.PASS:
                session.conversation_state = ConversationState.FAILED
                reason = (
                    pre_check.violations[0].detail
                    if pre_check.violations
                    else "pre-checkout verification failed"
                )
                self._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.FAILED,
                    user_message=_msg_failed(reason),
                    events=events,
                )

        # Execute checkout
        try:
            order = await self._port.checkout(
                cart_id=cart_id,
                payment_method=payment_method,
                explicit_confirmation=True,
                address_id=effective_address,
            )
        except UnconfirmedCheckoutError:
            raise
        except Exception as exc:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(str(exc)),
                events=events,
            )

        session.conversation_state = ConversationState.ORDERED
        session.order_id = order.order_id
        session.order_total = order.grand_total
        events.append(f"CHECKOUT_SUCCEEDED order_id={order.order_id}")
        self._store.save(session)

        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=ConversationState.ORDERED,
            user_message=_msg_ordered(order.order_id, order.grand_total),
            order_id=order.order_id,
            order_total=order.grand_total,
            events=events,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_intent(
        self,
        message: str,
        session: OrchestratorSession,
        events: list[str],
    ) -> IntentContract:
        """Parse message → IntentContract, inheriting session_id."""
        contract = self._parser.parse(message, session_id=session.session_id)
        # Merge with prior contract only if this is a refinement (no items)
        if session.intent_contract and not _is_fresh_request(message):
            contract = _merge_contracts(session.intent_contract, contract)
        events.append(
            f"INTENT_PARSED goal={contract.goal!r} items={len(contract.items)}"
        )
        return contract

    def _apply_preferences(
        self,
        contract: IntentContract,
        customer_id: str,
        events: list[str],
    ) -> None:
        """Load established soft preferences and apply where not overridden (Spec §7).

        Precedence: current request > stored preference (Spec §5.3).
        """
        prefs = default_preference_store.get_preferences(customer_id)
        applied = 0
        for pref in prefs:
            if pref.preference_type != PreferenceType.BRAND:
                continue
            if not pref.is_established:
                continue
            for item in contract.items:
                if (
                    pref.product_or_category.lower() in item.name.lower()
                    and item.brand_preference is None  # don't override explicit request
                ):
                    item.brand_preference = pref.value
                    applied += 1
        if applied:
            events.append(f"PREFERENCES_APPLIED count={applied}")

    async def _resolve_items(
        self,
        contract: IntentContract,
        address_id: str,
        events: list[str],
    ) -> list[CartItemUpdate]:
        """Resolve each IntentItem into a CartItemUpdate via CommercePort search."""
        updates: list[CartItemUpdate] = []
        for item in contract.items:
            update = await _search_and_pick(self._port, address_id, item)
            if update:
                updates.append(update)
                events.append(f"ITEM_RESOLVED name={item.name!r} spin_id={update.spin_id}")
            else:
                events.append(f"ITEM_UNRESOLVED name={item.name!r}")
        return updates

    def _make_awaiting_confirmation(
        self,
        session: OrchestratorSession,
        contract: IntentContract,
        cart: Any,
        recovery_notes: list[str],
        events: list[str],
    ) -> OrchestratorTurnResult:
        """Transition to AWAITING_CONFIRMATION and return the full result."""
        session.conversation_state = ConversationState.AWAITING_CONFIRMATION
        self._store.save(session)

        basket = _build_basket_summary(cart, contract, recovery_notes)
        budget = contract.budget.max_budget if contract.budget else None

        msg = (
            _msg_auto_recovered(recovery_notes, cart.grand_total)
            if recovery_notes
            else _msg_basket_ready(cart.grand_total, budget, [])
        )

        events.append("AWAITING_CONFIRMATION")
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.AWAITING_CONFIRMATION,
            user_message=msg,
            basket_summary=basket,
            requires_confirmation=True,
            events=events,
        )


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def _is_fresh_request(message: str) -> bool:
    """Heuristic: treat message as fresh grocery request vs a refinement."""
    fresh_keywords = {
        "get", "buy", "order", "weekly", "monthly", "groceries",
        "vegetables", "staples", "restock", "need",
    }
    lower = message.lower()
    return any(kw in lower for kw in fresh_keywords)


def _merge_contracts(existing: IntentContract, new: IntentContract) -> IntentContract:
    """Merge new contract onto existing, respecting intent precedence (Spec §5.3)."""
    if new.items:
        return new  # New explicit request wins entirely
    merged = copy.deepcopy(existing)
    merged.intent_id = new.intent_id
    merged.version = existing.version + 1
    if new.goal:
        merged.goal = new.goal
    if new.hard_constraints:
        merged.hard_constraints = new.hard_constraints
    if new.budget and new.budget.max_budget:
        merged.budget = new.budget
    return merged
