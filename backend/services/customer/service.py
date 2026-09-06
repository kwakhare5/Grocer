"""Consumer commerce service — temporary cleanroom implementation.

This module deliberately contains only the provider-facing operations needed by
GROCER's consumer experience. It does not own store inventory, suppliers,
risk, forecasting, recommendations, or simulation state.
"""

from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.models import (
    Cart,
    CommerceOrderResult,
    CommerceProduct,
    PaymentOption,
)
from backend.integrations.commerce.port import CommercePort


class CustomerService:
    """Thin application service over the consumer CommercePort."""

    def __init__(self, commerce: Optional[CommercePort] = None) -> None:
        self.commerce = commerce or get_commerce_adapter()

    def get_addresses(self):
        return self.commerce.get_addresses()

    def get_go_to_items(self):
        return self.commerce.get_go_to_items()

    def search_products(self, query: str, limit: int = 20):
        return self.commerce.search_products(query, limit=limit)

    def get_cart(self) -> Cart:
        return self.commerce.get_cart()

    def update_cart(self, items):
        return self.commerce.update_cart(items)

    def clear_cart(self) -> Cart:
        return self.commerce.clear_cart()

    def get_payment_options(self) -> list[PaymentOption]:
        return self.commerce.get_payment_options()

    def checkout(self, *, explicit_confirmation: bool) -> CommerceOrderResult:
        return self.commerce.checkout(explicit_confirmation=explicit_confirmation)

    def track_order(self, order_id: str):
        return self.commerce.track_order(order_id)
