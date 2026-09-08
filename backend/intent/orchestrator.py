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
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceOrderResult,
    CommerceProductItem,
    OrderChildResult,
    PaymentOption,
)
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.exceptions import CommerceError, UnconfirmedCheckoutError

from backend.intent.enums import PreferenceType
from backend.intent.models import IntentContract, IntentItem
from backend.intent.parser import IntentParser
from backend.intent.policy import PolicyEngine
from backend.intent.preferences import default_preference_store
from backend.intent.recovery import RecoveryCandidate, RecoveryEngine, RecoveryState
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.semantics import (
    brand_identity_matches,
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)
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
    confirmation_fingerprint,
    create_confirmation_snapshot,
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
    clarification_nonce: Optional[str] = None
    requires_confirmation: bool = False
    order_id: Optional[str] = None
    order_total: Optional[float] = None
    payment_status: Optional[str] = None
    payment_url: Optional[str] = None
    child_orders: list[OrderChildResult] = Field(default_factory=list)
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


def _msg_ordered(order_id: str, total: Optional[float]) -> str:
    total_note = f" Total ₹{total:,.0f}." if total is not None else ""
    return f"Order placed.{total_note} Order ID: {order_id}."


def _msg_payment_pending(order_id: Optional[str], payment_url: Optional[str]) -> str:
    order_note = f" for order {order_id}" if order_id else ""
    action = f" Complete payment here: {payment_url}" if payment_url else ""
    return f"Payment is pending{order_note}.{action} I will report success only after confirmation."


# ---------------------------------------------------------------------------
# Product resolution helpers
# ---------------------------------------------------------------------------

async def _search_and_pick(
    port: CommercePort,
    address_id: str,
    item: IntentItem,
) -> Optional[CartItemUpdate]:
    """Search commerce for an IntentItem and pick the best matching variant.

    Candidates must first satisfy product, explicit-brand, and physical-quantity
    semantics. Price ranks only the remaining semantically valid candidates.
    Returns None if no available variants found.
    """
    try:
        results: list[CommerceProductItem] = await port.search_products(address_id, item.name)
    except CommerceError:
        return None

    if not results:
        return None

    all_variants = [
        (product, variant)
        for product in results
        for variant in product.variants
        if variant.in_stock
        and (
            product_identity_matches(
                item.name,
                variant.name,
                item.category,
                product.category,
            )
            or product_identity_matches(
                item.name,
                product.name,
                item.category,
                product.category,
            )
        )
    ]
    if not all_variants:
        return None

    if item.brand_preference:
        candidates = [
            (product, variant)
            for product, variant in all_variants
            if brand_identity_matches(
                item.brand_preference,
                product.brand,
                product.name,
                variant.name,
            )
        ]
        if not candidates:
            return None
    else:
        candidates = all_variants

    requested = normalize_requested_quantity(
        item.quantity,
        item.unit,
        item.name,
        quantity_is_explicit=item.quantity_is_explicit,
        pack_size_preference=item.pack_size_preference,
    )
    if requested is None:
        return None

    resolved: list[tuple[CommerceProductItem, Any, int]] = []
    for product, variant in candidates:
        pack_count = required_pack_count(
            requested,
            normalize_pack_quantity(variant.pack_size),
        )
        if pack_count is not None:
            resolved.append((product, variant, pack_count))
    if not resolved:
        return None

    preferred_pack = normalize_pack_quantity(item.pack_size_preference or "")

    def rank(candidate: tuple[CommerceProductItem, Any, int]) -> tuple[bool, float, float]:
        _product, variant, pack_count = candidate
        candidate_pack = normalize_pack_quantity(variant.pack_size)
        misses_preference = preferred_pack is not None and candidate_pack != preferred_pack
        return misses_preference, variant.price * pack_count, variant.price

    _best_product, best_variant, quantity = min(resolved, key=rank)

    return CartItemUpdate(spin_id=best_variant.spin_id, quantity=quantity)


