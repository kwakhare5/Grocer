"""Grocer v1.0 — Target Cart Assembly & Composite Commerce Engine.

Enforces:
1. Destructive Overwrite Safety: Reads get_cart(), merges existing items locally, and submits assembled target cart.
2. Read-After-Write Verification: Calls get_cart() post-update to detect drops, quantity reductions, or reverts.
3. Out-of-Stock Reconciliation: Missing items are rendered under "⚠️ *Not added (Out of stock)*" receipt cards.
4. 1-Tap Reorder (ADR 0008 & 0010): Adds available frequent items and gracefully catches warehouse stockouts.
5. Address Switching Mid-Basket (ADR 0007): Warns, clears cart, and rebuilds available items at new store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.agent.candidate_evaluator import format_paise_to_rupees
from backend.integrations.commerce.schemas import CartData, CartItem


@dataclass
class TargetCartItem:
    spin_id: str
    quantity: int = 1
    item_name: str | None = None
    price: float = 0.0

    @property
    def price_paise(self) -> int:
        return round(self.price * 100)


@dataclass
class CartReconciliationResult:
    cart: CartData
    requested_items: list[TargetCartItem]
    added_items: list[CartItem]
    dropped_out_of_stock: list[TargetCartItem]
    reduced_quantity: list[dict[str, Any]] = field(default_factory=list)
    receipt_text: str = ""


@dataclass
class AddressSwitchPlan:
    has_active_basket: bool
    confirm_action_id: str
    prompt_text: str


def format_cart_receipt(
    cart: CartData,
    dropped_items: list[TargetCartItem] | None = None,
    store_name: str | None = None,
) -> str:
    """Format WhatsApp receipt card adhering to DESIGN.md Section 1."""
    lines: list[str] = []
    item_count = sum(it.quantity for it in cart.items)
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

    # Add bill breakdown lines
    if cart.billBreakdown and cart.billBreakdown.lineItems:
        for b_line in cart.billBreakdown.lineItems:
            lines.append(f"*{b_line.label}:* {b_line.value}")

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
    """Orchestrates target cart assembly and read-after-write verification."""

    def __init__(self, swiggy_client: Any) -> None:
        self.client = swiggy_client

    def assemble_and_update_cart(
        self,
        items_to_add: list[TargetCartItem],
        address_id: str | None = None,
    ) -> CartReconciliationResult:
        # 1. Read existing baseline cart
        current_cart = self.client.get_cart(address_id=address_id)

        # 2. Assemble target dictionary: spin_id -> {spinId, quantity, itemName, price, mrp}
        target_map: dict[str, dict[str, Any]] = {}
        for it in current_cart.items:
            target_map[it.spinId] = {
                "spinId": it.spinId,
                "quantity": it.quantity,
                "itemName": it.itemName,
                "price": it.discountedFinalPrice,
                "mrp": it.mrp,
            }

        for new_it in items_to_add:
            if new_it.spin_id in target_map:
                target_map[new_it.spin_id]["quantity"] += new_it.quantity
            else:
                target_map[new_it.spin_id] = {
                    "spinId": new_it.spin_id,
                    "quantity": new_it.quantity,
                    "itemName": new_it.item_name or new_it.spin_id,
                    "price": new_it.price,
                    "mrp": new_it.price,
                }

        # 3. Call destructive update_cart with full target cart
        assembled_list = list(target_map.values())
        self.client.update_cart(items=assembled_list, address_id=address_id)

        # 4. Read-after-write verification
        verified_cart = self.client.get_cart(address_id=address_id)

        # 5. Diff requested against verified
        verified_spins = {it.spinId: it.quantity for it in verified_cart.items}
        dropped_out_of_stock: list[TargetCartItem] = []
        reduced_quantity: list[dict[str, Any]] = []

        for req in items_to_add:
            actual_qty = verified_spins.get(req.spin_id, 0)
            if actual_qty == 0:
                dropped_out_of_stock.append(req)
            elif actual_qty < req.quantity:
                reduced_quantity.append(
                    {
                        "spinId": req.spin_id,
                        "requested": req.quantity,
                        "actual": actual_qty,
                    }
                )

        receipt = format_cart_receipt(
            cart=verified_cart,
            dropped_items=dropped_out_of_stock,
        )

        return CartReconciliationResult(
            cart=verified_cart,
            requested_items=items_to_add,
            added_items=verified_cart.items,
            dropped_out_of_stock=dropped_out_of_stock,
            reduced_quantity=reduced_quantity,
            receipt_text=receipt,
        )

    def reorder_go_to_items(
        self,
        address_id: str | None = None,
    ) -> CartReconciliationResult:
        """Fetch past frequent items via your_go_to_items and add available SKUs (ADR 0008/0010)."""
        go_to_data = self.client.your_go_to_items(address_id=address_id)
        candidates_to_add: list[TargetCartItem] = []

        for prod in go_to_data.products:
            for v in prod.variations:
                candidates_to_add.append(
                    TargetCartItem(
                        spin_id=v.spinId,
                        quantity=1,
                        item_name=v.displayName,
                        price=v.price.offerPrice,
                    )
                )

        return self.assemble_and_update_cart(
            items_to_add=candidates_to_add,
            address_id=address_id,
        )

    def plan_address_switch(
        self,
        new_address_id: str,
        current_address_name: str = "",
        new_address_name: str = "",
    ) -> AddressSwitchPlan:
        """Warn user about dark store inventory change when switching address mid-basket (ADR 0007)."""
        current_cart = self.client.get_cart()
        has_items = bool(current_cart.items)

        prompt = (
            f"You have items in your basket. Changing delivery address to {new_address_name} "
            f"switches to a different dark store where item availability and prices may vary. "
            f"Would you like to rebuild your basket at the new location?"
            if has_items
            else f"Switching delivery address to {new_address_name}."
        )

        return AddressSwitchPlan(
            has_active_basket=has_items,
            confirm_action_id=f"switch_rebuild:{new_address_id}",
            prompt_text=f"{prompt}\n[Switch & Rebuild Basket] [Keep Current Address]",
        )

    def execute_address_switch(
        self,
        new_address_id: str,
    ) -> CartReconciliationResult:
        """Clear old cart and attempt to rebuild basket under new address dark store."""
        prev_cart = self.client.get_cart()
        prev_items = [
            TargetCartItem(
                spin_id=it.spinId,
                quantity=it.quantity,
                item_name=it.itemName,
                price=it.discountedFinalPrice,
            )
            for it in prev_cart.items
        ]

        # Clear cart at previous store
        self.client.clear_cart()

        # Rebuild at new store
        return self.assemble_and_update_cart(
            items_to_add=prev_items,
            address_id=new_address_id,
        )
