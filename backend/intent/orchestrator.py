"""GrocerOrchestrator — end-to-end conversational commerce loop (Spec Section 12, Section 20 Phase 6).

Connects:
    IntentParser → PolicyEngine → CommercePort → IntentVerifier → RecoveryEngine

Architecture rule (Spec Section 12.3):
    LLM interprets and proposes. Deterministic code enforces and verifies.
    All state transitions in this module are deterministic.

Entry points:
    handle_turn()    — main message handler: parse → build → verify → recover
    handle_choice()  — resolve a NEEDS_DECISION clarification
    handle_confirm() — explicit checkout confirmation (AWAITING_CONFIRMATION → ORDERED)
"""
from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceOrderResult,
    CommerceProductItem,
    DeliveryAddress,
    OrderChildResult,
    PaymentOption,
)
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.exceptions import (
    CommerceError,
    OrderStateUnknownError,
    ProviderAuthError,
    ProviderSessionRevokedError,
    UnconfirmedCheckoutError,
    UpstreamTimeoutError,
)

from backend.intent.enums import PreferenceType
from backend.intent.models import IntentContract, IntentItem, ResolvedMeaning
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
    PendingAddressChoice,
    PendingClarification,
    PendingPaymentChoice,
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
    payment_options: list[PaymentOption] = Field(default_factory=list)
    payment_choice_nonce: Optional[str] = None
    address_options: Optional[list[DeliveryAddress]] = None
    requires_confirmation: bool = False
    order_id: Optional[str] = None
    order_total: Optional[float] = None
    payment_status: Optional[str] = None
    payment_url: Optional[str] = None
    child_orders: list[OrderChildResult] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage helpers & re-exports (Spec Section 11 & Section 12)
# Delegated to backend.intent.stages modular architecture
# ---------------------------------------------------------------------------

from backend.intent.stages import (
    AddressStageManager,
    default_address_manager,
    _msg_confirmation_basket,
    _display_address,
    _msg_clarification,
    _msg_failed,
    _msg_ordered,
    _msg_payment_pending,
    _detect_swap_request,
    _detect_removal_request,
    _is_fresh_request,
    _is_incremental_add,
    _merge_contracts,
    _targeted_recovery_query,
    _search_and_pick,
    _resolve_items,
    _build_basket_summary,
    _candidates_to_options,
    _group_payment_options,
    _payment_option_key,
    _msg_payment_choice,
    format_delivery_status,
    format_order_cancellation_redirect,
)



# ---------------------------------------------------------------------------
# GrocerOrchestrator
# ---------------------------------------------------------------------------