def _build_basket_summary(
    cart: Any,
    contract: IntentContract,
    recovery_notes: list[str],
    *,
    confirmation_nonce: str,
    confirmation_expires_at: Any,
    payment_options: list[PaymentOption],
    selected_payment_method: str,
    selected_payment_option_id: Optional[str],
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
        packaging_fee=cart.packaging_fee,
        discount=cart.discount,
        grand_total=grand_total,
        address_id=cart.address_id,
        budget=budget,
        within_budget=(budget is None or grand_total <= budget),
        recovery_notes=recovery_notes,
        payment_options=payment_options,
        selected_payment_method=selected_payment_method,
        selected_payment_option_id=selected_payment_option_id,
        confirmation_nonce=confirmation_nonce,
        confirmation_expires_at=confirmation_expires_at,
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
        recovery_engine: Optional[LoopingRecoveryEngine] = None,
        verifier: Optional[IntentVerifier] = None,
    ) -> None:
        self._port: CommercePort = commerce_adapter or get_commerce_adapter()
        self._store: OrchestratorSessionStore = session_store or default_session_store
        self._parser = IntentParser()
        self._verifier = verifier or IntentVerifier()
        self._policy = PolicyEngine()
        self._recovery = recovery_engine

    async def handle_turn(
        self,
        session_id: str,
        customer_id: str,
        message: str,
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Run one turn with provider credentials bound to its customer."""
        async with self._store.lock_for(session_id):
            with self._port.customer_scope(customer_id):
                return await self._handle_turn_scoped(
                    session_id=session_id,
                    customer_id=customer_id,
                    message=message,
                    address_id=address_id,
                )

    async def _handle_turn_scoped(
        self,
        session_id: str,
        customer_id: str,
        message: str,
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Process one conversational message through the full commerce loop."""
        session = self._store.get_or_create(session_id, customer_id)
        session.pending_confirmation = None
        session.turn_count += 1
        events: list[str] = []

        if address_id:
            session.address_id = address_id

        # Phase B: Strict live address resolution per Swiggy Builders Club spec
        if not session.address_id:
            from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
            if isinstance(self._port, SwiggyMCPAdapter):
                try:
                    addresses = await self._port.get_addresses(customer_id)
                except Exception:
                    addresses = []

                if len(addresses) == 1:
                    session.address_id = addresses[0].id
                elif len(addresses) > 1:
                    lower_msg = message.lower().strip()
                    selected = None
                    for idx, addr in enumerate(addresses, 1):
                        if lower_msg in (str(idx), addr.label.lower(), addr.id.lower()):
                            selected = addr
                            break
                        if addr.street and lower_msg in addr.street.lower():
                            selected = addr
                            break

                    if selected:
                        session.address_id = selected.id
                        events.append(f"ADDRESS_SELECTED id={selected.id}")
                    else:
                        session.conversation_state = ConversationState.NEEDS_DECISION
                        self._store.save(session)
                        options_text = "\n".join(
                            f"{i}. {a.label}: {a.street or a.city or 'Saved Address'}"
                            for i, a in enumerate(addresses, 1)
                        )
                        return OrchestratorTurnResult(
                            session_id=session.session_id,
                            conversation_state=ConversationState.NEEDS_DECISION,
                            user_message=f"Which address would you like to use for delivery?\n{options_text}\nReply with the number or label of your choice.",
                            events=events + ["NEEDS_ADDRESS_SELECTION"],
                        )
                elif len(addresses) == 0:
                    session.conversation_state = ConversationState.FAILED
                    self._store.save(session)
                    return OrchestratorTurnResult(
                        session_id=session.session_id,
                        conversation_state=ConversationState.FAILED,
                        user_message="No delivery address found for your Swiggy account. Please add an address in Swiggy first.",
                        events=events + ["NO_ADDRESS_FOUND"],
                    )

        effective_address = session.address_id or f"addr-{customer_id}"
        session.address_id = effective_address

        session.conversation_state = ConversationState.BUILDING
        cart_id = session.cart_id or f"cart-{session_id}"
        session.cart_id = cart_id

        prior_recovery_notes: list[str] = []
        live_cart: Optional[CommerceCart] = None
        new_contract_items: list[IntentItem] = []

        # 1. Inspect live commerce cart for drift against prior intent contract
        prior_contract = session.intent_contract
        if session.turn_count > 1 and session.cart_id and prior_contract and not _is_fresh_request(message):
            cart_fetch_error: Optional[Exception] = None
            try:
                live_cart = await self._port.get_cart(cart_id)
            except Exception as exc:
                live_cart = None
                cart_fetch_error = exc

            drift = self._verifier.verify(prior_contract, live_cart) if live_cart else None
            needs_recovery = False

            if cart_fetch_error is not None:
                needs_recovery = True
            elif live_cart:
                is_below_min = bool(live_cart.items and live_cart.grand_total < live_cart.min_order_threshold)
                if (drift and drift.status != VerificationStatus.PASS) or not live_cart.is_serviceable or is_below_min:
                    needs_recovery = True

            if needs_recovery:
                events.append("RECOVERY_STARTED")
                session.conversation_state = ConversationState.RECOVERING
                try:
                    available = await self._port.search_products(effective_address, "")
                except Exception:
                    available = []
                engine = self._recovery or LoopingRecoveryEngine(
                    policy_engine=self._policy,
                    verifier=self._verifier,
                )
                rec_result = await engine.run(
                    contract=prior_contract,
                    cart_id=cart_id,
                    commerce_port=self._port,
                    available_products=available,
                    address_id=effective_address,
                    verifier=self._verifier,
                )
                events.append(f"RECOVERY_{rec_result.state.value.upper()}")
                events.append(f"POST_RECOVERY_VERIFY_{rec_result.verification.status.value.upper()}")
                if rec_result.state == RecoveryState.RECOVERED:
                    prior_recovery_notes = rec_result.recovery_notes
                    live_cart = rec_result.cart
                    if not _is_incremental_add(message):
                        return await self._make_awaiting_confirmation(
                            session, prior_contract, live_cart, prior_recovery_notes, events
                        )
                elif rec_result.state == RecoveryState.NEEDS_USER_DECISION:
                    outcome = rec_result.outcome or RecoveryOutcome(
                        state=rec_result.state,
                        failure_class=FailureClass.UNKNOWN,
                        message=rec_result.outcome.message if rec_result.outcome else "Clarification needed",
                        attempt_number=rec_result.attempts,
                        can_auto_apply=False,
                        remaining_violations=rec_result.verification.violations,
                    )
                    return self._handle_needs_decision(
                        session,
                        rec_result.cart or live_cart,
                        drift or rec_result.verification,
                        outcome,
                        events,
                    )
                else:
                    reason = (
                        rec_result.verification.violations[0].detail
                        if rec_result.verification.violations
                        else "a constraint could not be satisfied"
                    )
                    return self._handle_failed(session, reason, events)

        # 2. Parse current message into IntentContract and update session
        contract = self._parse_intent(message, session, events)
        session.intent_contract = contract
        default_intent_store.save(contract)

        self._apply_preferences(contract, customer_id, events)

        if live_cart and live_cart.items:
            existing_updates = [
                CartItemUpdate(spin_id=ci.spin_id, quantity=ci.quantity)
                for ci in live_cart.items
            ]
            new_contract_items = [
                item for item in contract.items
                if not any(
                    item.name.lower() in ci.name.lower() or ci.name.lower() in item.name.lower()
                    for ci in live_cart.items
                )
            ]
            if new_contract_items:
                new_updates: list[CartItemUpdate] = []
                for item in new_contract_items:
                    update = await _search_and_pick(self._port, effective_address, item)
                    if update:
                        new_updates.append(update)
                        events.append(f"ITEM_RESOLVED name={item.name!r} spin_id={update.spin_id}")
                    else:
                        events.append(f"ITEM_UNRESOLVED name={item.name!r}")
                resolved_items = existing_updates + new_updates
            else:
                resolved_items = existing_updates
        else:
            resolved_items = await self._resolve_items(contract, effective_address, events)

        if not resolved_items:
            return self._handle_failed(session, "no matching products found for your request", events)

        if not live_cart or not live_cart.items or new_contract_items:
            try:
                cart = await self._port.update_cart(
                    items=resolved_items, cart_id=cart_id, address_id=effective_address
                )
            except Exception as exc:
                return self._handle_failed(session, str(exc), events)
            events.append(f"CART_BUILT cart_id={cart_id} total=₹{cart.grand_total}")
        else:
            cart = live_cart

        verification = self._verifier.verify(contract, cart)
        session.last_verification = {"status": verification.status.value}
        events.append(f"VERIFICATION_{verification.status.value.upper()}")
        is_below_min = bool(cart and cart.items and cart.grand_total < cart.min_order_threshold)
        if verification.status == VerificationStatus.PASS and not is_below_min and getattr(cart, "is_serviceable", True):
            return await self._make_awaiting_confirmation(
                session, contract, cart, prior_recovery_notes, events
            )

        events.append("RECOVERY_STARTED")
        session.conversation_state = ConversationState.RECOVERING

        try:
            available = await self._port.get_go_to_items(effective_address)
        except Exception:
            available = []

        engine = self._recovery or LoopingRecoveryEngine(
            policy_engine=self._policy,
            verifier=self._verifier,
        )
        recovery_result = await engine.run(
            contract=contract,
            cart_id=cart_id,
            commerce_port=self._port,
            available_products=available,
            address_id=effective_address,
            verifier=self._verifier,
        )
        updated_cart = recovery_result.cart
        new_verification = recovery_result.verification
        outcome = recovery_result.outcome or RecoveryOutcome(
            state=recovery_result.state,
            failure_class=FailureClass.UNKNOWN,
            message="Intent verified against live commerce state.",
            attempt_number=recovery_result.attempts,
            can_auto_apply=(recovery_result.state == RecoveryState.RECOVERED),
            remaining_violations=new_verification.violations,
        )

        session.last_verification = {"status": new_verification.status.value}
        session.last_recovery_state = outcome.state.value
        events.append(f"RECOVERY_{outcome.state.value.upper()}")
        events.append(f"POST_RECOVERY_VERIFY_{new_verification.status.value.upper()}")

        if outcome.state == RecoveryState.RECOVERED and new_verification.status == VerificationStatus.PASS:
            recovery_notes = prior_recovery_notes + (
                recovery_result.recovery_notes or [a.reason for a in outcome.recovery_actions]
            )
            return await self._make_awaiting_confirmation(
                session, contract, updated_cart, recovery_notes, events
            )

        if outcome.state == RecoveryState.NEEDS_USER_DECISION:
            return self._handle_needs_decision(session, updated_cart, new_verification, outcome, events)

        reason = (
            new_verification.violations[0].detail
            if new_verification.violations
            else "a constraint could not be satisfied"
        )
        return self._handle_failed(session, reason, events)

    def _handle_needs_decision(
        self,
        session: OrchestratorSession,
        cart: CommerceCart,
        verification: VerificationResult,
        outcome: RecoveryOutcome,
        events: list[str],
    ) -> OrchestratorTurnResult:
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
            session_id=session.session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message=_msg_clarification(question, options),
            clarification_options=options,
            clarification_nonce=session.pending_clarification.nonce,
            events=events,
        )

    async def handle_change_request(self, session_id: str) -> OrchestratorTurnResult:
        """Invalidate checkout approval and return the session to an editable state."""

        async with self._store.lock_for(session_id):
            session = self._store.get(session_id)
            if session is None:
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.FAILED,
                    user_message=_msg_failed("session not found"),
                    events=["SESSION_NOT_FOUND"],
                )
            session.pending_confirmation = None
            session.conversation_state = ConversationState.BUILDING
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.BUILDING,
                user_message="Tell me what you want to change in the basket.",
                events=["CONFIRMATION_CANCELLED"],
            )

    def _handle_failed(
        self,
        session: OrchestratorSession,
        reason: str,
        events: list[str],
    ) -> OrchestratorTurnResult:
        session.conversation_state = ConversationState.FAILED
        self._store.save(session)
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.FAILED,
            user_message=_msg_failed(reason),
            events=events,
        )

    async def handle_choice(
        self,
        session_id: str,
        chosen_spin_id: str,
        clarification_nonce: str,
    ) -> OrchestratorTurnResult:
        """Resolve a NEEDS_DECISION clarification with the user's chosen spin_id."""
        async with self._store.lock_for(session_id):
            return await self._handle_choice_locked(
                session_id=session_id,
                chosen_spin_id=chosen_spin_id,
                clarification_nonce=clarification_nonce,
            )

    async def _handle_choice_locked(
        self,
        *,
        session_id: str,
        chosen_spin_id: str,
        clarification_nonce: str,
    ) -> OrchestratorTurnResult:
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
        if clarification_nonce != pending.nonce:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.NEEDS_DECISION,
                user_message="That choice is stale. Please use the latest options.",
                clarification_options=_candidates_to_options(pending.candidates),
                clarification_nonce=pending.nonce,
                events=["STALE_CHOICE_REJECTED"],
            )
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
                clarification_nonce=pending.nonce,
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
            with self._port.customer_scope(session.customer_id):
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
            if multiple > 0:
                quantity = multiple

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
            with self._port.customer_scope(session.customer_id):
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
            return await self._make_awaiting_confirmation(
                session, contract, cart, [f"Applied your choice: {matching_candidate.name}."], events
            )

        # 7. If chosen option still violates intent (e.g. hard budget or dietary)
        events.append("CHOICE_VIOLATION_DETECTED")
        reason = (
            verification.violations[0].detail if verification.violations else "constraint violation"
        )

        try:
            with self._port.customer_scope(session.customer_id):
                available: list[CommerceProductItem] = await self._port.get_go_to_items(
                    effective_address
                )
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
                clarification_nonce=session.pending_clarification.nonce,
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
        explicit_confirmation: bool = True,
        confirmation_nonce: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Execute checkout after explicit user confirmation (Spec §6, §8.3)."""
        if not explicit_confirmation:
            raise UnconfirmedCheckoutError("Checkout requires explicit user confirmation")

        async with self._store.lock_for(session_id):
            return await self._handle_confirm_locked(
                session_id=session_id,
                payment_method=payment_method,
                address_id=address_id,
                confirmation_nonce=confirmation_nonce,
            )

    async def _handle_confirm_locked(
        self,
        *,
        session_id: str,
        payment_method: str,
        address_id: Optional[str],
        confirmation_nonce: Optional[str],
    ) -> OrchestratorTurnResult:
        session = self._store.get(session_id)
        if session is None:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.FAILED,
                user_message=_msg_failed("session not found"),
                events=["SESSION_NOT_FOUND"],
            )

        if session.conversation_state == ConversationState.ORDERED and session.order_id:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.ORDERED,
                user_message=_msg_ordered(session.order_id, session.order_total),
                order_id=session.order_id,
                order_total=session.order_total,
                events=["CHECKOUT_ALREADY_COMPLETED"],
            )

        if session.conversation_state != ConversationState.AWAITING_CONFIRMATION:
            raise UnconfirmedCheckoutError(
                f"Checkout requires session in AWAITING_CONFIRMATION state, "
                f"current: {session.conversation_state.value}"
            )

        contract = session.intent_contract
        pending = session.pending_confirmation
        if contract is None or pending is None:
            raise UnconfirmedCheckoutError("Checkout requires a current basket approval")
        supplied_nonce = confirmation_nonce or pending.nonce
        if supplied_nonce != pending.nonce or pending.consumed_at is not None or pending.is_expired:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.AWAITING_CONFIRMATION,
                user_message="That confirmation is stale or invalid. Please review the current basket.",
                requires_confirmation=True,
                events=["CONFIRMATION_REJECTED"],
            )
        cart_id = session.cart_id or f"cart-{session_id}"
        effective_address = address_id or session.address_id or f"addr-{session.customer_id}"
        events: list[str] = ["CHECKOUT_INITIATED"]

        try:
            with self._port.customer_scope(session.customer_id):
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

        current_fingerprint = confirmation_fingerprint(
            cart,
            contract,
            effective_address,
            pending.payment_method,
            pending.payment_option_id,
        )
        if current_fingerprint != pending.fingerprint:
            return await self._make_awaiting_confirmation(
                session,
                contract,
                cart,
                ["The basket changed after it was shown; please review it again."],
                events + ["CONFIRMATION_INVALIDATED_BASKET_CHANGED"],
            )

        if payment_method != pending.payment_method:
            return await self._make_awaiting_confirmation(
                session,
                contract,
                cart,
                ["Payment method changed; review the basket and payment choice again."],
                events + ["CONFIRMATION_INVALIDATED_PAYMENT_CHANGED"],
                preferred_payment_method=payment_method,
            )

        if contract is not None:
            pre_check = self._verifier.verify_checkout(
                contract=contract,
                cart=cart,
                explicit_confirmation=True,
            )
            events.append(f"PRE_CHECKOUT_VERIFY_{pre_check.status.value.upper()}")
            if pre_check.status != VerificationStatus.PASS:
                session.pending_confirmation = None
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

        pending.consumed_at = datetime.now(timezone.utc)
        self._store.save(session)

        try:
            with self._port.customer_scope(session.customer_id):
                order = await self._port.checkout(
                    cart_id=cart_id,
                    payment_method=pending.payment_method,
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

        session.pending_confirmation = None
        return self._apply_order_result(session, order, events)

    async def handle_payment_status(self, session_id: str) -> OrchestratorTurnResult:
        """Observe and advance a pending payment without tight-loop polling."""

        async with self._store.lock_for(session_id):
            session = self._store.get(session_id)
            if session is None:
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.FAILED,
                    user_message=_msg_failed("session not found"),
                    events=["SESSION_NOT_FOUND"],
                )
            if (
                session.conversation_state != ConversationState.PAYMENT_PENDING
                or not session.payment_paas_id
            ):
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=session.conversation_state,
                    user_message="There is no pending payment to check.",
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=session.payment_status,
                    events=["NO_PENDING_PAYMENT"],
                )

            with self._port.customer_scope(session.customer_id):
                payment = await self._port.check_payment_status(
                    session.payment_paas_id,
                    session.order_id,
                )
            session.payment_status = payment.normalized_status
            events = [f"PAYMENT_STATUS_{payment.normalized_status}"]

            if payment.normalized_status == "PAYMENT_PENDING":
                self._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.PAYMENT_PENDING,
                    user_message=_msg_payment_pending(session.order_id, session.payment_url),
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=payment.normalized_status,
                    payment_url=session.payment_url,
                    events=events,
                )
            if payment.normalized_status == "PAYMENT_FAILED":
                session.conversation_state = ConversationState.PAYMENT_FAILED
                self._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.PAYMENT_FAILED,
                    user_message="Payment failed or was cancelled. No successful order is being reported.",
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=payment.normalized_status,
                    events=events,
                )
            if payment.normalized_status != "PAYMENT_CONFIRMED" or not session.order_id:
                session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
                self._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                    user_message="Payment or order status is unknown. I will not retry checkout or claim success.",
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=payment.normalized_status,
                    events=events,
                )

            if payment.confirmed:
                session.conversation_state = ConversationState.ORDERED
                self._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.ORDERED,
                    user_message=_msg_ordered(session.order_id, session.order_total),
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=payment.normalized_status,
                    events=events + ["ORDER_CONFIRMED_BY_PAYMENT_STATUS"],
                )

            with self._port.customer_scope(session.customer_id):
                order = await self._port.confirm_order(
                    session.order_id, session.payment_paas_id
                )
            return self._apply_order_result(session, order, events + ["ORDER_CONFIRM_ATTEMPTED"])

    async def handle_order_details(self, session_id: str) -> OrchestratorTurnResult:
        """Read back provider order facts without synthesizing missing fields."""

        session = self._store.get(session_id)
        if session is None or not session.order_id:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=(
                    session.conversation_state if session else ConversationState.FAILED
                ),
                user_message="I do not have an order ID for this session.",
                events=["ORDER_DETAILS_UNAVAILABLE"],
            )
        try:
            with self._port.customer_scope(session.customer_id):
                details = await self._port.get_order_details(session.order_id)
        except CommerceError:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message="Order details are unavailable from the commerce provider right now.",
                order_id=session.order_id,
                order_total=session.order_total,
                events=["ORDER_DETAILS_UNAVAILABLE"],
            )

        facts = [
            f"{item.quantity}× {item.name}"
            for item in details.items
            if item.removed is not True
        ]
        parts = [f"Order {details.order_id}"]
        if details.raw_status:
            parts.append(f"status: {details.raw_status}")
        if facts:
            parts.append("items: " + ", ".join(facts))
        if details.total_bill is not None:
            parts.append(f"total: ₹{details.total_bill:,.0f}")
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=session.conversation_state,
            user_message=". ".join(parts) + ".",
            order_id=details.order_id,
            order_total=details.total_bill,
            events=["ORDER_DETAILS_READ"],
        )

    async def handle_delivery_status(self, session_id: str) -> OrchestratorTurnResult:
        """Read one structured provider delivery observation at user request."""

        session = self._store.get(session_id)
        if session is None or not session.order_id or not session.address_id:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=(
                    session.conversation_state if session else ConversationState.FAILED
                ),
                user_message="I do not have enough provider order data to check delivery.",
                events=["DELIVERY_STATUS_UNAVAILABLE"],
            )
        try:
            with self._port.customer_scope(session.customer_id):
                delivery = await self._port.get_delivery_status(
                    session.order_id, session.address_id
                )
        except CommerceError:
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message="Delivery status is unavailable from the commerce provider right now.",
                order_id=session.order_id,
                order_total=session.order_total,
                events=["DELIVERY_STATUS_UNAVAILABLE"],
            )

        facts = [delivery.status_text, delivery.eta_text]
        known = [fact for fact in facts if fact]
        message = (
            f"Order {delivery.order_id}: " + ". ".join(known) + "."
            if known
            else f"Order {delivery.order_id} has no new delivery status available."
        )
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=session.conversation_state,
            user_message=message,
            order_id=delivery.order_id,
            order_total=session.order_total,
            events=["DELIVERY_STATUS_READ"],
        )

    def _apply_order_result(
        self,
        session: OrchestratorSession,
        order: CommerceOrderResult,
        events: list[str],
    ) -> OrchestratorTurnResult:
        """Map a normalized provider result without collapsing uncertain states."""

        session.order_id = order.order_id
        session.order_total = order.grand_total
        session.payment_status = order.status
        session.payment_paas_id = order.paas_id
        session.payment_transaction_id = order.transaction_id
        session.payment_url = order.bridge_url or order.upi_intent_url
        session.payment_polling_interval_ms = order.polling_interval_ms
        session.payment_max_time_ms = order.max_time_to_poll_ms
        session.child_orders = [child.model_dump(mode="json") for child in order.orders]

        if order.status == "PAYMENT_PENDING":
            session.conversation_state = ConversationState.PAYMENT_PENDING
            message = _msg_payment_pending(order.order_id, session.payment_url)
            events.append("PAYMENT_PENDING")
        elif order.status == "PARTIAL_ORDER":
            session.conversation_state = ConversationState.PARTIAL_ORDER
            message = "Only part of the order was placed. Review the individual order results before continuing."
            events.append("CHECKOUT_PARTIAL")
        elif order.status == "ORDER_PLACED" and order.order_id:
            session.conversation_state = ConversationState.ORDERED
            message = _msg_ordered(order.order_id, order.grand_total)
            events.append(f"CHECKOUT_SUCCEEDED order_id={order.order_id}")
        elif order.status == "FAILED":
            session.conversation_state = ConversationState.PAYMENT_FAILED
            message = "Checkout failed. No successful order is being reported."
            events.append("CHECKOUT_FAILED")
        else:
            session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
            message = "The checkout outcome is unknown. I will not retry or claim that an order was placed."
            events.append("CHECKOUT_STATE_UNKNOWN")

        self._store.save(session)
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=session.conversation_state,
            user_message=message,
            order_id=order.order_id,
            order_total=order.grand_total,
            payment_status=session.payment_status,
            payment_url=session.payment_url,
            child_orders=order.orders,
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

    async def _make_awaiting_confirmation(
        self,
        session: OrchestratorSession,
        contract: IntentContract,
        cart: Any,
        recovery_notes: list[str],
        events: list[str],
        *,
        preferred_payment_method: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Transition to AWAITING_CONFIRMATION and return the full result."""
        address_id = session.address_id or cart.address_id
        try:
            with self._port.customer_scope(session.customer_id):
                payment_options = [
                    option
                    for option in await self._port.get_payment_options(
                        cart_id=cart.cart_id,
                        address_id=address_id,
                    )
                    if option.is_available
                ]
        except Exception:
            payment_options = []

        if not payment_options:
            return self._handle_failed(
                session,
                "no payment option is currently available",
                events + ["PAYMENT_OPTIONS_UNAVAILABLE"],
            )

        selected = payment_options[0]
        if preferred_payment_method is not None:
            requested = preferred_payment_method.casefold()
            matching = next(
                (
                    option
                    for option in payment_options
                    if option.method.casefold() == requested
                    or (option.id is not None and option.id.casefold() == requested)
                ),
                None,
            )
            if matching is None:
                return self._handle_failed(
                    session,
                    "the requested payment method is not available",
                    events + ["PAYMENT_METHOD_UNAVAILABLE"],
                )
            selected = matching

        snapshot = create_confirmation_snapshot(
            cart,
            contract,
            address_id,
            selected.method,
            selected.id,
        )
        session.pending_confirmation = snapshot
        session.conversation_state = ConversationState.AWAITING_CONFIRMATION
        self._store.save(session)

        basket = _build_basket_summary(
            cart,
            contract,
            recovery_notes,
            confirmation_nonce=snapshot.nonce,
            confirmation_expires_at=snapshot.expires_at,
            payment_options=payment_options,
            selected_payment_method=selected.method,
            selected_payment_option_id=selected.id,
        )
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


def _is_incremental_add(message: str) -> bool:
    lower = message.lower().strip()
    return lower.startswith(("add", "also add", "plus", "and add", "include"))


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

