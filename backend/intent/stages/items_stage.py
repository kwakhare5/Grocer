"""Stage 1: Items Stage.

Handles grocery item extraction, variant picking from catalog, item clarification,
conversational item swaps, and item removals while preserving SKU ID and spin ID invariants.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any, Optional

from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceProductItem,
    PaymentOption,
    ProductVariant,
)
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import (
    IntentContract,
    IntentItem,
    ResolvedMeaning,
)
from backend.intent.semantics import (
    brand_identity_matches,
    normalize_pack_quantity,
    normalize_requested_quantity,
    product_identity_matches,
    required_pack_count,
)
from backend.intent.recovery import RecoveryCandidate
from backend.intent.session import (
    BasketItem,
    BasketSummary,
    ClarificationOption,
)


def _detect_swap_request(message: str) -> Optional[tuple[Optional[str], str]]:
    """Detect conversational swap/replacement request.

    Returns (old_item_hint, new_item_name) or None.
    """
    lower = message.lower().strip()
    m = re.match(r"^(?:replace|change|swap)\s+(.+?)\s+(?:with|to|for)\s+(.+)$", lower)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(?:make\s+it|switch\s+to|change(?:\s+it)?\s+to)\s+(.+)$", lower)
    if m:
        return None, m.group(1).strip()
    m = re.match(r"^instead\s+of\s+(.+?)\s*,\s*(?:make\s+it|get|give\s+me)?\s*(.+)$", lower)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.+?)\s+instead(?:\s+of\s+(.+))?$", lower)
    if m:
        old_part = m.group(2).strip() if m.group(2) else None
        return old_part, m.group(1).strip()
    return None


def _detect_removal_request(message: str) -> Optional[str]:
    """Detect conversational removal request.

    Returns target item hint or None.
    """
    lower = message.lower().strip()
    m = re.match(r"^(?:remove|drop|delete|cancel|omit|exclude)\s+(?:the\s+)?(.+)$", lower)
    if m:
        return m.group(1).strip()
    m = re.match(r"^(?:no|don['']?t\s+need|don['']?t\s+want|do\s+not\s+want)\s+(?:the\s+)?(.+)$", lower)
    if m:
        return m.group(1).strip()
    return None


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
                            "sku_id": variant.sku_id,
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


async def _resolve_items(
    port: CommercePort,
    contract: IntentContract,
    address_id: str,
    events: list[str],
) -> list[CartItemUpdate]:
    """Resolve each IntentItem into a CartItemUpdate via CommercePort search."""
    updates: list[CartItemUpdate] = []
    for item in contract.items:
        update = await _search_and_pick(port, address_id, item)
        if update:
            updates.append(update)
            events.append(f"ITEM_RESOLVED name={item.name!r} spin_id={update.spin_id}")
        else:
            events.append(f"ITEM_UNRESOLVED name={item.name!r}")
    return updates


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


def _is_incremental_add(message: str) -> bool:
    lower = message.lower().strip()
    return lower.startswith(("add", "also add", "plus", "and add", "include"))


def _is_fresh_request(message: str) -> bool:
    """Heuristic: treat message as fresh grocery request vs a refinement."""
    lower = message.lower().strip()
    if _is_incremental_add(message) or _detect_swap_request(message) or _detect_removal_request(message):
        return False
    fresh_keywords = {
        "get", "buy", "order", "weekly", "monthly", "groceries",
        "vegetables", "staples", "restock", "need",
    }
    return any(kw in lower for kw in fresh_keywords)


def _merge_contracts(
    existing: IntentContract, new: IntentContract, message: str = ""
) -> IntentContract:
    """Merge new contract onto existing, respecting intent precedence (Spec Section 5.3)."""
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

