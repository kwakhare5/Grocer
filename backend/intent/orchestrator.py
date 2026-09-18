"""GrocerOrchestrator — end-to-end conversational commerce loop (Spec Section 12, Section 20 Phase 6).

Connects:
    IntentParser → PolicyEngine → CommercePort → IntentVerifier → RecoveryEngine

Architecture rule (Spec Section 12.3):
    LLM interprets and proposes. Deterministic code enforces and verifies.
    All state transitions in this module are deterministic.

Entry points:
    handle_turn()           — main message handler: parse → build → verify → recover
    handle_choice()         — resolve a NEEDS_DECISION clarification
    handle_change_request() — invalidate approval and return to building
    handle_address_choice() — select delivery address
    handle_payment_choice() — select payment option
    handle_confirm()        — explicit checkout confirmation (AWAITING_CONFIRMATION → ORDERED)
    handle_payment_status() — poll/advance pending UPI/gateway payment
    handle_order_details()  — fetch itemized provider order bill
    handle_delivery_status()— fetch real-time ETA and tracking status
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.integrations.commerce.exceptions import (
    CommerceError,
    ProviderAuthError,
    ProviderSessionRevokedError,
    UnconfirmedCheckoutError,
    UpstreamTimeoutError,
)
from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.models import (
    CartItem,
    CartItemUpdate,
    CommerceCart,
    CommerceOrderResult,
    CommerceProductItem,
    DeliveryAddress,
    OrderChildResult,
    PaymentOption,
)
from backend.integrations.commerce.port import CommercePort
from backend.intent import (
    orchestrator_address as address_flow,
    orchestrator_choice as choice_flow,
    orchestrator_confirm as confirm_flow,
    orchestrator_payment as payment_flow,
    orchestrator_tracking as tracking_flow,
)
from backend.intent.enums import PreferenceType
from backend.intent.models import BrandPreference, IntentContract, IntentItem
from backend.intent.parser import IntentParser
from backend.intent.policy import PolicyEngine
from backend.intent.preferences import default_preference_store
from backend.intent.recovery import (
    FailureClass,
    RecoveryCandidate,
    RecoveryEngine,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.recovery_loop import LoopingRecoveryEngine
from backend.intent.session import (
    BasketSummary,
    ClarificationOption,
    ConversationState,
    OrchestratorSession,
    OrchestratorSessionStore,
    PendingAddressChoice,
    PendingClarification,
    PendingPaymentChoice,
    default_session_store,
)
from backend.intent.stages import (
    AddressStageManager,
    _candidates_to_options,
    _detect_removal_request,
    _detect_swap_request,
    _display_address,
    _group_payment_options,
    _is_fresh_request,
    _is_incremental_add,
    _msg_clarification,
    _msg_confirmation_basket,
    _msg_failed,
    _msg_ordered,
    _msg_payment_choice,
    _msg_payment_pending,
    _payment_option_key,
    _resolve_items,
    _search_and_pick,
    _targeted_recovery_query,
    default_address_manager,
    match_payment_choice,
)
from backend.intent.storage import default_intent_store
from backend.intent.verifier import IntentVerifier, VerificationResult, VerificationStatus


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
        policy_engine: Optional[PolicyEngine] = None,
        parser: Optional[IntentParser] = None,
    ) -> None:
        self._port = commerce_adapter or get_commerce_adapter()
        self._store = session_store or default_session_store
        self._recovery = recovery_engine
        self._verifier = verifier or IntentVerifier()
        self._policy = policy_engine or PolicyEngine()
        self._parser = parser or IntentParser()
        self._customer_payment_preferences: dict[str, str] = {}
        self._customer_addresses: dict[str, str] = {}

    async def handle_turn(
        self,
        session_id: str,
        customer_id: str,
        message: str,
        address_id: Optional[str] = None,
    ) -> OrchestratorTurnResult:
        """Main entry point: handle a user message for a session."""
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

        # 0. Conversational greeting check
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

        # Universal intent interception
        is_item_mod = bool(
            temp_contract.items
            or _detect_swap_request(message)
            or _detect_removal_request(message)
        )
        if is_item_mod:
            session.pending_address_choice = None
            session.pending_payment_choice = None
            session.conversation_state = ConversationState.BUILDING
            self._store.save(session)
        elif session.conversation_state == ConversationState.NEEDS_DECISION and session.pending_address_choice:
            if not _is_fresh_request(message):
                return await self.handle_address_choice(session_id, message)

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

        # 1. Inspect live cart for drift, swaps, or removals
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

            # Fast-path 1.1: Conversational item swap
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

            # Fast-path 1.2: Conversational item removal
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

    # ------------------------------------------------------------------
    # Delegated action handlers
    # ------------------------------------------------------------------

    def _handle_needs_decision(
        self,
        session: OrchestratorSession,
        cart: CommerceCart,
        verification: VerificationResult,
        outcome: RecoveryOutcome,
        events: list[str],
    ) -> OrchestratorTurnResult:
        return choice_flow.handle_needs_decision(self, session, cart, verification, outcome, events)

    async def handle_change_request(self, session_id: str) -> OrchestratorTurnResult:
        return await choice_flow.handle_change_request(self, session_id)

    async def handle_choice(
        self,
        session_id: str,
        chosen_spin_id: str,
        clarification_nonce: str,
    ) -> OrchestratorTurnResult:
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
        return await choice_flow.handle_choice_locked(
            self,
            session_id=session_id,
            chosen_spin_id=chosen_spin_id,
            clarification_nonce=clarification_nonce,
        )

    def _payment_choice_result(
        self,
        session: OrchestratorSession,
        options: list[PaymentOption],
        recovery_notes: list[str],
        events: list[str],
        *,
        pending: Optional[PendingPaymentChoice] = None,
    ) -> OrchestratorTurnResult:
        return payment_flow.payment_choice_result(
            self, session, options, recovery_notes, events, pending=pending
        )

    async def handle_payment_choice(
        self,
        session_id: str,
        payment_option_id: str,
        payment_choice_nonce: Optional[str],
    ) -> OrchestratorTurnResult:
        return await payment_flow.handle_payment_choice(
            self, session_id, payment_option_id, payment_choice_nonce
        )

    async def handle_address_choice(
        self,
        session_id: str,
        address_id: str,
    ) -> OrchestratorTurnResult:
        return await address_flow.handle_address_choice(self, session_id, address_id)

    async def _advance_after_cart_built(
        self,
        session: OrchestratorSession,
        contract: IntentContract,
        cart: Any,
        recovery_notes: list[str],
        events: list[str],
    ) -> OrchestratorTurnResult:
        return await address_flow.advance_after_cart_built(
            self, session, contract, cart, recovery_notes, events
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
        return await confirm_flow.make_awaiting_confirmation(
            self,
            session,
            contract,
            cart,
            recovery_notes,
            events,
            preferred_payment_method=preferred_payment_method,
            preferred_payment_option_id=preferred_payment_option_option_id if False else preferred_payment_option_id,
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
        return await confirm_flow.handle_confirm_locked(
            self,
            session_id=session_id,
            payment_method=payment_method,
            address_id=address_id,
            confirmation_nonce=confirmation_nonce,
        )

    def _apply_order_result(
        self,
        session: OrchestratorSession,
        order: CommerceOrderResult,
        events: list[str],
    ) -> OrchestratorTurnResult:
        return confirm_flow.apply_order_result(self, session, order, events)

    async def handle_payment_status(self, session_id: str) -> OrchestratorTurnResult:
        return await tracking_flow.handle_payment_status(self, session_id)

    async def handle_order_details(self, session_id: str) -> OrchestratorTurnResult:
        return await tracking_flow.handle_order_details(self, session_id)

    async def handle_delivery_status(self, session_id: str) -> OrchestratorTurnResult:
        return await tracking_flow.handle_delivery_status(self, session_id)

    # ------------------------------------------------------------------
    # Error & parsing helpers
    # ------------------------------------------------------------------

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

    def _parse_intent(self, message: str, session: OrchestratorSession, events: list[str]) -> IntentContract:
        contract = self._parser.parse(message, session_id=session.session_id)
        events.append(f"INTENT_PARSED items={len(contract.items)}")
        return contract

    def _apply_preferences(self, contract: IntentContract, customer_id: str, events: list[str]) -> None:
        customer_prefs = default_preference_store.get_preferences(customer_id)
        for pref in customer_prefs:
            if pref.preference_type == PreferenceType.DIETARY and pref.value == "vegetarian":
                contract.dietary_preferences.append("vegetarian")
                events.append("PREFERENCE_APPLIED dietary=vegetarian")
            elif pref.preference_type == PreferenceType.PREFERRED_BRAND and pref.target:
                contract.brand_preferences.append(
                    BrandPreference(brand=pref.value, target_category=pref.target, is_hard=False)
                )
                events.append(f"PREFERENCE_APPLIED brand={pref.value}")