class GrocerOrchestrator:
    """Stateless conversational commerce orchestrator (Spec Section 12, Phase 6).

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
        self._customer_addresses: dict[str, str] = {}
        self._customer_payment_preferences: dict[str, str] = {}

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
        session = self._store.get_or_create(session_id, customer_id)
        session.pending_confirmation = None
        session.turn_count += 1
        events: list[str] = []

        if session.conversation_state == ConversationState.NEEDS_DECISION and session.pending_address_choice:
            if not _is_fresh_request(message):
                return await self.handle_address_choice(session_id, address_id or message)

        # 0. Check if message is a conversational greeting BEFORE triggering commerce flow
        temp_contract = self._parser.parse(message, session_id=session.session_id)
        if temp_contract.is_greeting:
            session.conversation_state = ConversationState.READY
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session.session_id,
                conversation_state=ConversationState.READY,
                user_message=(
                    "Hi! I'm Grocer, your WhatsApp grocery assistant. "
                    "Tell me what you need, like '1L milk and brown bread under ₹200' or 'get my weekly groceries'."
                ),
                events=events + ["GREETING_HANDLED"],
            )

        if not session.address_id and customer_id in self._customer_addresses:
            session.address_id = self._customer_addresses[customer_id]

        from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter

        is_swiggy = isinstance(self._port, SwiggyMCPAdapter)
        swiggy_addresses: list[DeliveryAddress] = []
        if is_swiggy:
            try:
                swiggy_addresses = await self._port.get_addresses(customer_id)
            except Exception as exc:
                return self._provider_failure_result(session, exc, events)

            if not swiggy_addresses:
                session.pending_address_choice = None
                session.conversation_state = ConversationState.FAILED
                self._store.save(session)
                return OrchestratorTurnResult(
                    session_id=session.session_id,
                    conversation_state=ConversationState.FAILED,
                    user_message=(
                        "No delivery address found for your Swiggy account. "
                        "Please add an address in Swiggy first."
                    ),
                    events=events + ["NO_ADDRESS_FOUND"],
                )

        addr_id, addr_disp, is_conf = AddressStageManager.resolve_session_address(
            customer_id=customer_id,
            explicit_address_id=address_id,
            session_address_id=session.address_id,
            swiggy_addresses=swiggy_addresses,
        )
        session.address_id = addr_id
        session.address_display = addr_disp
        if is_conf:
            session.address_confirmed = True
        effective_address = addr_id


        session.conversation_state = ConversationState.BUILDING
        cart_id = session.cart_id or f"cart-{session_id}"
        session.cart_id = cart_id

        prior_recovery_notes: list[str] = []
        live_cart: Optional[CommerceCart] = None
        new_contract_items: list[IntentItem] = []

        # 1. Inspect live commerce cart for drift against prior intent contract, swaps, or removals
        prior_contract = session.intent_contract
        swap_req = _detect_swap_request(message)
        removal_req = _detect_removal_request(message)

        if session.cart_id and not _is_fresh_request(message):
            cart_fetch_error: Optional[Exception] = None
            try:
                live_cart = await self._port.get_cart(cart_id)
            except Exception as exc:
                live_cart = None
                cart_fetch_error = exc

            # Fast-path 1.1: Conversational item swap ("make it jim jam", "replace biscuits with jim jam")
            if swap_req and live_cart and live_cart.items:
                events.append("ITEM_SWAP_REQUESTED")
                old_hint, new_hint = swap_req
                temp_item = IntentItem(name=new_hint, quantity=1.0, unit="units")
                try:
                    replacement_update = await _search_and_pick(self._port, effective_address, temp_item)
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)

                if not replacement_update:
                    return OrchestratorTurnResult(
                        session_id=session.session_id,
                        conversation_state=session.conversation_state,
                        user_message=f"I couldn't find '{new_hint}' in stock at your store.",
                        events=events + ["SWAP_ITEM_NOT_FOUND"],
                    )

                target_old: Optional[CartItem] = None
                if old_hint:
                    target_old = next(
                        (
                            ci
                            for ci in live_cart.items
                            if old_hint.lower() in ci.name.lower() or ci.name.lower() in old_hint.lower()
                        ),
                        None,
                    )
                if not target_old:
                    new_tokens = set(re.findall(r"\w+", new_hint.lower()))
                    scored = []
                    for ci in live_cart.items:
                        ci_tokens = set(re.findall(r"\w+", ci.name.lower()))
                        overlap = len(new_tokens & ci_tokens)
                        scored.append((overlap, ci))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    if scored and scored[0][0] > 0:
                        target_old = scored[0][1]
                    else:
                        target_old = live_cart.items[0]

                replacement_update.quantity = target_old.quantity

                updated_updates = [
                    CartItemUpdate(spin_id=ci.spin_id, sku_id=ci.sku_id, quantity=ci.quantity)
                    for ci in live_cart.items
                    if ci.spin_id != target_old.spin_id
                ]
                updated_updates.append(CartItemUpdate(spin_id=target_old.spin_id, sku_id=target_old.sku_id, quantity=0))
                updated_updates.append(replacement_update)

                try:
                    cart = await self._port.update_cart(
                        items=updated_updates, cart_id=cart_id, address_id=effective_address
                    )
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)

                contract = session.intent_contract or IntentContract(session_id=session_id, goal="grocery order")
                new_items = []
                replaced = False
                for it in contract.items:
                    if not replaced and (
                        target_old.name.lower() in it.name.lower()
                        or it.name.lower() in target_old.name.lower()
                        or it.name.lower() == (old_hint or "").lower()
                    ):
                        new_items.append(IntentItem(name=new_hint, quantity=replacement_update.quantity, unit=it.unit))
                        replaced = True
                    else:
                        new_items.append(it)
                if not replaced:
                    new_items.append(IntentItem(name=new_hint, quantity=replacement_update.quantity, unit="units"))
                contract.items = new_items
                session.intent_contract = contract
                default_intent_store.save(contract)
                self._store.save(session)

                return await self._make_awaiting_confirmation(
                    session, contract, cart, prior_recovery_notes, events + [f"ITEM_SWAPPED old={target_old.name!r} new={replacement_update.spin_id}"]
                )

            # Fast-path 1.2: Conversational item removal ("remove milk", "drop biscuits")
            if removal_req and live_cart and live_cart.items:
                events.append("ITEM_REMOVAL_REQUESTED")
                target_hint = removal_req
                target_old = None
                if target_hint.isdigit():
                    idx = int(target_hint) - 1
                    if 0 <= idx < len(live_cart.items):
                        target_old = live_cart.items[idx]
                else:
                    target_old = next(
                        (
                            ci
                            for ci in live_cart.items
                            if target_hint.lower() in ci.name.lower() or ci.name.lower() in target_hint.lower()
                        ),
                        None,
                    )
                if not target_old:
                    return OrchestratorTurnResult(
                        session_id=session.session_id,
                        conversation_state=session.conversation_state,
                        user_message=f"I couldn't find '{target_hint}' in your basket.",
                        events=events + ["REMOVE_ITEM_NOT_FOUND"],
                    )

                updated_updates = [
                    CartItemUpdate(spin_id=ci.spin_id, sku_id=ci.sku_id, quantity=ci.quantity)
                    for ci in live_cart.items
                    if ci.spin_id != target_old.spin_id
                ]
                updated_updates.append(CartItemUpdate(spin_id=target_old.spin_id, sku_id=target_old.sku_id, quantity=0))

                try:
                    cart = await self._port.update_cart(
                        items=updated_updates, cart_id=cart_id, address_id=effective_address
                    )
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)

                contract = session.intent_contract or IntentContract(session_id=session_id, goal="grocery order")
                contract.items = [
                    it for it in contract.items
                    if not (target_old.name.lower() in it.name.lower() or it.name.lower() in target_old.name.lower())
                ]
                session.intent_contract = contract
                default_intent_store.save(contract)
                self._store.save(session)

                if not cart.items:
                    session.conversation_state = ConversationState.READY
                    self._store.save(session)
                    return OrchestratorTurnResult(
                        session_id=session.session_id,
                        conversation_state=ConversationState.READY,
                        user_message="I've removed that item. Your basket is now empty. What would you like to add?",
                        events=events + ["ITEM_REMOVED_CART_EMPTY"],
                    )

                return await self._make_awaiting_confirmation(
                    session, contract, cart, prior_recovery_notes, events + [f"ITEM_REMOVED name={target_old.name!r}"]
                )

            # Normal recovery check for drift
            drift = self._verifier.verify(prior_contract, live_cart) if (prior_contract and live_cart) else None
            needs_recovery = False

            if cart_fetch_error is not None:
                needs_recovery = True
            elif live_cart and session.turn_count > 1 and prior_contract:
                is_below_min = bool(live_cart.items and live_cart.grand_total < live_cart.min_order_threshold)
                if (
                    (drift and drift.status != VerificationStatus.PASS)
                    or live_cart.is_serviceable is False
                    or is_below_min
                ):
                    needs_recovery = True

            if needs_recovery:
                events.append("RECOVERY_STARTED")
                session.conversation_state = ConversationState.RECOVERING
                try:
                    available = await self._port.search_products(
                        effective_address,
                        _targeted_recovery_query(prior_contract, drift),
                    )
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)
                engine = self._recovery or LoopingRecoveryEngine(
                    policy_engine=self._policy,
                    verifier=self._verifier,
                )
                try:
                    rec_result = await engine.run(
                        contract=prior_contract,
                        cart_id=cart_id,
                        commerce_port=self._port,
                        available_products=available,
                        address_id=effective_address,
                        verifier=self._verifier,
                    )
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)
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
                CartItemUpdate(spin_id=ci.spin_id, sku_id=ci.sku_id, quantity=ci.quantity)
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
                temp_contract = IntentContract(
                    session_id=session.session_id,
                    goal=contract.goal or "incremental items",
                    items=new_contract_items,
                )
                try:
                    new_updates = await _resolve_items(
                        self._port, temp_contract, effective_address, events
                    )
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)
                resolved_items = existing_updates + new_updates
            else:
                resolved_items = existing_updates
        else:
            try:
                resolved_items = await _resolve_items(
                    self._port, contract, effective_address, events
                )
            except Exception as exc:
                return self._provider_failure_result(session, exc, events)

        # First, apply whatever we successfully resolved
        if resolved_items and (not live_cart or not live_cart.items or new_contract_items):
            try:
                cart = await self._port.update_cart(
                    items=resolved_items, cart_id=cart_id, address_id=effective_address
                )
            except Exception as exc:
                return self._handle_failed(session, str(exc), events)
            events.append(f"CART_BUILT cart_id={cart_id} total=₹{cart.grand_total}")
        else:
            cart = live_cart

        # Second, check for any ambiguities that need clarification
        ambiguity_item = next(
            (
                item
                for item in contract.items
                if item.resolved_meaning is not None
                and item.resolved_meaning.clarification_required
            ),
            None,
        )
        
        if ambiguity_item is not None:
            ambiguity = ambiguity_item.resolved_meaning
            session.conversation_state = ConversationState.NEEDS_DECISION
            
            clarification_options = []
            candidates_for_session = []
            for i, cand in enumerate(ambiguity.candidates[:10], 1):
                opt = ClarificationOption(
                    index=i,
                    spin_id=cand["spin_id"],
                    name=cand["name"],
                    pack_size=cand["pack_size"],
                    price=cand["price"],
                    brand=cand.get("brand")
                )
                clarification_options.append(opt)
                candidates_for_session.append(RecoveryCandidate(
                    spin_id=cand["spin_id"],
                    sku_id=cand.get("sku_id"),
                    name=cand["name"],
                    pack_size=cand["pack_size"],
                    price=cand["price"],
                ))
                
            session.pending_clarification = PendingClarification(
                item_name=ambiguity_item.name,
                clarification_question=ambiguity.explanation,
                candidates=candidates_for_session,
                intended_quantity=int(ambiguity_item.quantity)
            )
            
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session.session_id,
                conversation_state=ConversationState.NEEDS_DECISION,
                user_message=ambiguity.explanation,
                clarification_options=clarification_options,
                clarification_nonce=session.pending_clarification.nonce,
                events=events + ["QUANTITY_CLARIFICATION_REQUIRED"],
            )

        if not resolved_items:
            return self._handle_failed(session, "no matching products found for your request", events)

        verification = self._verifier.verify(contract, cart)
        session.last_verification = {"status": verification.status.value}
        events.append(f"VERIFICATION_{verification.status.value.upper()}")
        is_below_min = bool(cart and cart.items and cart.grand_total < cart.min_order_threshold)
        if (
            verification.status == VerificationStatus.PASS
            and not is_below_min
            and getattr(cart, "is_serviceable", None) is not False
        ):
            return await self._advance_after_cart_built(
                session, contract, cart, prior_recovery_notes, events
            )

        events.append("RECOVERY_STARTED")
        session.conversation_state = ConversationState.RECOVERING

        try:
            available = await self._port.search_products(
                effective_address,
                _targeted_recovery_query(contract, verification),
            )
        except Exception as exc:
            return self._provider_failure_result(session, exc, events)

        engine = self._recovery or LoopingRecoveryEngine(
            policy_engine=self._policy,
            verifier=self._verifier,
        )
        try:
            recovery_result = await engine.run(
                contract=contract,
                cart_id=cart_id,
                commerce_port=self._port,
                available_products=available,
                address_id=effective_address,
                verifier=self._verifier,
            )
        except Exception as exc:
            return self._provider_failure_result(session, exc, events)
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
            return await self._advance_after_cart_built(
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
            session.pending_payment_choice = None
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

    def _provider_failure_result(
        self,
        session: OrchestratorSession,
        error: Exception,
        events: list[str],
    ) -> OrchestratorTurnResult:
        """Return a safe, truthful state without collapsing provider failures into emptiness."""

        if isinstance(error, ProviderSessionRevokedError):
            event = "PROVIDER_SESSION_REVOKED"
            reason = (
                "your Swiggy session was revoked and must be reconnected before continuing"
            )
        elif isinstance(error, ProviderAuthError):
            event = "PROVIDER_REAUTH_REQUIRED"
            reason = "your Swiggy connection must be reauthenticated before continuing"
        elif isinstance(
            error,
            (UpstreamTimeoutError, CommerceError, TimeoutError, ConnectionError, OSError),
        ):
            event = "PROVIDER_TEMPORARILY_UNAVAILABLE"
            reason = "the commerce provider is temporarily unavailable"
        else:
            event = "PROVIDER_TEMPORARILY_UNAVAILABLE"
            reason = "the commerce provider could not complete the request"
        return self._handle_failed(session, reason, events + [event])

    def _payment_choice_result(
        self,
        session: OrchestratorSession,
        options: list[PaymentOption],
        recovery_notes: list[str],
        events: list[str],
        *,
        pending: Optional[PendingPaymentChoice] = None,
    ) -> OrchestratorTurnResult:
        """Persist and render a live provider payment choice without preselecting."""

        grouped = _group_payment_options(options)
        payment_choice = pending or PendingPaymentChoice(
            options=grouped,
            raw_options=options,
            recovery_notes=recovery_notes,
        )
        session.pending_confirmation = None
        session.pending_payment_choice = payment_choice
        session.conversation_state = ConversationState.NEEDS_DECISION
        self._store.save(session)
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message=_msg_payment_choice(payment_choice.options),
            payment_options=payment_choice.options,
            payment_choice_nonce=payment_choice.nonce,
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
        session.cart_id = cart_id

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
        chosen_sku_id = matching_candidate.sku_id
        if not chosen_sku_id:
            try:
                with self._port.customer_scope(session.customer_id):
                    search_query = matching_candidate.name or pending.item_name
                    prods = await self._port.search_products(effective_address, search_query)
                    for p in prods:
                        for v in p.variants:
                            if v.spin_id == chosen_spin_id and v.sku_id:
                                chosen_sku_id = v.sku_id
                                break
                        if chosen_sku_id:
                            break
            except Exception:
                pass

        for ci in current_cart.items:
            if removes_spin_id and ci.spin_id == removes_spin_id:
                updates.append(CartItemUpdate(spin_id=chosen_spin_id, sku_id=chosen_sku_id, quantity=quantity))
                replaced = True
            else:
                updates.append(CartItemUpdate(spin_id=ci.spin_id, sku_id=ci.sku_id, quantity=ci.quantity))

        if not replaced:
            updates.append(CartItemUpdate(spin_id=chosen_spin_id, sku_id=chosen_sku_id, quantity=quantity))

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

        if intent_item and intent_item.resolved_meaning:
            intent_item.resolved_meaning.status = "EXACT"
            intent_item.resolved_meaning.spin_id = chosen_spin_id
            intent_item.resolved_meaning.provider_pack_description = matching_candidate.pack_size
            intent_item.resolved_meaning.cart_quantity = quantity
            intent_item.resolved_meaning.clarification_required = False
            intent_item.resolved_meaning.explanation = f"User explicitly chose {matching_candidate.name} ({matching_candidate.pack_size})"

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
                available: list[CommerceProductItem] = await self._port.search_products(
                    effective_address,
                    _targeted_recovery_query(contract, verification),
                )
        except Exception as exc:
            return self._provider_failure_result(session, exc, events)

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

    async def handle_payment_choice(
        self,
        session_id: str,
        payment_option_id: str,
        payment_choice_nonce: Optional[str],
    ) -> OrchestratorTurnResult:
        """Bind an exact live provider payment option before basket confirmation."""

        async with self._store.lock_for(session_id):
            session = self._store.get(session_id)
            if session is None:
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.FAILED,
                    user_message=_msg_failed("session not found"),
                    events=["SESSION_NOT_FOUND"],
                )

            pending = session.pending_payment_choice
            if (
                session.conversation_state != ConversationState.NEEDS_DECISION
                or pending is None
            ):
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=session.conversation_state,
                    user_message="There is no pending payment choice.",
                    events=["NO_PENDING_PAYMENT_CHOICE"],
                )
            if payment_choice_nonce != pending.nonce:
                return self._payment_choice_result(
                    session,
                    pending.options,
                    pending.recovery_notes,
                    ["STALE_PAYMENT_CHOICE_REJECTED"],
                    pending=pending,
                )

            all_candidates = list(pending.options) + list(getattr(pending, "raw_options", []))
            selected = next(
                (
                    option
                    for option in all_candidates
                    if _payment_option_key(option) == payment_option_id
                    or option.method.casefold() == payment_option_id.casefold()
                    or (option.id and option.id.casefold() == payment_option_id.casefold())
                    or payment_option_id.casefold() in option.label.casefold()
                ),
                None,
            )
            if selected is None:
                return self._payment_choice_result(
                    session,
                    pending.options,
                    pending.recovery_notes,
                    ["PAYMENT_CHOICE_REJECTED"],
                    pending=pending,
                )

            self._customer_payment_preferences[session.customer_id] = selected.id or selected.method
            session.selected_payment_method = selected.method
            session.selected_payment_option_id = selected.id
            session.selected_payment_option_kind = selected.kind
            session.selected_payment_option_label = selected.label

            contract = session.intent_contract
            if contract is None:
                return self._handle_failed(
                    session,
                    "no active intent contract",
                    ["PAYMENT_CHOICE_REJECTED"],
                )
            cart_id = session.cart_id or f"cart-{session_id}"
            try:
                with self._port.customer_scope(session.customer_id):
                    cart = await self._port.get_cart(cart_id)
            except Exception as exc:
                return self._provider_failure_result(session, exc, [])

            return await self._make_awaiting_confirmation(
                session,
                contract,
                cart,
                pending.recovery_notes,
                [f"PAYMENT_OPTION_SELECTED id={payment_option_id}"],
                preferred_payment_option_id=payment_option_id,
            )

    async def handle_confirm(
        self,
        session_id: str,
        payment_method: str = "UPI",
        address_id: Optional[str] = None,
        explicit_confirmation: bool = False,
        confirmation_nonce: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Execute checkout after explicit user confirmation (Spec Section 6, Section 8.3)."""
        if not explicit_confirmation or confirmation_nonce is None:
            raise UnconfirmedCheckoutError(
                "Checkout requires explicit confirmation bound to the presented basket"
            )

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
        if confirmation_nonce != pending.nonce or pending.consumed_at is not None or pending.is_expired:
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
            pending.payment_option_kind,
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

        import os
        demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("true", "1")
        
        try:
            if demo_mode:
                order = CommerceOrderResult(
                    order_id="demo_order_123",
                    status="ORDER_PLACED",
                    raw_status="success",
                    success=True,
                    grand_total=1.0,
                    provider_message="✅ Your order is ready. Demo mode: order not actually placed on Swiggy."
                )
                events.append("DEMO_CHECKOUT_SIMULATED")
            else:
                with self._port.customer_scope(session.customer_id):
                    order = await self._port.checkout(
                        cart_id=cart_id,
                        payment_method=pending.payment_method,
                        explicit_confirmation=True,
                        address_id=effective_address,
                        payment_option_id=pending.payment_option_id,
                        payment_option_kind=pending.payment_option_kind,
                    )
        except UnconfirmedCheckoutError:
            raise
        except OrderStateUnknownError:
            session.pending_confirmation = None
            session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
            self._store.save(session)
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                user_message="The checkout outcome is unknown. I will not retry or claim that an order was placed.",
                events=events + ["CHECKOUT_STATE_UNKNOWN"],
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

            now = datetime.now(timezone.utc)
            if session.payment_poll_deadline and now >= session.payment_poll_deadline:
                events = ["PAYMENT_POLL_CAP_CONFIRM_ATTEMPTED"]
                session.payment_poll_deadline = None
                if not session.order_id:
                    session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
                    self._store.save(session)
                    return OrchestratorTurnResult(
                        session_id=session_id,
                        conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                        user_message=(
                            "The payment polling window ended without enough provider "
                            "data to finalize. I will not retry checkout or claim success."
                        ),
                        order_total=session.order_total,
                        payment_status=session.payment_status,
                        events=events + ["PAYMENT_POLL_CAP_CONFIRM_UNKNOWN"],
                    )
                try:
                    with self._port.customer_scope(session.customer_id):
                        order = await self._port.confirm_order(
                            session.order_id,
                            session.payment_paas_id,
                        )
                except Exception:
                    session.conversation_state = ConversationState.ORDER_STATE_UNKNOWN
                    self._store.save(session)
                    return OrchestratorTurnResult(
                        session_id=session_id,
                        conversation_state=ConversationState.ORDER_STATE_UNKNOWN,
                        user_message=(
                            "The payment finalization outcome is unknown. I will not "
                            "retry checkout or claim success."
                        ),
                        order_id=session.order_id,
                        order_total=session.order_total,
                        payment_status=session.payment_status,
                        events=events + ["PAYMENT_POLL_CAP_CONFIRM_UNKNOWN"],
                    )
                return self._apply_order_result(session, order, events)
            if session.payment_next_poll_at and now < session.payment_next_poll_at:
                return OrchestratorTurnResult(
                    session_id=session_id,
                    conversation_state=ConversationState.PAYMENT_PENDING,
                    user_message=_msg_payment_pending(session.order_id, session.payment_url),
                    order_id=session.order_id,
                    order_total=session.order_total,
                    payment_status=session.payment_status,
                    payment_url=session.payment_url,
                    events=["PAYMENT_POLL_DEFERRED"],
                )

            with self._port.customer_scope(session.customer_id):
                payment = await self._port.check_payment_status(
                    session.payment_paas_id,
                    session.order_id,
                )
            session.payment_status = payment.normalized_status
            if payment.order_id:
                session.order_id = payment.order_id
            events = [f"PAYMENT_STATUS_{payment.normalized_status}"]

            if payment.normalized_status == "PAYMENT_PENDING":
                if session.payment_polling_interval_ms:
                    session.payment_next_poll_at = now + timedelta(
                        milliseconds=session.payment_polling_interval_ms
                    )
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
        """Prefer rich conversational tracking, with a coordinate-safe ETA fallback."""

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

        if (
            session.delivery_latitude is not None
            and session.delivery_longitude is not None
        ):
            try:
                with self._port.customer_scope(session.customer_id):
                    tracking = await self._port.track_order(
                        session.order_id,
                        lat=session.delivery_latitude,
                        lng=session.delivery_longitude,
                    )
            except Exception as exc:
                return self._provider_failure_result(session, exc, [])

            facts: list[str] = []
            if tracking.raw_status:
                facts.append(tracking.raw_status)
            if (
                tracking.status_message
                and tracking.status_message != tracking.raw_status
            ):
                facts.append(tracking.status_message)
            if tracking.sub_status_message:
                facts.append(tracking.sub_status_message)
            eta = tracking.eta_text
            if not eta and tracking.eta_minutes is not None:
                eta = f"ETA {tracking.eta_minutes} minutes"
            if eta:
                facts.append(eta)
            if tracking.store_name:
                store = tracking.store_name
                if tracking.store_address:
                    store += f" ({tracking.store_address})"
                facts.append(f"Store: {store}")
            if tracking.delivery_address:
                label = (
                    f"{tracking.delivery_address_label}: "
                    if tracking.delivery_address_label
                    else ""
                )
                facts.append(f"Delivery: {label}{tracking.delivery_address}")
            if tracking.rider_location:
                facts.append(
                    "Rider location: "
                    f"{tracking.rider_location.latitude:.5f}, "
                    f"{tracking.rider_location.longitude:.5f}"
                )
            if tracking.items:
                facts.append(
                    "Items: "
                    + ", ".join(
                        f"{item.quantity}× {item.name}" for item in tracking.items
                    )
                )
            if tracking.payment_message:
                payment = tracking.payment_message
                if tracking.payment_amount:
                    payment += f" ({tracking.payment_amount})"
                facts.append(f"Payment: {payment}")
            message = (
                f"Order {tracking.order_id}: " + ". ".join(facts) + "."
                if facts
                else f"Order {tracking.order_id} has no new tracking status available."
            )
            return OrchestratorTurnResult(
                session_id=session_id,
                conversation_state=session.conversation_state,
                user_message=message,
                order_id=tracking.order_id,
                order_total=session.order_total,
                events=["ORDER_TRACKING_READ"],
            )

        try:
            with self._port.customer_scope(session.customer_id):
                delivery = await self._port.get_delivery_status(
                    session.order_id, session.address_id
                )
        except Exception as exc:
            return self._provider_failure_result(session, exc, [])

        facts = [delivery.status_text, delivery.eta_text]
        known = [fact for fact in facts if fact]
        fallback_note = (
            "Detailed rider tracking is unavailable because Swiggy has not returned "
            "delivery coordinates."
        )
        message = fallback_note
        if known:
            message += f" Order {delivery.order_id}: " + ". ".join(known) + "."
        else:
            message += f" Order {delivery.order_id} has no new delivery status available."
        return OrchestratorTurnResult(
            session_id=session_id,
            conversation_state=session.conversation_state,
            user_message=message,
            order_id=delivery.order_id,
            order_total=session.order_total,
            events=["ORDER_TRACKING_FALLBACK_DELIVERY_STATUS"],
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
        now = datetime.now(timezone.utc)
        session.payment_next_poll_at = (
            now + timedelta(milliseconds=order.polling_interval_ms)
            if order.polling_interval_ms
            else None
        )
        session.payment_poll_deadline = (
            now + timedelta(milliseconds=order.max_time_to_poll_ms)
            if order.max_time_to_poll_ms
            else None
        )
        if order.delivery_address is not None:
            session.delivery_latitude = order.delivery_address.latitude
            session.delivery_longitude = order.delivery_address.longitude
        session.child_orders = [child.model_dump(mode="json") for child in order.orders]

        if order.status == "PAYMENT_PENDING":
            session.conversation_state = ConversationState.PAYMENT_PENDING
            message = _msg_payment_pending(order.order_id, session.payment_url)
            events.append("PAYMENT_PENDING")
        elif order.status == "PARTIAL_ORDER":
            session.conversation_state = ConversationState.PARTIAL_ORDER
            failed_children = [
                f"{child.order_id or 'unknown store'}: {child.error}"
                for child in order.orders
                if child.status == "FAILED" and child.error
            ]
            detail = f" Failed: {'; '.join(failed_children)}." if failed_children else ""
            message = (
                "Only part of the order was placed. Review the individual order results before continuing."
                + detail
            )
            events.append("CHECKOUT_PARTIAL")
        elif order.status == "ORDER_PLACED" and order.order_id:
            session.conversation_state = ConversationState.ORDERED
            message = order.provider_message or _msg_ordered(order.order_id, order.grand_total)
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
        """Load established soft preferences and apply where not overridden (Spec Section 7)."""
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

    async def _advance_after_cart_built(
        self,
        session: OrchestratorSession,
        contract: IntentContract,
        cart: Any,
        recovery_notes: list[str],
        events: list[str],
    ) -> OrchestratorTurnResult:
        """Route to address selection (Turn 2) if address unconfirmed on Swiggy, else confirmation."""
        from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
        is_swiggy = isinstance(self._port, SwiggyMCPAdapter)

        if is_swiggy and not session.address_confirmed:
            try:
                addresses = await self._port.get_addresses(session.customer_id)
            except Exception as exc:
                return self._provider_failure_result(session, exc, events)

            if addresses:
                session.pending_address_choice = PendingAddressChoice(
                    addresses=addresses,
                    request_message=contract.goal or "grocery order",
                )
                session.conversation_state = ConversationState.NEEDS_DECISION
                events.append("NEEDS_ADDRESS_SELECTION")
                self._store.save(session)

                basket_lines = ["🛒 *Added to your basket:*", ""]
                for it in cart.items:
                    basket_lines.append(f"• {it.quantity} × {it.name} ({it.pack_size}) — ₹{it.total_price:,.0f}")
                basket_lines.append("")
                basket_lines.append(f"Subtotal: ₹{cart.item_total:,.0f}")
                basket_prefix = "\n".join(basket_lines)

                prompt_msg = AddressStageManager.format_address_prompt(
                    addresses, basket_prefix=basket_prefix
                )
                return OrchestratorTurnResult(
                    session_id=session.session_id,
                    conversation_state=ConversationState.NEEDS_DECISION,
                    user_message=prompt_msg,
                    address_options=addresses,
                    events=events,
                )

        return await self._make_awaiting_confirmation(
            session, contract, cart, recovery_notes, events
        )

    async def handle_address_choice(
        self,
        session_id: str,
        address_id: str,
    ) -> OrchestratorTurnResult:
        """Handle delivery address selection (Turn 2: Address -> Turn 3: Payment)."""
        session = self._store.get(session_id)
        if not session or not session.pending_address_choice:
            return await self.handle_turn(
                session_id=session_id,
                customer_id=session.customer_id if session else "default",
                message=address_id,
            )

        events: list[str] = list(session.events)
        pending = session.pending_address_choice
        addresses = pending.addresses

        selected: Optional[DeliveryAddress] = None
        cleaned = address_id.strip().lower()
        if cleaned.isdigit():
            idx = int(cleaned) - 1
            if 0 <= idx < len(addresses):
                selected = addresses[idx]
        if not selected:
            for addr in addresses:
                if addr.id.lower() == cleaned or (addr.label and addr.label.lower() == cleaned):
                    selected = addr
                    break
        if not selected:
            for addr in addresses:
                if cleaned in (addr.label or "").lower() or cleaned in (addr.street or "").lower():
                    selected = addr
                    break
        if not selected:
            selected = addresses[0]

        session.address_id = selected.id
        session.address_display = _display_address(selected)
        session.address_confirmed = True
        session.pending_address_choice = None
        default_address_manager.save_address(session.customer_id, selected.id)
        events.append(f"ADDRESS_SELECTED id={selected.id}")

        cart_id = session.cart_id
        try:
            with self._port.customer_scope(session.customer_id):
                raw_options = await self._port.get_payment_options(
                    cart_id=cart_id,
                    address_id=selected.id,
                )
                payment_options = [o for o in raw_options if o.is_available]
        except Exception as exc:
            return self._provider_failure_result(session, exc, events)

        if not payment_options:
            return self._handle_failed(session, "no payment options available", events)

        grouped = _group_payment_options(payment_options)

        # If only 1 payment option available, auto-select and proceed to confirmation receipt
        if len(grouped) == 1:
            contract = session.intent_contract or IntentContract(session_id=session_id, goal="grocery order")
            try:
                cart = await self._port.get_cart(cart_id)
            except Exception as exc:
                return self._provider_failure_result(session, exc, events)
            return await self._make_awaiting_confirmation(
                session, contract, cart, [], events,
                preferred_payment_option_id=grouped[0].id,
                preferred_payment_method=grouped[0].method,
            )

        session.pending_payment_choice = PendingPaymentChoice(
            options=grouped,
            raw_options=payment_options,
            recovery_notes=[],
        )
        session.conversation_state = ConversationState.NEEDS_DECISION
        self._store.save(session)
        events.append("PAYMENT_CHOICE_REQUIRED")

        user_msg = _msg_payment_choice(grouped, address_display=session.address_display)
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.NEEDS_DECISION,
            user_message=user_msg,
            payment_options=grouped,
            payment_choice_nonce=session.pending_payment_choice.nonce,
            events=events,
        )

    async def _make_awaiting_confirmation(
        self,
        session: OrchestratorSession,
        contract: IntentContract,
        cart: Any,
        recovery_notes: list[str],
        events: list[str],
        *,
        preferred_payment_method: Optional[str] = None,
        preferred_payment_option_id: Optional[str] = None,
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
        except Exception as exc:
            return self._provider_failure_result(session, exc, events)

        if not payment_options:
            session.pending_payment_choice = None
            return self._handle_failed(
                session,
                "no payment option is currently available",
                events + ["PAYMENT_OPTIONS_UNAVAILABLE"],
            )

        # Resolve customer or session payment preference if not passed explicitly
        if preferred_payment_option_id is None and preferred_payment_method is None:
            if session.selected_payment_option_id:
                preferred_payment_option_id = session.selected_payment_option_id
            elif session.selected_payment_method:
                preferred_payment_method = session.selected_payment_method
            elif session.customer_id in self._customer_payment_preferences:
                preferred_payment_option_id = self._customer_payment_preferences[session.customer_id]

        selected: Optional[PaymentOption] = None
        if preferred_payment_option_id is not None:
            selected = next(
                (
                    option
                    for option in payment_options
                    if _payment_option_key(option) == preferred_payment_option_id
                    or (option.id and option.id.casefold() == preferred_payment_option_id.casefold())
                    or option.method.casefold() == preferred_payment_option_id.casefold()
                ),
                None,
            )
            if selected is None:
                return self._payment_choice_result(
                    session,
                    payment_options,
                    recovery_notes,
                    events + ["PAYMENT_METHOD_UNAVAILABLE"],
                )
        elif preferred_payment_method is not None:
            requested = preferred_payment_method.casefold()
            matching = [
                option
                for option in payment_options
                if option.method.casefold() == requested
                or (option.id is not None and option.id.casefold() == requested)
                or requested in option.label.casefold()
            ]
            if len(matching) == 1:
                selected = matching[0]
            elif len(matching) > 1:
                selected = matching[0]
            else:
                return self._payment_choice_result(
                    session,
                    payment_options,
                    recovery_notes,
                    events + ["PAYMENT_METHOD_UNAVAILABLE"],
                )
        elif len(payment_options) == 1:
            selected = payment_options[0]
        else:
            return self._payment_choice_result(
                session,
                payment_options,
                recovery_notes,
                events + ["PAYMENT_CHOICE_REQUIRED"],
            )

        assert selected is not None

        session.selected_payment_method = selected.method
        session.selected_payment_option_id = selected.id
        session.selected_payment_option_kind = selected.kind
        session.selected_payment_option_label = selected.label
        self._customer_payment_preferences[session.customer_id] = selected.id or selected.method

        snapshot = create_confirmation_snapshot(
            cart,
            contract,
            address_id,
            selected.method,
            selected.id,
            selected.kind,
        )
        session.pending_payment_choice = None
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
            address_display=session.address_display,
            selected_payment_method=selected.method,
            selected_payment_option_id=selected.id,
            selected_payment_option_kind=selected.kind,
            selected_payment_option_label=selected.label,
        )
        msg = _msg_confirmation_basket(basket)

        events.append("AWAITING_CONFIRMATION")
        return OrchestratorTurnResult(
            session_id=session.session_id,
            conversation_state=ConversationState.AWAITING_CONFIRMATION,
            user_message=msg,
            basket_summary=basket,
            requires_confirmation=True,
            events=events,
        )


