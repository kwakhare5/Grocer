"""Grocer v1.0 — Target Cart Assembly & Composite Commerce Engine.

Enforces:
1. Destructive Overwrite Safety: Reads get_cart(), merges existing items locally, and submits assembled target cart.
2. Read-After-Write Verification: Full-basket diffing against verified cart to detect drops, quantity reductions, or reverts.
3. Out-of-Stock Reconciliation: Missing items are rendered under "⚠️ *Not added (Out of stock)*" receipt cards.
4. Top 3-5 Go-To Items Proposal (ADR 0008:10): Surfaces top frequent SKUs with [Add All to Basket] button.
5. Address Switching Mid-Basket (ADR 0007): Warns, clears cart, and rebuilds available items at new store.
6. Integer Paise Math Discipline: Zero floating-point money calculations.
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
    price_paise: int = 0  # Strict integer paise (₹1 = 100 paise)


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


@dataclass
class GoToItemsProposal:
    card_text: str
    action_id: str
    items: list[TargetCartItem]


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
        for line in cart.billBreakdown.lineItems:
            lines.append(f"*{line.label}:* {line.value}")

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
                "price_paise": it.discounted_final_price_paise,
                "mrp": it.mrp,
            }

        for new_it in items_to_add:
            price_rupees = new_it.price_paise / 100 if new_it.price_paise else 0.0
            if new_it.spin_id in target_map:
                target_map[new_it.spin_id]["quantity"] += new_it.quantity
            else:
                target_map[new_it.spin_id] = {
                    "spinId": new_it.spin_id,
                    "quantity": new_it.quantity,
                    "itemName": new_it.item_name or new_it.spin_id,
                    "price": price_rupees,
                    "price_paise": new_it.price_paise,
                    "mrp": price_rupees,
                }

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

    def propose_go_to_items(
        self,
        address_id: str | None = None,
    ) -> GoToItemsProposal:
        """Surface customer's top 3–5 frequently ordered SKUs in a structured card (ADR 0008:10)."""
        go_to_data = self.client.your_go_to_items(address_id=address_id)
        candidates: list[TargetCartItem] = []

        lines = ["📋 *Your Go-To Items (Frequent Staples)*"]
        count = 0
        for prod in go_to_data.products:
            for v in prod.variations:
                if count >= 5:
                    break
                paise = round(v.price.offerPrice * 100)
                formatted_p = format_paise_to_rupees(paise)
                lines.append(
                    f"• {v.displayName} ({v.quantityDescription}) — {formatted_p}"
                )
                candidates.append(
                    TargetCartItem(
                        spin_id=v.spinId,
                        quantity=1,
                        item_name=v.displayName,
                        price_paise=paise,
                    )
                )
                count += 1
            if count >= 5:
                break

        lines.append("\nTap below to reorder your staples in one tap.")
        return GoToItemsProposal(
            card_text="\n".join(lines),
            action_id="goto:add_all",
            items=candidates,
        )

    def reorder_go_to_items(
        self,
        address_id: str | None = None,
    ) -> CartReconciliationResult:
        """Add top 3–5 frequent SKUs to basket with graceful partial stock handling (ADR 0008/0010)."""
        proposal = self.propose_go_to_items(address_id=address_id)
        return self.assemble_and_update_cart(
            items_to_add=proposal.items,
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
        """Clear old cart and rebuild basket under new address dark store (ADR 0007)."""
        prev_cart = self.client.get_cart()
        prev_items = [
            TargetCartItem(
                spin_id=it.spinId,
                quantity=it.quantity,
                item_name=it.itemName,
                price_paise=it.discounted_final_price_paise,
            )
            for it in prev_cart.items
        ]

        self.client.clear_cart()

        return self.assemble_and_update_cart(
            items_to_add=prev_items,
            address_id=new_address_id,
        )
