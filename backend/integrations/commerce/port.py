"""Abstract interface for grocery commerce adapters (Spec §5.1, §28.1).

Enforces clean architectural boundary: internal dark store replenishment
and customer reordering interact with external quick-commerce systems (or local
simulation) solely through this port.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Optional

from backend.integrations.commerce.models import (
    DeliveryAddress,
    CommerceProductItem,
    CartItemUpdate,
    CommerceCart,
    PaymentOption,
    CommerceOrderResult,
    DeliveryTrackingStatus,
    PaymentStatusResult,
    DeliveryStatusResult,
    OrderDetails,
    OrderSummary,
)


class CommercePort(ABC):
    """Abstract port for commerce provider operations."""

    @abstractmethod
    async def get_addresses(self, customer_id: str) -> list[DeliveryAddress]:
        """Fetch saved delivery addresses for customer."""
        raise NotImplementedError

    @abstractmethod
    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        """Fetch frequently ordered staple items available for this address."""
        raise NotImplementedError

    @abstractmethod
    async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
        """Search products available at delivery address."""
        raise NotImplementedError

    @abstractmethod
    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        """Fetch active cart with items and bill breakdown."""
        raise NotImplementedError

    @abstractmethod
    async def update_cart(
        self, items: list[CartItemUpdate], cart_id: Optional[str] = None, address_id: Optional[str] = None
    ) -> CommerceCart:
        """Update or replace cart items with given variants and quantities."""
        raise NotImplementedError

    @abstractmethod
    async def clear_cart(self, cart_id: Optional[str] = None) -> bool:
        """Remove all items from cart."""
        raise NotImplementedError

    @abstractmethod
    async def get_payment_options(
        self, cart_id: Optional[str] = None, address_id: Optional[str] = None
    ) -> list[PaymentOption]:
        """Fetch available payment methods (UPI, Cash on Delivery)."""
        raise NotImplementedError

    @abstractmethod
    async def checkout(
        self,
        cart_id: str,
        payment_method: str = "UPI",
        explicit_confirmation: bool = False,
        address_id: Optional[str] = None,
        payment_option_id: Optional[str] = None,
        payment_option_kind: Optional[str] = None,
    ) -> CommerceOrderResult:
        """Place and confirm order.

        CRITICAL: Must raise UnconfirmedCheckoutError if explicit_confirmation is False.
        """
        raise NotImplementedError

    @abstractmethod
    async def check_payment_status(
        self, paas_id: str, order_id: Optional[str] = None
    ) -> PaymentStatusResult:
        """Observe a pending payment without assuming that an order is placed."""
        raise NotImplementedError

    @abstractmethod
    async def confirm_order(self, order_id: str, paas_id: str) -> CommerceOrderResult:
        """Confirm an order only after terminal successful payment."""
        raise NotImplementedError

    @abstractmethod
    async def get_orders(
        self, count: int = 10, active_only: bool = False
    ) -> list[OrderSummary]:
        """Return recent provider orders for order lookup and history."""
        raise NotImplementedError

    @abstractmethod
    async def get_order_details(self, order_id: str) -> OrderDetails:
        """Return provider facts for one existing order."""
        raise NotImplementedError

    @abstractmethod
    async def get_delivery_status(
        self, order_id: str, address_id: str
    ) -> DeliveryStatusResult:
        """Return one structured delivery-status observation."""
        raise NotImplementedError

    @abstractmethod
    async def track_order(
        self,
        order_id: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> DeliveryTrackingStatus:
        """Fetch rich real-time tracking when delivery coordinates are available."""
        raise NotImplementedError

    @contextmanager
    def customer_scope(self, customer_id: str) -> Iterator[None]:
        """Bind provider calls to one customer for the current execution context."""
        del customer_id
        yield
