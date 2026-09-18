from __future__ import annotations

from typing import Optional

import pytest

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import (
    CartItemUpdate,
    CommerceCart,
    CommerceOrderResult,
    CommerceProductItem,
    DeliveryAddress,
    DeliveryTrackingStatus,
    PaymentOption,
)
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


class IncompleteLifecycleAdapter(CommercePort):
    """Adapter implementing shopping but falsely omitting lifecycle support."""

    async def get_addresses(self, customer_id: str) -> list[DeliveryAddress]:
        return []

    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        return []

    async def search_products(
        self, address_id: str, query: str
    ) -> list[CommerceProductItem]:
        return []

    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        raise AssertionError("not exercised")

    async def update_cart(
        self,
        items: list[CartItemUpdate],
        cart_id: Optional[str] = None,
        address_id: Optional[str] = None,
    ) -> CommerceCart:
        raise AssertionError("not exercised")

    async def clear_cart(self, cart_id: Optional[str] = None) -> bool:
        return True

    async def get_payment_options(
        self,
        cart_id: Optional[str] = None,
        address_id: Optional[str] = None,
    ) -> list[PaymentOption]:
        return []

    async def checkout(
        self,
        cart_id: str,
        payment_method: str = "UPI",
        explicit_confirmation: bool = False,
        address_id: Optional[str] = None,
        payment_option_id: Optional[str] = None,
        payment_option_kind: Optional[str] = None,
    ) -> CommerceOrderResult:
        raise AssertionError("not exercised")

    async def track_order(
        self,
        order_id: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> DeliveryTrackingStatus:
        raise AssertionError("not exercised")


def test_incomplete_lifecycle_adapter_cannot_instantiate() -> None:
    with pytest.raises(TypeError, match="abstract"):
        IncompleteLifecycleAdapter()


def test_real_commerce_adapters_satisfy_complete_port_contract() -> None:
    assert isinstance(MockCommerceAdapter(), CommercePort)
    assert isinstance(SwiggyMCPAdapter(), CommercePort)

