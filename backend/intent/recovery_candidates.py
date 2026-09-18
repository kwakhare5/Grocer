"""Candidate generation, scoring, and hard constraint filtering for recovery engine."""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import (
    CommerceCart,
    CommerceProductItem,
    ProductVariant,
)
from backend.intent.enums import BrandTolerance, SubstitutionTolerance
from backend.intent.models import IntentContract, IntentItem
from backend.intent.policy import ActionProposal, PolicyEngine
from backend.intent.semantics import (
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)


def extract_brand(product_name: str) -> str:
    """Extract brand name heuristic (first token in Indian grocery catalog)."""
    tokens = product_name.strip().split()
    return tokens[0] if tokens else ""


def calculate_pack_multiple(intent_item: IntentItem, candidate_pack_size: str) -> int:
    """Return the exact quantity-preserving pack count, or zero if unsafe."""
    if (
        intent_item.resolved_meaning is not None
        and intent_item.resolved_meaning.cart_quantity is not None
        and intent_item.resolved_meaning.expected_dimension == "pack_count"
    ):
        return intent_item.resolved_meaning.cart_quantity

    requested = normalize_requested_quantity(
        intent_item.quantity,
        intent_item.unit,
        intent_item.name,
        quantity_is_explicit=intent_item.quantity_is_explicit,
        pack_size_preference=intent_item.pack_size_preference,
    )
    if requested is None:
        return 0
    count = required_pack_count(
        requested,
        normalize_pack_quantity(candidate_pack_size),
    )
    return count or 0


def find_candidates(
    target_name: str,
    intent_item: Optional[IntentItem],
    available_products: list[CommerceProductItem],
) -> list[tuple[CommerceProductItem, ProductVariant]]:
    """Find in-stock product variants matching the target's category or name."""
    candidates: list[tuple[CommerceProductItem, ProductVariant]] = []
    requested_name = intent_item.name if intent_item else target_name
    requested_category = intent_item.category if intent_item else None

    for prod in available_products:
        if product_identity_matches(
            requested_name,
            prod.name,
            requested_category,
            prod.category,
        ):
            for variant in prod.variants:
                if (
                    variant.in_stock is not False
                    and (
                        intent_item is None
                        or intent_item.resolved_meaning is None
                        or intent_item.resolved_meaning.cart_quantity is None
                        or variant.max_quantity is None
                        or variant.max_quantity >= intent_item.resolved_meaning.cart_quantity
                    )
                    and product_identity_matches(
                        requested_name,
                        variant.name,
                        requested_category,
                        prod.category,
                    )
                ):
                    candidates.append((prod, variant))

    return candidates


def filter_by_hard_constraints(
    candidates: list[tuple[CommerceProductItem, ProductVariant]],
    target_name: str,
    contract: IntentContract,
    cart: CommerceCart,
    policy_engine: PolicyEngine,
    removes_spin_id: Optional[str] = None,
    intent_item: Optional[IntentItem] = None,
) -> list[tuple[CommerceProductItem, ProductVariant]]:
    """Filter candidate variants using PolicyEngine hard constraint checks."""
    valid: list[tuple[CommerceProductItem, ProductVariant]] = []

    old_price = 0.0
    if removes_spin_id:
        for item in cart.items:
            if item.spin_id == removes_spin_id:
                old_price = item.total_price
                break

    for prod, variant in candidates:
        quantity = (
            calculate_pack_multiple(intent_item, variant.pack_size)
            if intent_item
            else 1
        )
        if quantity < 1:
            continue
        price_delta = variant.price * quantity - old_price
        proposal = ActionProposal(
            action_type="substitute" if removes_spin_id else "add_item",
            target=target_name,
            details={
                "item_name": variant.name,
                "category": prod.category,
                "new_brand": extract_brand(variant.name),
                "price_delta": price_delta,
                "current_total": cart.grand_total,
            },
            reason="Candidate viability check",
        )
        violations = policy_engine._check_hard_constraints(proposal, contract)
        if not violations:
            valid.append((prod, variant))

    return valid


def score_candidate(
    item_tuple: tuple[CommerceProductItem, ProductVariant],
    target_name: str,
    intent_item: Optional[IntentItem],
    contract: IntentContract,
) -> tuple[float, list[str]]:
    """Score candidate along 7 deterministic dimensions (Spec Section 10.3).
    
    Returns:
        (clamped_score, reasons_list)
    """
    prod, variant = item_tuple
    score = 0.4  # Base score for category/keyword relevance
    reasons: list[str] = ["Category/keyword match"]

    target_lower = (intent_item.name if intent_item else target_name).lower()
    bp = contract.get_brand_preference(target_lower)
    var_name_lower = variant.name.lower()

    # 1. Brand affinity scoring
    if bp:
        if bp.preferred_brand.lower() in var_name_lower:
            score += 0.45
            reasons.append(f"Preferred brand ({bp.preferred_brand}) match")
        else:
            alt_matched = False
            for idx, alt in enumerate(bp.alternative_brands):
                if alt.lower() in var_name_lower:
                    bonus = max(0.15, 0.30 - (idx * 0.10))
                    score += bonus
                    reasons.append(f"Approved alternative brand ({alt}) match (priority #{idx+1})")
                    alt_matched = True
                    break
            if not alt_matched and contract.substitution_policy.brand_tolerance == BrandTolerance.USUAL_BRANDS:
                score += 0.05
    else:
        # Check intent item brand_preference
        if intent_item and intent_item.brand_preference:
            if intent_item.brand_preference.lower() in var_name_lower:
                score += 0.45
                reasons.append(f"Specified brand ({intent_item.brand_preference}) match")

    # 2. Pack size similarity
    preferred_pack = intent_item.pack_size_preference if intent_item else None
    if preferred_pack:
        if preferred_pack.lower() in variant.pack_size.lower():
            score += 0.20
            reasons.append(f"Pack size ({preferred_pack}) exact match")
        elif contract.pack_size_rules.tolerance == SubstitutionTolerance.REASONABLE:
            score += 0.05
            reasons.append("Pack size within reasonable tolerance")

    # 3. Price impact
    if intent_item and intent_item.max_price and variant.price <= intent_item.max_price:
        score += 0.10
        reasons.append(f"Price ₹{variant.price:.0f} within item limit ₹{intent_item.max_price:.0f}")

    # Clamp between 0.0 and 1.0
    final_score = min(1.0, round(score, 2))
    return final_score, reasons
