"""Grocer v1.0 — Coupon guard: savings never change the basket."""

from __future__ import annotations

from backend.agent.customer_advocate import optimize_coupons
from backend.integrations.commerce.schemas import CartData, CartItem


def _item(spin: str, name: str, qty: int, price: float) -> CartItem:
    return CartItem(
        spinId=spin,
        skuId=f"sku_{spin}",
        productId=f"prod_{spin}",
        itemName=name,
        quantity=qty,
        isInStockAndAvailable=True,
        mrp=price,
        discountedFinalPrice=price,
    )


def _cart(items: list[CartItem], to_pay_paise: int) -> CartData:
    value = f"{to_pay_paise // 100}.{to_pay_paise % 100:02d}"
    return CartData(
        cartId="cart_test",
        cartTotalAmount=value,
        items=items,
        billBreakdown={
            "lineItems": [{"label": "Item Total", "value": f"₹{value}"}],
            "toPay": {"label": "To Pay", "value": f"₹{value}"},
        },
    )


class _Coupon:
    def __init__(self, code: str) -> None:
        self.couponCode = code
        self.isApplicable = True


class _CouponList:
    def __init__(self) -> None:
        self.availableCoupons = [_Coupon("SAVE50")]


class FakeCouponClient:
    def __init__(self, coupon_cart: CartData) -> None:
        self.coupon_cart = coupon_cart
        self.writes: list[list[dict]] = []

    def list_coupons(self, address_id: str | None = None) -> _CouponList:
        return _CouponList()

    def apply_coupon(self, code: str) -> CartData:
        return self.coupon_cart

    def update_cart(self, items: list[dict], address_id: str | None = None) -> None:
        self.writes.append(items)


def test_a_coupon_that_lowers_the_bill_is_kept():
    cart = _cart([_item("spin_milk", "Milk", 2, 70.0)], 15000)
    client = FakeCouponClient(_cart([_item("spin_milk", "Milk", 2, 70.0)], 12000))

    result = optimize_coupons(cart, client, "addr_01")

    assert result.applied_coupon == "SAVE50"
    assert result.savings_paise == 3000
    assert result.final_to_pay_paise == 12000


def test_a_coupon_that_changes_items_is_ignored():
    cart = _cart(
        [
            _item("spin_milk", "Milk", 2, 70.0),
            _item("spin_bread", "Bread", 1, 45.0),
        ],
        18500,
    )
    client = FakeCouponClient(_cart([_item("spin_milk", "Milk", 2, 70.0)], 12000))

    result = optimize_coupons(cart, client, "addr_01")

    assert result.applied_coupon is None
    assert result.savings_paise == 0
    assert result.final_to_pay_paise == 18500
    assert client.writes
