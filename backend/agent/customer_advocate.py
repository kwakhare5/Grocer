"""Customer Advocate Engine: Real-data proactive savings, coupon hunting, delivery fee thresholds, and zero-loss UX."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.agent.formatters import _format_inr
from backend.integrations.commerce.models import CommerceCart, Coupon, CouponApplyResult
from backend.integrations.commerce.port import CommercePort

logger = logging.getLogger("grocer.agent.customer_advocate")


class CustomerAdvocate:
    """Proactive customer champion ensuring best prices, zero fee waste, and optimal dark-store value."""

    def __init__(self, commerce: CommercePort) -> None:
        self.commerce = commerce

    async def optimize_cart(
        self,
        cart: CommerceCart,
        address_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Runs customer advocacy optimizations:
        1. Auto-apply the highest value applicable coupon from live Swiggy MCP.
        2. Identify delivery fee savings opportunities (e.g. adding a small staple to save delivery fee).
        3. Compute total savings achieved for the customer.
        """
        result: dict[str, Any] = {
            "coupon_applied": False,
            "coupon_code": None,
            "coupon_savings": 0.0,
            "delivery_savings_tip": None,
            "total_savings": 0.0,
            "staple_suggestions": [],
        }

        if not cart or not cart.items:
            return result

        # 1. Auto-Coupon Hunter
        try:
            coupons: list[Coupon] = await self.commerce.list_coupons(cart_id=cart.cart_id)
            applicable = [
                c for c in coupons
                if c.is_applicable
                and (c.min_cart_value is None or cart.item_total >= c.min_cart_value)
            ]
            if applicable:
                best_coupon = max(applicable, key=lambda c: float(c.discount_amount or 0.0))
                discount = float(best_coupon.discount_amount or 0.0)
                if discount > 0:
                    original_total = cart.grand_total
                    apply_res: CouponApplyResult = await self.commerce.apply_coupon(
                        code=best_coupon.code,
                        cart_id=cart.cart_id,
                    )
                    if apply_res.applied:
                        potential_new_total = max(0.0, round(cart.grand_total - discount, 2))
                        if potential_new_total <= original_total:
                            result["coupon_applied"] = True
                            result["coupon_code"] = best_coupon.code
                            result["coupon_savings"] = discount
                            cart.discount = round((cart.discount or 0.0) + discount, 2)
                            cart.grand_total = potential_new_total
                        else:
                            logger.info("Coupon %s increased grand total; discarded", best_coupon.code)
        except Exception as exc:
            logger.debug("Auto-coupon search skipped: %s", exc)

        # 2. Free Delivery Threshold Saver
        delivery_fee = float(cart.delivery_fee or 0.0)
        if delivery_fee > 0:
            threshold = float(cart.min_order_threshold or 199.0)
            if cart.item_total < threshold:
                delta = round(threshold - cart.item_total, 2)
                # If adding delta costs less than or roughly equal to delivery fee, highlight the net gain
                if 0 < delta <= max(delivery_fee * 1.5, 50.0):
                    staples = []
                    try:
                        frequent = await self.commerce.get_go_to_items(address_id=address_id or "")
                        for item in frequent:
                            for v in getattr(item, "variants", []):
                                if v.price and v.price <= delta * 1.5 and getattr(v, "in_stock", True) is not False:
                                    staples.append({
                                        "name": v.name,
                                        "price": v.price,
                                        "formatted_price": _format_inr(v.price),
                                    })
                                    break
                            if len(staples) >= 2:
                                break
                    except Exception as exc:
                        logger.debug("Failed to fetch staple recommendations: %s", exc)

                    net_savings = round(delivery_fee - delta, 2)
                    if net_savings > 0:
                        tip = f"Adding {_format_inr(delta)} more unlocks FREE delivery (saving you {_format_inr(net_savings)} net)!"
                    else:
                        tip = f"Adding {_format_inr(delta)} more unlocks FREE delivery (saves {_format_inr(delivery_fee)} delivery fee)!"

                    if staples:
                        staple_names = " or ".join(f"{s['name']} ({s['formatted_price']})" for s in staples)
                        tip += f" Suggestions: {staple_names}."

                    result["delivery_savings_tip"] = tip
                    result["staple_suggestions"] = staples

        # 3. Total Savings Badge
        total_saved = round((cart.discount or 0.0), 2)
        result["total_savings"] = total_saved
        return result
