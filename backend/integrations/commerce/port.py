"""Abstract interface for grocery commerce adapters.

Enforces clean architectural boundary: consumer grocery ordering and basket
management interact with external quick-commerce systems (or local
simulation) solely through this port.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Optional

from backend.integrations.commerce.models import (
    AddressRecommendation,
    CartItemUpdate,
    CommerceCart,
    CommerceOrderResult,
    CommerceProductItem,
    Coupon,
    CouponApplyResult,
    DeliveryAddress,
    DeliveryStatusResult,
    DeliveryTrackingStatus,
    ErrorReportResult,
    OrderDetails,
    OrderSummary,
    PaymentOption,
    PaymentStatusResult,
)

SWIGGY_CUSTOMER_CARE_PHONE = "080-67466729" 


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
        self, order_id: str, address_id: Optional[str] = None
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
        """Fetch rich real-time tracking for an active order."""
        raise NotImplementedError

    @abstractmethod
    async def create_address(
        self,
        customer_id: str,
        label: str,
        street: str,
        area: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        phone_number: Optional[str] = None,
        landmark: Optional[str] = None,
        address_tag: Optional[str] = None,
    ) -> DeliveryAddress:
        """Create a new delivery address for the customer."""
        raise NotImplementedError

    @abstractmethod
    async def delete_address(self, address_id: str) -> bool:
        """Delete a saved delivery address."""
        raise NotImplementedError

    @abstractmethod
    async def list_coupons(self, cart_id: Optional[str] = None) -> list[Coupon]:
        """Fetch available coupons for current active cart."""
        raise NotImplementedError

    @abstractmethod
    async def apply_coupon(
        self, code: str, cart_id: Optional[str] = None
    ) -> CouponApplyResult:
        """Apply a coupon code to the active cart."""
        raise NotImplementedError

    @abstractmethod
    async def recommend_address(
        self, latitude: Optional[float] = None, longitude: Optional[float] = None
    ) -> AddressRecommendation:
        """Recommend best delivery address based on location or order history."""
        raise NotImplementedError

    @abstractmethod
    async def report_error(
        self, report_id: str, context: Optional[dict[str, Any]] = None
    ) -> ErrorReportResult:
        """Submit diagnostic context for a provider error."""
        raise NotImplementedError

    @contextmanager
    def customer_scope(self, customer_id: str) -> Iterator[None]:
        """Bind provider calls to one customer for the current execution context."""
        del customer_id
        yield
