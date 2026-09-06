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
from backend.intent.recovery import RecoveryCandidate, RecoveryState
from backend.intent.recovery_loop import LoopingRecoveryEngine
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

    all_variants = [
        (product, variant)
        for product in results
        for variant in product.variants
        if variant.in_stock
    ]
    if not all_variants:
        return None

    if item.brand_preference:
        branded = [
            (p, v) for p, v in all_variants
            if item.brand_preference.lower() in p.name.lower()
        ]
        candidates = branded if branded else all_variants
    else:
        candidates = all_variants

    if item.pack_size_preference:
        pref = item.pack_size_preference.lower()
        size_match = [(p, v) for p, v in candidates if pref in v.pack_size.lower()]
        if size_match:
            candidates = size_match

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

    async def handle_turn(
        self,
        session_id: str,
        customer_id: str,
        message: str,
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Process one conversational message through the full commerce loop."""
        session = self._store.get_or_create(session_id, customer_id)
        session.turn_count += 1
        events: list[str] = []

        if address_id:
            session.address_id = address_id
        effective_address = session.address_id or f"addr-{customer_id}"

        session.conversation_state = ConversationState.BUILDING
        contract = self._parse_intent(message, session, events)
        session.intent_contract = contract
        default_intent_store.save(contract)

        self._apply_preferences(contract, customer_id, events)

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

        verification = self._verifier.verify(contract, cart)
        session.last_verification = {"status": verification.status.value}
        events.append(f"VERIFICATION_{verification.status.value.upper()}")

        if verification.status == VerificationStatus.PASS:
            return self._make_awaiting_confirmation(session, contract, cart, [], events)

        events.append("RECOVERY_STARTED")
        session.conversation_state = ConversationState.RECOVERING

        try:
            available: list[CommerceProductItem] = await self._port.get_go_to_items(effective_address)
        except Exception:
            available = []

        engine = LoopingRecoveryEngine(policy_engine=self._policy)
        updated_cart, new_verification, outcome = await engine.execute_recovery(
            contract=contract,
            cart_id=cart_id,
            commerce_port=self._port,
            verifier=self._verifier,
            available_products=available,
            verification_result=verification,
            address_id=effective_address,
        )

        session.last_verification = {"status": new_verification.status.value}
        session.last_recovery_state = outcome.state.value
        events.append(f"RECOVERY_{outcome.state.value.upper()}")
        events.append(f"POST_RECOVERY_VERIFY_{new_verification.status.value.upper()}")

        if outcome.state == RecoveryState.RECOVERED and new_verification.status == VerificationStatus.PASS:
            recovery_notes = [a.reason for a in outcome.recovery_actions]
            return self._make_awaiting_confirmation(
                session, contract, updated_cart, recovery_notes, events
            )

        if outcome.state == RecoveryState.NEEDS_USER_DECISION:
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
            removes_spin_id = None
            intended_quantity = 1
            if outcome.recovery_actions:
                top_act = outcome.recovery_actions[0]
                removes_spin_id = top_act.removes_spin_id
                intended_quantity = max(1, top_act.quantity)
            else:
                matched_cart_item = next(
                    (ci for ci in cart.items if item_name.lower() in ci.name.lower() or ci.name.lower() in item_name.lower()),
                    None,
                )
                if matched_cart_item:
                    removes_spin_id = matched_cart_item.spin_id
                    intended_quantity = matched_cart_item.quantity

            session.pending_clarification = PendingClarification(
                item_name=item_name,
                candidates=candidates,
                clarification_question=question,
                removes_spin_id=removes_spin_id,
                intended_quantity=intended_quantity,
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

        reason = (
            new_verification.violations[0].detail
            if new_verification.violations
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

    async def handle_choice(self, session_id: str, chosen_spin_id: str) -> OrchestratorTurnResult:
        """Resolve a NEEDS_DECISION clarification with the user's chosen spin_id."""
        session = self._store.get(session_id)
        if session is None:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("session not found"),
                events=["SESSION_NOT_FOUND"],
            )

        if (
            session.conversation_state != ConversationState.NEEDS_DECISION
            or not session.pending_clarification
        ):
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message="No pending decision. Please send a new grocery request.",
                events=["NO_PENDING_DECISION"],
            )

        # 1. Validate chosen_spin_id strictly inside orchestrator
        pending = session.pending_clarification
        matching_candidate = next(
            (c for c in pending.candidates if c.spin_id == chosen_spin_id),
            None,
        )
        if matching_candidate is None:
            options = _candidates_to_options(pending.candidates)
            events = list(session.events) + [f"INVALID_CHOICE spin_id={chosen_spin_id}"]
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.NEEDS_DECISION,
                user_message=(
                    f"'{chosen_spin_id}' is not one of the available options. Please choose from:\n"
                    + _msg_clarification(pending.clarification_question, options)
                ),
                clarification_options=options,
                events=events,
            )

        events: list[str] = [f"USER_CHOICE spin_id={chosen_spin_id}"]
        contract = session.intent_contract
        if contract is None:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("no active intent contract"),
                events=events,
            )

        effective_address = session.address_id or f"addr-{session.customer_id}"
        cart_id = session.cart_id or f"cart-{session_id}"

        # 2. Fetch live cart to preserve all existing items
        try:
            current_cart = await self._port.get_cart(cart_id)
        except Exception as exc:
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(f"could not fetch cart: {exc}"),
                events=events,
            )

        # 3. Determine quantity to add / replace
        quantity = pending.intended_quantity
        intent_item = next(
            (
                item
                for item in contract.items
                if item.name.lower() in pending.item_name.lower()
                or pending.item_name.lower() in item.name.lower()
            ),
            None,
        )
        if intent_item and contract.pack_size_rules.preferred_multiples:
            engine = RecoveryEngine(policy_engine=self._policy)
            multiple = engine._calculate_pack_multiple(intent_item, matching_candidate.pack_size)
            if multiple > 1:
                quantity = multiple * max(1, int(intent_item.quantity))

        removes_spin_id = pending.removes_spin_id
        if not removes_spin_id:
            matched = next(
                (
                    ci
                    for ci in current_cart.items
                    if pending.item_name.lower() in ci.name.lower()
                    or ci.name.lower() in pending.item_name.lower()
                ),
                None,
            )
            if matched:
                removes_spin_id = matched.spin_id

        # 4. Build cart updates preserving ALL other items
        updates: list[CartItemUpdate] = []
        replaced = False
        for ci in current_cart.items:
            if removes_spin_id and ci.spin_id == removes_spin_id:
                updates.append(CartItemUpdate(spin_id=chosen_spin_id, quantity=quantity))
                replaced = True
            else:
                updates.append(CartItemUpdate(spin_id=ci.spin_id, quantity=ci.quantity))

        if not replaced:
            updates.append(CartItemUpdate(spin_id=chosen_spin_id, quantity=quantity))

        # 5. Apply update to commerce port
        try:
            cart = await self._port.update_cart(
                items=updates,
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

        events.append(f"CART_UPDATED cart_id={cart_id}")

        # 6. Re-verify full cart against full intent
        verification = self._verifier.verify(contract, cart)
        session.last_verification = {"status": verification.status.value}
        events.append(f"VERIFICATION_{verification.status.value.upper()}")

        if verification.status == VerificationStatus.PASS:
            session.pending_clarification = None
            return self._make_awaiting_confirmation(
                session, contract, cart, [f"Applied your choice: {matching_candidate.name}."], events
            )

        # 7. If chosen option still violates intent (e.g. hard budget or dietary)
        events.append("CHOICE_VIOLATION_DETECTED")
        reason = (
            verification.violations[0].detail if verification.violations else "constraint violation"
        )

        try:
            available: list[CommerceProductItem] = await self._port.get_go_to_items(effective_address)
        except Exception:
            available = []

        engine = RecoveryEngine(policy_engine=self._policy)
        outcome = engine.recover(
            contract=contract,
            cart=cart,
            verification_result=verification,
            available_products=available,
            attempt_number=1,
            max_attempts=3,
        )

        if outcome.state == RecoveryState.NEEDS_USER_DECISION:
            new_candidates = outcome.candidates_for_user or []
            options = _candidates_to_options(new_candidates)
            session.pending_clarification = PendingClarification(
                item_name=(
                    verification.violations[0].target
                    if verification.violations
                    else pending.item_name
                ),
                candidates=new_candidates,
                clarification_question=outcome.message,
                removes_spin_id=chosen_spin_id,
                intended_quantity=quantity,
            )
            session.conversation_state = ConversationState.NEEDS_DECISION
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.NEEDS_DECISION,
                user_message=f"That choice causes an issue: {reason}. {outcome.message}",
                clarification_options=options,
                events=events,
            )
        else:
            session.pending_clarification = None
            session.conversation_state = ConversationState.FAILED
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed(f"Selected option cannot be used: {reason}"),
                events=events,
            )

    async def handle_confirm(
        self,
        session_id: str,
        payment_method: str = "UPI",
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Execute checkout after explicit user confirmation (Spec §6, §8.3)."""
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

    def _parse_intent(self, message: str, session: OrchestratorSession, events: list[str]) -> IntentContract:
        """Parse message → IntentContract, inheriting session_id."""
        contract = self._parser.parse(message, session_id=session.session_id)
        if session.intent_contract and not _is_fresh_request(message):
            contract = _merge_contracts(session.intent_contract, contract, message)
        events.append(
            f"INTENT_PARSED goal={contract.goal!r} items={len(contract.items)}"
        )
        return contract

    def _apply_preferences(self, contract: IntentContract, customer_id: str, events: list[str]) -> None:
        """Load established soft preferences and apply where not overridden (Spec §7)."""
        prefs = default_preference_store.get_preferences(customer_id)
        applied = 0
        for pref in prefs:
            if pref.preference_type != PreferenceType.BRAND or not pref.is_established:
                continue
            for item in contract.items:
                if pref.product_or_category.lower() in item.name.lower() and item.brand_preference is None:
                    item.brand_preference = pref.value
                    applied += 1
        if applied:
            events.append(f"PREFERENCES_APPLIED count={applied}")

    async def _resolve_items(self, contract: IntentContract, address_id: str, events: list[str]) -> list[CartItemUpdate]:
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


<<<<<<< HEAD
=======
def _is_incremental_add(message: str) -> bool:
    lower = message.lower().strip()
    return lower.startswith(("add", "also add", "plus", "and add", "include"))


>>>>>>> b916129 (feat(intent): implement deterministic recovery loop, failure injection, and golden oos test)
def _is_fresh_request(message: str) -> bool:
    """Heuristic: treat message as fresh grocery request vs a refinement."""
    lower = message.lower().strip()
    if _is_incremental_add(message):
        return False
    fresh_keywords = {
        "get", "buy", "order", "weekly", "monthly", "groceries",
        "vegetables", "staples", "restock", "need",
    }
    return any(kw in lower for kw in fresh_keywords)


def _merge_contracts(
    existing: IntentContract, new: IntentContract, message: str = ""
) -> IntentContract:
    """Merge new contract onto existing, respecting intent precedence (Spec §5.3)."""
    merged = copy.deepcopy(existing)
    merged.intent_id = new.intent_id
    merged.version = existing.version + 1

    if _is_incremental_add(message):
        existing_names = {it.name.lower() for it in merged.items}
        for it in new.items:
            if it.name.lower() not in existing_names:
                merged.items.append(it)
        if new.budget and new.budget.max_budget:
            merged.budget = new.budget
        return merged

    if new.items:
        return new  # New explicit request wins entirely

    if new.goal:
        merged.goal = new.goal
    if new.hard_constraints:
        merged.hard_constraints = new.hard_constraints
    if new.budget and new.budget.max_budget:
        merged.budget = new.budget
    return merged

