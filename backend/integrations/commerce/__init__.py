"""Commerce integration layer for Grocer (Spec §5.1, §28, & §38.9).

Provides the CommercePort abstraction decoupling customer replenishment from
the specific underlying delivery provider (Mock/Simulated vs Swiggy Instamart MCP).
"""
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.models import (
    DeliveryAddress,
    CommerceProductItem,
    ProductVariant,
    CartItemUpdate,
    CommerceCart,
    CartItem,
    PaymentOption,
    CommerceOrderResult,
    DeliveryTrackingStatus,
)
from backend.integrations.commerce.exceptions import (
    CommerceError,
    UnconfirmedCheckoutError,
    AddressNotServiceableError,
    ItemOutOfStockError,
    MinOrderNotMetError,
    CartExpiredError,
    ProviderAuthError,
    UpstreamTimeoutError,
)

__all__ = [
    "CommercePort",
    "DeliveryAddress",
    "CommerceProductItem",
    "ProductVariant",
    "CartItemUpdate",
    "CommerceCart",
    "CartItem",
    "PaymentOption",
    "CommerceOrderResult",
    "DeliveryTrackingStatus",
    "CommerceError",
    "UnconfirmedCheckoutError",
    "AddressNotServiceableError",
    "ItemOutOfStockError",
    "MinOrderNotMetError",
    "CartExpiredError",
    "ProviderAuthError",
    "UpstreamTimeoutError",
]