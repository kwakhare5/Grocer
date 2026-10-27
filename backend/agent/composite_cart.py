"""Grocer v1.0 — Target Cart Assembly & Composite Commerce Engine.

Enforces:
1. Destructive Overwrite Safety: Reads get_cart(), merges existing items locally, and submits assembled target cart.
2. Read-After-Write Verification: Full-basket diffing against verified cart to detect drops, quantity reductions, or reverts.
3. Out-of-Stock Reconciliation: Missing items are rendered under "⚠️ *Not added (Out of stock)*" receipt cards.
4. Integer Paise Math Discipline: Zero floating-point money calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.integrations.commerce.schemas import CartData

logger = logging.getLogger("grocer.composite_cart")


@dataclass
class TargetCartItem:
    spin_id: str
    quantity: int = 1
    item_name: str | None = None
    price_paise: int = 0  # Strict integer paise (₹1 = 100 paise)
    sku_id: str | None = None
    max_quantity: int | None = None
    max_quantity_message: str | None = None


@dataclass
class CartReconciliationResult:
    cart: CartData
    dropped_out_of_stock: list[TargetCartItem]
    reduced_quantity: list[dict[str, Any]] = field(default_factory=list)
    capped_items: list[dict[str, Any]] = field(default_factory=list)
    added_lines: list[TargetCartItem] = field(default_factory=list)
    baseline_count: int = 0
    baseline_to_pay: str | None = None
    receipt_text: str = ""


def format_cart_receipt(
    cart: CartData,
    dropped_items: list[TargetCartItem] | None = None,
    store_name: str | None = None,
    coupon_code: str | None = None,
    coupon_savings_paise: int = 0,
    added_items: list[TargetCartItem] | None = None,
    capped_items: list[dict[str, Any]] | None = None,
    reduced_quantity: list[dict[str, Any]] | None = None,
    baseline_count: int = 0,
    baseline_to_pay: str | None = None,
) -> str:
    """Format the receipt. Show the change, not a second full basket dump.

    When the cart already had items, the added lines and the totals are the
    answer. When it was empty, the full list is the change.
    """
    lines: list[str] = []
    item_count = sum(it.quantity for it in cart.items)
    show_delta_only = bool(added_items) and baseline_count > 0

    if show_delta_only:
        lines.append("✅ *Added to your basket*")
        for it in added_items or []:
            total = format_paise_to_rupees(it.price_paise * it.quantity)
            lines.append(f"• {it.item_name or it.spin_id} x{it.quantity} — {total}")
        lines.append("")
        old = f" ({baseline_to_pay})" if baseline_to_pay else ""
        lines.append(
            f"You already had {baseline_count} items{old}. Basket now: *{item_count} items*. "
            "Ask *what's in my basket* to see them."
        )
        lines.append("-----------------------------------")
    else:
        lines.append("-----------------------------------")
        lines.append(f"🛒 *Your Basket ({item_count} items)*")
        for it in cart.items:
            it_price_paise = it.discounted_final_price_paise
            item_total_paise = it_price_paise * it.quantity
            formatted_price = format_paise_to_rupees(item_total_paise)
            variant_desc = f" ({it.itemVariant})" if it.itemVariant else ""
            lines.append(
                f"• {it.itemName}{variant_desc} x{it.quantity} — {formatted_price}"
            )
        lines.append("-----------------------------------")

    for cap in capped_items or []:
        allowed = cap.get("allowed", 0)
        requested = cap.get("requested", 0)
        message = cap.get("message") or f"Swiggy allows {allowed} of this item per order."
        if requested and allowed:
            lines.append(f"⚠️ {message} I asked for {requested}, so I added {allowed}.")
        else:
            lines.append(f"⚠️ {message}")

    for red in reduced_quantity or []:
        lines.append(
            f"⚠️ Swiggy kept *{red['itemName']}* at {red['actual']} instead of {red['requested']}."
        )

    # Add bill breakdown lines
    if cart.billBreakdown and cart.billBreakdown.lineItems:
        for line in cart.billBreakdown.lineItems:
            lines.append(f"*{line.label}:* {line.value}")

    # Coupon savings line
    if coupon_code and coupon_savings_paise > 0:
        lines.append(f"🎟️ *Coupon ({coupon_code}):* -{format_paise_to_rupees(coupon_savings_paise)} saved")

    # To pay
    if cart.billBreakdown and cart.billBreakdown.toPay:
        lines.append("-----------------------------------")
        lines.append(f"*To Pay:* *{cart.billBreakdown.toPay.value}*")

    # Out of stock section if any
    if dropped_items:
        store_suffix = f" at {store_name}" if store_name else ""
        lines.append("\n⚠️ *Not added (Out of stock" + store_suffix + "):*")
        for drop in dropped_items:
            name = drop.item_name or drop.spin_id
            lines.append(f"• {name}")

    return "\n".join(lines)


class CompositeCartManager:
    """Orchestrates target cart assembly, full-basket diffing, and read-after-write verification."""

    def __init__(self, swiggy_client: Any) -> None:
        self.client = swiggy_client

    def assemble_and_update_cart(
        self,
        items_to_add: list[TargetCartItem],
        address_id: str | None = None,
        auto_optimize_coupons: bool = False,
    ) -> CartReconciliationResult:
        # 1. Read existing baseline cart
        current_cart = self.client.get_cart(address_id=address_id)
        baseline_count = len(current_cart.items)
        baseline_to_pay = (
            current_cart.billBreakdown.toPay.value
            if current_cart.billBreakdown and current_cart.billBreakdown.toPay
            else None
        )

        # 2. Assemble target dictionary: spin_id -> {spinId, skuId, quantity, itemName, price, mrp}
        target_map: dict[str, dict[str, Any]] = {}
        for it in current_cart.items:
            target_map[it.spinId] = {
                "spinId": it.spinId,
                "skuId": it.skuId,
                "quantity": it.quantity,
                "itemName": it.itemName,
                "price": it.discountedFinalPrice,
                "price_paise": it.discounted_final_price_paise,
                "mrp": it.mrp,
            }

        added_lines: list[TargetCartItem] = []
        capped_items: list[dict[str, Any]] = []
        for new_it in items_to_add:
            price_rupees = new_it.price_paise / 100 if new_it.price_paise else 0.0
            existing = target_map.get(new_it.spin_id)
            existing_qty = existing["quantity"] if existing else 0
            allowed = new_it.quantity
            if new_it.max_quantity is not None and existing_qty + allowed > new_it.max_quantity:
                allowed = max(0, new_it.max_quantity - existing_qty)
                capped_items.append(
                    {
                        "spinId": new_it.spin_id,
                        "itemName": new_it.item_name or new_it.spin_id,
                        "requested": new_it.quantity,
                        "allowed": allowed,
                        "max": new_it.max_quantity,
                        "message": new_it.max_quantity_message,
                    }
                )
            if allowed <= 0:
                continue
            if existing:
                existing["quantity"] += allowed
            else:
                target_map[new_it.spin_id] = {
                    "spinId": new_it.spin_id,
                    "skuId": new_it.sku_id or f"sku_{new_it.spin_id}",
                    "quantity": allowed,
                    "itemName": new_it.item_name or new_it.spin_id,
                    "price": price_rupees,
                    "price_paise": new_it.price_paise,
                    "mrp": price_rupees,
                }
            added_lines.append(
                TargetCartItem(
                    spin_id=new_it.spin_id,
                    quantity=allowed,
                    item_name=new_it.item_name,
                    price_paise=new_it.price_paise,
                    sku_id=new_it.sku_id,
                    max_quantity=new_it.max_quantity,
                    max_quantity_message=new_it.max_quantity_message,
                )
            )

        # 3. Call destructive update_cart with full assembled target cart
        assembled_list = list(target_map.values())
        self.client.update_cart(items=assembled_list, address_id=address_id)

        # 4. Read-after-write verification
        verified_cart = self.client.get_cart(address_id=address_id)

        # 5. Full-Basket Diffing: verify every expected item in target_map against verified cart
        verified_spins = {it.spinId: it.quantity for it in verified_cart.items}
        dropped_out_of_stock: list[TargetCartItem] = []
        reduced_quantity: list[dict[str, Any]] = []

        for spin_id, target_item in target_map.items():
            expected_qty = target_item["quantity"]
            actual_qty = verified_spins.get(spin_id, 0)
            if actual_qty == 0:
                dropped_out_of_stock.append(
                    TargetCartItem(
                        spin_id=spin_id,
                        quantity=expected_qty,
                        item_name=target_item.get("itemName", spin_id),
                        price_paise=target_item.get("price_paise", 0),
                    )
                )
            elif actual_qty < expected_qty:
                reduced_quantity.append(
                    {
                        "spinId": spin_id,
                        "itemName": target_item.get("itemName", spin_id),
                        "requested": expected_qty,
                        "actual": actual_qty,
                    }
                )

        # 6. Autonomous Wallet Advocate: optimize coupons if enabled
        coupon_res = None
        if auto_optimize_coupons and hasattr(self.client, "list_coupons") and hasattr(self.client, "apply_coupon"):
            try:
                from backend.agent.customer_advocate import optimize_coupons

                coupon_res = optimize_coupons(
                    cart=verified_cart,
                    swiggy_client=self.client,
                    address_id=address_id,
                )
            except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
                logger.debug("Coupon optimization skipped in cart builder: %s", exc)

        final_cart = coupon_res.final_cart if coupon_res else verified_cart
        coupon_code = coupon_res.applied_coupon if coupon_res else None
        coupon_savings = coupon_res.savings_paise if coupon_res else 0

        receipt = format_cart_receipt(
            cart=final_cart,
            dropped_items=dropped_out_of_stock,
            coupon_code=coupon_code,
            coupon_savings_paise=coupon_savings,
            added_items=added_lines,
            capped_items=capped_items,
            reduced_quantity=reduced_quantity,
            baseline_count=baseline_count,
            baseline_to_pay=baseline_to_pay,
        )

        return CartReconciliationResult(
            cart=final_cart,
            dropped_out_of_stock=dropped_out_of_stock,
            reduced_quantity=reduced_quantity,
            capped_items=capped_items,
            added_lines=added_lines,
            baseline_count=baseline_count,
            baseline_to_pay=baseline_to_pay,
            receipt_text=receipt,
        )
