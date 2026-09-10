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
import math
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
# Message templates  (Spec §11)
# ---------------------------------------------------------------------------

def _msg_confirmation_basket(basket: BasketSummary) -> str:
    """Render every approval-bound fact available to conversational clients."""

    lines = ["Your basket is ready:"]
    lines.extend(
        f"- {item.quantity} x {item.name} ({item.pack_size}): ₹{item.line_total:,.0f}"
        for item in basket.items
    )
    lines.extend(
        [
            f"Items: ₹{basket.item_total:,.0f}",
            f"Delivery: ₹{basket.delivery_fee:,.0f}",
            f"Packaging: ₹{basket.packaging_fee:,.0f}",
            f"Discount: -₹{basket.discount:,.0f}",
            f"Total: ₹{basket.grand_total:,.0f}",
            f"Address: {basket.address_display or basket.address_id or 'selected address'}",
            f"Payment: {basket.selected_payment_option_label or basket.selected_payment_method}",
        ]
    )
    if basket.recovery_notes:
        lines.append(f"Recovery: {'; '.join(basket.recovery_notes)}")
    if basket.interpretation_notes:
        lines.append(f"Interpretation: {'; '.join(basket.interpretation_notes)}")
    lines.append("Confirm to place this exact order.")
    return "\n".join(lines)


def _display_address(address: DeliveryAddress) -> str:
    return ", ".join(
        part
        for part in (
            address.label,
            address.street,
            address.city,
            address.postal_code,
        )
        if part
    ) or address.id


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


def _msg_payment_choice(options: list[PaymentOption]) -> str:
    lines = ["Which payment method would you like to use?"]
    lines.extend(f"{index}. {option.label}" for index, option in enumerate(options, 1))
    lines.append("Reply with the number or name of your choice.")
    return "\n".join(lines)


def _payment_option_key(option: PaymentOption) -> str:
    return option.id or option.method


