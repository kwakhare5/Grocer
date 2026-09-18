"""Concrete recovery failure handlers for GROCER intent drift repair (Spec Section 10)."""
from __future__ import annotations

import math
from typing import Any, Optional

from backend.integrations.commerce.models import (
    CartItem,
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.intent.models import IntentContract, IntentItem
from backend.intent.policy import (
    ActionProposal,
    AutonomyLevel,
    PolicyEngine,
)
from backend.intent.verifier import (
    VerificationResult,
    ViolationCode,
)
from backend.intent.semantics import (
    brand_identity_matches,
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)
from backend.intent.recovery_candidates import (
    calculate_pack_multiple,
    extract_brand,
    filter_by_hard_constraints,
    find_candidates,
    score_candidate,
)


def handle_transient_error(attempt_number: int, max_attempts: int) -> Any:
    """Handle safe provider retry after a transient error (Spec Section 10.2 item 6)."""
    from backend.intent.recovery import FailureClass, RecoveryAction, RecoveryOutcome, RecoveryState

    action = RecoveryAction(
        action_type="retry",
        spin_id="system-retry",
        name="upstream_provider",
        quantity=1,
        price=0.0,
        reason="Safe transient retry per provider contract",
    )
    return RecoveryOutcome(
        state=RecoveryState.RECOVERED,
        failure_class=FailureClass.TRANSIENT_ERROR,
        recovery_actions=[action],
        message="Transient provider error detected; safely retrying action.",
        attempt_number=attempt_number,
        can_auto_apply=True,
    )


def handle_min_order_failure(
    contract: IntentContract,
    cart: CommerceCart,
    available_products: list[CommerceProductItem],
    attempt_number: int,
) -> Any:
    """Handle minimum-order basket failure by suggesting staple addition (Spec Section 10.2 item 8)."""
    from backend.intent.recovery import (
        FailureClass,
        RecoveryAction,
        RecoveryCandidate,
        RecoveryOutcome,
        RecoveryState,
    )

    shortfall = cart.min_order_threshold - cart.grand_total
    max_budget = contract.budget.max_budget if contract.budget else float("inf")

    active_categories = {
        (ci.category or "").lower() for ci in cart.items if getattr(ci, "category", None)
    } | {
        (it.category or "").lower() for it in contract.items if getattr(it, "category", None)
    }
    active_categories.discard("")

    candidates: list[tuple[RecoveryCandidate, int]] = []
    for prod in available_products:
        for variant in prod.variants:
            if variant.in_stock is not False and variant.price > 0:
                required_quantity = max(1, math.ceil(shortfall / variant.price))
                added_total = variant.price * required_quantity
                new_total = cart.grand_total + added_total
                if new_total <= max_budget:
                    base_score = max(0.1, 1.0 - abs(added_total - shortfall) / 100.0)
                    prod_cat = (prod.category or "").lower()
                    if active_categories and prod_cat in active_categories:
                        base_score += 0.3
                    elif prod_cat in {"staples", "dairy", "produce"}:
                        base_score += 0.1
                    elif active_categories and prod_cat not in active_categories:
                        base_score = max(0.05, base_score - 0.2)
                    score = round(min(1.0, max(0.05, base_score)), 2)
                    candidates.append(
                        (
                            RecoveryCandidate(
                                spin_id=variant.spin_id,
                                name=variant.name,
                                pack_size=variant.pack_size,
                                price=variant.price,
                                category=prod.category,
                                score=score,
                                reasons=[
                                    f"Adds {required_quantity} × ₹{variant.price:.0f} "
                                    f"to satisfy the ₹{cart.min_order_threshold:.0f} minimum"
                                ],
                            ),
                            required_quantity,
                        )
                    )

    candidates.sort(key=lambda entry: entry[0].score, reverse=True)
    if candidates:
        top, top_quantity = candidates[0]
        action = RecoveryAction(
            action_type="add_item",
            spin_id=top.spin_id,
            name=top.name,
            quantity=top_quantity,
            price=top.price,
            reason=f"Add staple item to meet min order threshold (₹{cart.min_order_threshold:.0f})",
        )
        return RecoveryOutcome(
            state=RecoveryState.NEEDS_USER_DECISION,
            failure_class=FailureClass.MIN_ORDER_FAILURE,
            recovery_actions=[action],
            candidates_for_user=[candidate for candidate, _ in candidates[:3]],
            message=(
                f"Cart total (₹{cart.grand_total:.0f}) is below the "
                f"₹{cart.min_order_threshold:.0f} minimum order threshold. "
                f"Add {top_quantity} × {top.name} "
                f"(₹{top.price * top_quantity:.0f}) to meet the threshold?"
            ),
            attempt_number=attempt_number,
            can_auto_apply=False,
        )

    return RecoveryOutcome(
        state=RecoveryState.BLOCKED,
        failure_class=FailureClass.MIN_ORDER_FAILURE,
        message=f"Cart total (₹{cart.grand_total:.0f}) is below minimum order threshold (₹{cart.min_order_threshold:.0f}) and no compliant items found within budget.",
        attempt_number=attempt_number,
        can_auto_apply=False,
    )


def handle_stale_cart(
    cart: CommerceCart,
    verification_result: VerificationResult,
    attempt_number: int,
) -> Any:
    """Handle stale cart or serviceability changes. Always requires human attention."""
    from backend.intent.recovery import FailureClass, RecoveryOutcome, RecoveryState

    return RecoveryOutcome(
        state=RecoveryState.NEEDS_USER_DECISION,
        failure_class=FailureClass.STALE_CART,
        message="Cart is stale or store is not serviceable. Please refresh or update address.",
        attempt_number=attempt_number,
        can_auto_apply=False,
        remaining_violations=verification_result.violations,
    )


def handle_budget_drift(
    policy_engine: PolicyEngine,
    contract: IntentContract,
    cart: CommerceCart,
    verification_result: VerificationResult,
    available_products: list[CommerceProductItem],
    attempt_number: int,
) -> Any:
    """Attempt to swap an item for a cheaper variant to bring cart under budget."""
    from backend.intent.recovery import (
        FailureClass,
        RecoveryAction,
        RecoveryCandidate,
        RecoveryOutcome,
        RecoveryState,
    )

    max_budget = contract.budget.max_budget if contract.budget else float("inf")
    overrun = cart.grand_total - max_budget

    best_swap: Optional[
        tuple[CartItem, IntentItem, CommerceProductItem, ProductVariant, int, float]
    ] = None

    for cart_item in cart.items:
        intent_item = next(
            (
                item
                for item in contract.items
                if product_identity_matches(
                    item.name,
                    cart_item.name,
                    item.category,
                    cart_item.category,
                )
            ),
            None,
        )
        if intent_item is None:
            continue
        requested = normalize_requested_quantity(
            intent_item.quantity,
            intent_item.unit,
            intent_item.name,
            quantity_is_explicit=intent_item.quantity_is_explicit,
            pack_size_preference=intent_item.pack_size_preference,
        )
        if requested is None:
            continue
        matching_products = [
            p for p in available_products
            if product_identity_matches(
                intent_item.name,
                p.name,
                intent_item.category,
                p.category,
            )
        ]
        for prod in matching_products:
            for variant in prod.variants:
                if variant.in_stock is False:
                    continue
                if variant.spin_id == cart_item.spin_id:
                    continue
                brand_rule = contract.get_brand_preference(intent_item.name)
                required_brand = intent_item.brand_preference or (
                    brand_rule.preferred_brand
                    if brand_rule and brand_rule.is_hard
                    else None
                )
                if required_brand and not brand_identity_matches(
                    required_brand,
                    prod.brand,
                    prod.name,
                    variant.name,
                ):
                    continue
                pack_count = required_pack_count(
                    requested,
                    normalize_pack_quantity(variant.pack_size),
                )
                if pack_count is None:
                    continue
                replacement_total = variant.price * pack_count
                savings = cart_item.total_price - replacement_total
                projected_total = cart.grand_total - cart_item.total_price + replacement_total
                if savings >= overrun and projected_total <= max_budget:
                    if best_swap is None or savings < best_swap[5]:
                        best_swap = (
                            cart_item,
                            intent_item,
                            prod,
                            variant,
                            pack_count,
                            savings,
                        )

    if best_swap:
        old_item, selected_intent, selected_product, new_variant, pack_count, savings = best_swap
        brand_rule = contract.get_brand_preference(selected_intent.name)
        new_brand = selected_product.brand or extract_brand(new_variant.name)
        if brand_rule and brand_identity_matches(
            brand_rule.preferred_brand,
            selected_product.brand,
            selected_product.name,
            new_variant.name,
        ):
            new_brand = brand_rule.preferred_brand
        proposal = ActionProposal(
            action_type="substitute",
            target=selected_intent.name,
            details={
                "item_name": new_variant.name,
                "replacement": new_variant.name,
                "price_delta": -savings,
                "new_brand": new_brand,
            },
            reason=f"Downsize/swap to bring total within ₹{max_budget:.0f} budget",
        )
        decision = policy_engine.evaluate(proposal, contract)
        action = RecoveryAction(
            action_type="replace_item",
            spin_id=new_variant.spin_id,
            name=new_variant.name,
            quantity=pack_count,
            removes_spin_id=old_item.spin_id,
            price=new_variant.price,
            reason=proposal.reason,
        )
        if decision.autonomy_level == AutonomyLevel.AUTO_EXECUTE:
            return RecoveryOutcome(
                state=RecoveryState.RECOVERED,
                failure_class=FailureClass.BUDGET_DRIFT,
                recovery_actions=[action],
                message=f"Adjusted {old_item.name} to {new_variant.name} to stay within ₹{max_budget:.0f} budget.",
                attempt_number=attempt_number,
                can_auto_apply=True,
            )
        else:
            return RecoveryOutcome(
                state=RecoveryState.NEEDS_USER_DECISION,
                failure_class=FailureClass.BUDGET_DRIFT,
                candidates_for_user=[
                    RecoveryCandidate(
                        spin_id=new_variant.spin_id,
                        name=new_variant.name,
                        pack_size=new_variant.pack_size,
                        price=new_variant.price,
                        category="budget_saver",
                        score=0.9,
                        reasons=[f"Saves ₹{savings:.0f} to meet budget"],
                    )
                ],
                message=f"Cart exceeds budget by ₹{overrun:.0f}. Would you like to swap {old_item.name} with {new_variant.name}?",
                attempt_number=attempt_number,
                can_auto_apply=False,
            )

    return RecoveryOutcome(
        state=RecoveryState.NEEDS_USER_DECISION,
        failure_class=FailureClass.BUDGET_DRIFT,
        message=f"Basket is ₹{overrun:.0f} over budget. Please adjust your items or budget limit.",
        attempt_number=attempt_number,
        can_auto_apply=False,
        remaining_violations=verification_result.violations,
    )


def handle_item_or_brand_unavailable(
    policy_engine: PolicyEngine,
    contract: IntentContract,
    cart: CommerceCart,
    verification_result: VerificationResult,
    available_products: list[CommerceProductItem],
    failure_class: Any,
    attempt_number: int,
) -> Any:
    """Generate, filter, rank candidates for missing/unavailable item."""
    from backend.intent.recovery import (
        FailureClass,
        RecoveryAction,
        RecoveryCandidate,
        RecoveryOutcome,
        RecoveryState,
    )

    target_name = ""
    removes_spin_id: Optional[str] = None
    quantity = 1

    for v in verification_result.violations:
        if v.violation_code in (
            ViolationCode.ITEM_UNAVAILABLE,
            ViolationCode.MISSING_ITEM,
            ViolationCode.WRONG_BRAND,
            ViolationCode.WRONG_PACK_SIZE,
            ViolationCode.WRONG_QUANTITY,
            ViolationCode.DIETARY_VIOLATION,
        ):
            target_name = v.target
            break

    if not target_name and verification_result.unresolved_items:
        target_name = verification_result.unresolved_items[0]

    intent_item = next(
        (item for item in contract.items if item.name.lower() in target_name.lower() or target_name.lower() in item.name.lower()),
        None,
    )
    if intent_item:
        quantity = int(intent_item.quantity)

    matched_cart_item = next(
        (ci for ci in cart.items if ci.name.lower() == target_name.lower() or target_name.lower() in ci.name.lower()),
        None,
    )
    if matched_cart_item:
        removes_spin_id = matched_cart_item.spin_id
        quantity = matched_cart_item.quantity

    raw_candidates = find_candidates(target_name, intent_item, available_products)

    filtered_candidates = filter_by_hard_constraints(
        raw_candidates,
        target_name,
        contract,
        cart,
        policy_engine,
        removes_spin_id,
        intent_item,
    )

    if intent_item:
        filtered_candidates = [
            (product, variant)
            for product, variant in filtered_candidates
            if calculate_pack_multiple(intent_item, variant.pack_size) > 0
            and (
                not intent_item.brand_preference
                or brand_identity_matches(
                    intent_item.brand_preference,
                    product.brand,
                    product.name,
                    variant.name,
                )
            )
        ]

    if not filtered_candidates:
        return RecoveryOutcome(
            state=RecoveryState.BLOCKED,
            failure_class=failure_class,
            message=f"No compliant replacement found for '{target_name}' that satisfies all hard constraints",
            attempt_number=attempt_number,
            can_auto_apply=False,
            remaining_violations=verification_result.violations,
        )

    scored = []
    for c in filtered_candidates:
        prod, variant = c
        final_score, reasons = score_candidate(c, target_name, intent_item, contract)
        scored.append(
            RecoveryCandidate(
                spin_id=variant.spin_id,
                sku_id=variant.sku_id,
                name=variant.name,
                pack_size=variant.pack_size,
                price=variant.price,
                category=prod.category,
                score=final_score,
                reasons=reasons,
            )
        )
    scored.sort(key=lambda c: c.score, reverse=True)

    top_candidate = scored[0]

    multiple = 1
    if intent_item:
        multiple = calculate_pack_multiple(intent_item, top_candidate.pack_size)
        if multiple < 1:
            return RecoveryOutcome(
                state=RecoveryState.BLOCKED,
                failure_class=failure_class,
                message=f"No exact quantity-preserving replacement found for '{target_name}'",
                attempt_number=attempt_number,
                can_auto_apply=False,
                remaining_violations=verification_result.violations,
            )
        quantity = multiple

    old_pack = (
        matched_cart_item.pack_size
        if matched_cart_item and matched_cart_item.pack_size
        else (intent_item.pack_size_preference if intent_item and intent_item.pack_size_preference else "")
    )
    new_pack = top_candidate.pack_size or ""
    proposal = ActionProposal(
        action_type="substitute" if removes_spin_id else "add_item",
        target=target_name,
        details={
            "item_name": top_candidate.name,
            "replacement": top_candidate.name,
            "category": top_candidate.category,
            "price_delta": (
                top_candidate.price * quantity
                - (matched_cart_item.total_price if matched_cart_item else 0.0)
            ),
            "current_total": cart.grand_total,
            "new_brand": extract_brand(top_candidate.name),
            "old_pack_size": old_pack,
            "new_pack_size": new_pack,
        },
        reason=f"Substitute for unavailable '{target_name}'",
    )
    policy_decision = policy_engine.evaluate(proposal, contract)

    is_ambiguous = False
    target_lower = (intent_item.name if intent_item else target_name).lower()
    bp = contract.get_brand_preference(target_lower)
    if len(scored) > 1:
        score_diff = scored[0].score - scored[1].score
        has_exact_match = (
            bp is not None and bp.preferred_brand.lower() in scored[0].name.lower()
            and intent_item is not None and intent_item.pack_size_preference is not None
            and intent_item.pack_size_preference.lower() in scored[0].pack_size.lower()
        )
        if not has_exact_match:
            if score_diff < 0.08:
                is_ambiguous = True

    restores_existing_variant = bool(
        matched_cart_item
        and top_candidate.spin_id == matched_cart_item.spin_id
    )
    if restores_existing_variant:
        is_ambiguous = False

    action_reason = (
        f"Supplied {multiple}x {top_candidate.pack_size} packs to fulfill requested {intent_item.name}"
        if multiple > 1 and intent_item
        else f"Replaced unavailable '{target_name}' with {top_candidate.name}"
    )

    action = RecoveryAction(
        action_type=(
            "adjust_quantity"
            if restores_existing_variant
            else ("replace_item" if removes_spin_id else "add_item")
        ),
        spin_id=top_candidate.spin_id,
        sku_id=top_candidate.sku_id,
        name=top_candidate.name,
        quantity=quantity,
        removes_spin_id=None if restores_existing_variant else removes_spin_id,
        price=top_candidate.price,
        reason=action_reason,
    )

    if policy_decision.autonomy_level == AutonomyLevel.AUTO_EXECUTE and not is_ambiguous:
        if failure_class == FailureClass.PROVIDER_QUANTITY_LIMIT and intent_item is not None:
            resolved = intent_item.resolved_meaning
            if (
                resolved is not None
                and resolved.cart_quantity is not None
                and resolved.actual_cart_quantity is not None
                and resolved.actual_cart_quantity < resolved.cart_quantity
            ):
                remaining = resolved.cart_quantity - resolved.actual_cart_quantity
                return RecoveryOutcome(
                    state=RecoveryState.RECOVERED,
                    failure_class=failure_class,
                    recovery_actions=[action],
                    message=(
                        f"You asked for {resolved.cart_quantity} × "
                        f"{resolved.provider_pack_description or top_candidate.pack_size}, "
                        f"but this store currently allows only {resolved.actual_cart_quantity} "
                        f"of this SKU. I added an alternative for the remaining {remaining}."
                    ),
                    attempt_number=attempt_number,
                    can_auto_apply=True,
                )
        return RecoveryOutcome(
            state=RecoveryState.RECOVERED,
            failure_class=failure_class,
            recovery_actions=[action],
            message=f"Automatically replaced '{target_name}' with '{top_candidate.name}'.",
            attempt_number=attempt_number,
            can_auto_apply=True,
        )

    if failure_class == FailureClass.PROVIDER_QUANTITY_LIMIT and intent_item is not None:
        resolved = intent_item.resolved_meaning
        if (
            resolved is not None
            and resolved.cart_quantity is not None
            and resolved.actual_cart_quantity is not None
            and resolved.actual_cart_quantity < resolved.cart_quantity
        ):
            remaining = resolved.cart_quantity - resolved.actual_cart_quantity
            clarification_msg = (
                policy_decision.clarification_needed
                or (
                    f"You asked for {resolved.cart_quantity} × "
                    f"{resolved.provider_pack_description or target_name}, "
                    f"but this store currently allows only {resolved.actual_cart_quantity} "
                    f"of this SKU. I can search for another option for the remaining {remaining}."
                )
            )
            return RecoveryOutcome(
                state=RecoveryState.NEEDS_USER_DECISION,
                failure_class=failure_class,
                candidates_for_user=scored[:3],
                recovery_actions=[action],
                message=clarification_msg,
                attempt_number=attempt_number,
                can_auto_apply=False,
            )
    clarification_msg = (
        policy_decision.clarification_needed
        or f"'{target_name}' is unavailable. I found multiple options: {', '.join(c.name for c in scored[:2])}. Which should I choose?"
    )
    return RecoveryOutcome(
        state=RecoveryState.NEEDS_USER_DECISION,
        failure_class=failure_class,
        candidates_for_user=scored[:3],
        recovery_actions=[action],
        message=clarification_msg,
        attempt_number=attempt_number,
        can_auto_apply=False,
    )