def _targeted_recovery_query(
    contract: IntentContract, verification: Optional[Any]
) -> str:
    """Return one bounded, failed-intent catalog query rather than a broad pool."""
    violation_targets = {
        str(violation.target).casefold()
        for violation in getattr(verification, "violations", [])
        if getattr(violation, "target", None)
    }
    for item in contract.items:
        item_name = item.name.casefold()
        if any(target in item_name or item_name in target for target in violation_targets):
            return item.name
    return contract.items[0].name if contract.items else "grocery item"


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
    results: list[CommerceProductItem] = await port.search_products(address_id, item.name)

    if not results:
        return None

    all_variants = [
        (product, variant)
        for product in results
        for variant in product.variants
        if variant.in_stock is not False
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

    resolved: list[tuple[CommerceProductItem, Any, int, ResolvedMeaning]] = []
    catalog_dependent = requested.dimension == "catalog_dependent"
    individual_variants = [
        (product, variant)
        for product, variant in candidates
        if (pack := normalize_pack_quantity(variant.pack_size)) is not None
        and pack.dimension == "count"
        and math.isclose(pack.amount, 1)
    ]
    if catalog_dependent and individual_variants:
        candidates = individual_variants
    for product, variant in candidates:
        pack = normalize_pack_quantity(variant.pack_size)
        if catalog_dependent:
            if individual_variants:
                pack_count = int(requested.amount)
                meaning = ResolvedMeaning(
                    original_expression=f"{item.quantity:g} {item.name}",
                    requested_quantity=item.quantity,
                    requested_dimension="catalog_dependent",
                    interpretation_explicit=False,
                    status="EXACT",
                    spin_id=variant.spin_id,
                    sku_id=variant.sku_id,
                    provider_pack_description=variant.pack_size,
                    cart_quantity=pack_count,
                    expected_dimension="count",
                    expected_amount=requested.amount,
                    explanation=(
                        f"I found {item.name} sold individually, so this means "
                        f"{item.quantity:g} individual items."
                    ),
                )
            elif pack is not None and pack.dimension in {"mass", "volume"}:
                pack_count = int(requested.amount)
                meaning = ResolvedMeaning(
                    original_expression=f"{item.quantity:g} {item.name}",
                    requested_quantity=item.quantity,
                    requested_dimension="catalog_dependent",
                    interpretation_explicit=False,
                    status="INFERRED",
                    spin_id=variant.spin_id,
                    sku_id=variant.sku_id,
                    provider_pack_description=variant.pack_size,
                    cart_quantity=pack_count,
                    expected_dimension="pack_count",
                    expected_amount=requested.amount,
                    explanation=(
                        f"I found {item.name} sold as {variant.pack_size} retail packs, so this means "
                        f"{item.quantity:g} packs."
                    ),
                )
            else:
                continue
        else:
            pack_count = required_pack_count(requested, pack)
            meaning = ResolvedMeaning(
                original_expression=f"{item.quantity:g} {item.unit} {item.name}",
                requested_quantity=item.quantity,
                requested_dimension=requested.dimension,
                interpretation_explicit=True,
                status="EXACT",
                spin_id=variant.spin_id,
                sku_id=variant.sku_id,
                provider_pack_description=variant.pack_size,
                cart_quantity=pack_count,
                expected_dimension=requested.dimension,
                expected_amount=requested.amount,
                explanation=f"Adding {pack_count} × {variant.pack_size}.",
            )
        if pack_count is not None:
            resolved.append((product, variant, pack_count, meaning))
    if not resolved:
        if catalog_dependent:
            count_packs = [
                variant.pack_size
                for _product, variant in candidates
                if (pack := normalize_pack_quantity(variant.pack_size)) is not None
                and pack.dimension == "count"
                and not math.isclose(pack.amount, 1)
            ]
            if count_packs:
                ambiguous_candidates = []
                for _product, variant in candidates:
                    if (pack := normalize_pack_quantity(variant.pack_size)) is not None and pack.dimension == "count" and not math.isclose(pack.amount, 1):
                        ambiguous_candidates.append({
                            "spin_id": variant.spin_id,
                            "name": variant.name,
                            "pack_size": variant.pack_size,
                            "price": variant.price,
                            "brand": _product.brand
                        })
                item.resolved_meaning = ResolvedMeaning(
                    original_expression=f"{item.quantity:g} {item.name}",
                    requested_quantity=item.quantity,
                    requested_dimension="catalog_dependent",
                    interpretation_explicit=False,
                    status="AMBIGUOUS",
                    clarification_required=True,
                    explanation=(
                        f"{item.name} is available only in count packs ({', '.join(count_packs)}), "
                        f"so I need to know which pack you mean."
                    ),
                    candidates=ambiguous_candidates,
                )
        return None

    preferred_pack = normalize_pack_quantity(item.pack_size_preference or "")

    def rank(candidate: tuple[CommerceProductItem, Any, int, ResolvedMeaning]) -> tuple[bool, float, float]:
        _product, variant, pack_count, _meaning = candidate
        candidate_pack = normalize_pack_quantity(variant.pack_size)
        misses_preference = preferred_pack is not None and candidate_pack != preferred_pack
        return misses_preference, variant.price * pack_count, variant.price

    _best_product, best_variant, quantity, meaning = min(resolved, key=rank)
    item.resolved_meaning = meaning

    return CartItemUpdate(
        spin_id=best_variant.spin_id,
        quantity=quantity,
        sku_id=best_variant.sku_id,
    )


def _build_basket_summary(
    cart: Any,
    contract: IntentContract,
    recovery_notes: list[str],
    *,
    confirmation_nonce: str,
    confirmation_expires_at: Any,
    payment_options: list[PaymentOption],
    address_display: Optional[str],
    selected_payment_method: str,
    selected_payment_option_id: Optional[str],
    selected_payment_option_kind: Optional[str],
    selected_payment_option_label: Optional[str],
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
        address_display=address_display,
        budget=budget,
        within_budget=(budget is None or grand_total <= budget),
        recovery_notes=recovery_notes,
        interpretation_notes=[
            item.resolved_meaning.explanation
            for item in contract.items
            if item.resolved_meaning is not None
            and item.resolved_meaning.status == "INFERRED"
        ],
        payment_options=payment_options,
        selected_payment_method=selected_payment_method,
        selected_payment_option_id=selected_payment_option_id,
        selected_payment_option_kind=selected_payment_option_kind,
        selected_payment_option_label=selected_payment_option_label,
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

        from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter

        is_swiggy = isinstance(self._port, SwiggyMCPAdapter)
        if address_id and not is_swiggy:
            if address_id != session.address_id:
                session.address_display = None
            session.address_id = address_id

        # Phase B: Strict live address resolution per Swiggy Builders Club spec
        needs_swiggy_address = is_swiggy and (
            not session.address_id
            or bool(address_id and address_id != session.address_id)
        )
        if needs_swiggy_address:
            try:
                addresses = await self._port.get_addresses(customer_id)
            except Exception as exc:
                return self._provider_failure_result(session, exc, events)

            if not addresses:
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

            pending_address = session.pending_address_choice
            selected: Optional[DeliveryAddress] = None
            selection_text = (address_id or message).casefold().strip()
            if pending_address is not None or address_id is not None:
                for index, candidate in enumerate(addresses, 1):
                    candidate_values = {
                        str(index),
                        candidate.id.casefold(),
                        candidate.label.casefold(),
                    }
                    if selection_text in candidate_values or (
                        candidate.street
                        and selection_text
                        and selection_text in candidate.street.casefold()
                    ):
                        selected = candidate
                        break

            if selected is None:
                original_request = (
                    pending_address.request_message if pending_address else message
                )
                session.pending_address_choice = PendingAddressChoice(
                    addresses=addresses,
                    request_message=original_request,
                )
                session.conversation_state = ConversationState.NEEDS_DECISION
                self._store.save(session)
                options_text = "\n".join(
                    f"{index}. {candidate.label}: "
                    f"{candidate.street or candidate.city or 'Saved Address'}"
                    for index, candidate in enumerate(addresses, 1)
                )
                return OrchestratorTurnResult(
                    session_id=session.session_id,
                    conversation_state=ConversationState.NEEDS_DECISION,
                    user_message=(
                        "Which address would you like to use for delivery?\n"
                        f"{options_text}\n"
                        "Reply with the number or label of your choice."
                    ),
                    address_options=addresses,
                    events=events + ["NEEDS_ADDRESS_SELECTION"],
                )

            session.address_id = selected.id
            session.address_display = _display_address(selected)
            if pending_address is not None:
                message = pending_address.request_message
            session.pending_address_choice = None
            events.append(f"ADDRESS_SELECTED id={selected.id}")

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
                new_updates: list[CartItemUpdate] = []
                try:
                    for item in new_contract_items:
                        update = await _search_and_pick(
                            self._port, effective_address, item
                        )
                        if update:
                            new_updates.append(update)
                            events.append(
                                f"ITEM_RESOLVED name={item.name!r} spin_id={update.spin_id}"
                            )
                        else:
                            events.append(f"ITEM_UNRESOLVED name={item.name!r}")
                except Exception as exc:
                    return self._provider_failure_result(session, exc, events)
                resolved_items = existing_updates + new_updates
            else:
                resolved_items = existing_updates
        else:
            try:
                resolved_items = await self._resolve_items(
                    contract, effective_address, events
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
            return await self._make_awaiting_confirmation(
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

        payment_choice = pending or PendingPaymentChoice(
            options=options,
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

            selected = next(
                (
                    option
                    for option in pending.options
                    if _payment_option_key(option) == payment_option_id
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
        """Execute checkout after explicit user confirmation (Spec §6, §8.3)."""
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

        selected: Optional[PaymentOption] = None
        if preferred_payment_option_id is not None:
            selected = next(
                (
                    option
                    for option in payment_options
                    if _payment_option_key(option) == preferred_payment_option_id
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
            ]
            if len(matching) == 1:
                selected = matching[0]
            elif len(matching) > 1:
                return self._payment_choice_result(
                    session,
                    matching,
                    recovery_notes,
                    events + ["PAYMENT_CHOICE_REQUIRED"],
                )
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

