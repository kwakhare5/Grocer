"""Canonical exception taxonomy for CommercePort and Swiggy Instamart integration."""
from __future__ import annotations


class CommerceError(Exception):
    """Base exception for all commerce adapter failures."""
    def __init__(self, message: str, provider: str = "commerce", code: str = "COMMERCE_ERROR"):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.code = code


class UnconfirmedCheckoutError(CommerceError):
    """Raised when checkout is attempted without explicit human/user confirmation.

    In accordance with Spec §28.3 & §39.15, consequential actions require explicit
    confirmation to prevent unintended production charges or inventory mutations.
    """
    def __init__(self, message: str = "Checkout requires explicit customer confirmation."):
        super().__init__(message=message, code="UNCONFIRMED_CHECKOUT")


class AddressNotServiceableError(CommerceError):
    """Raised when the commerce provider cannot serve a delivery address."""
    def __init__(self, address_id: str):
        super().__init__(
            message=f"Address {address_id} is not currently serviceable.",
            code="ADDRESS_NOT_SERVICEABLE",
        )
        self.address_id = address_id


class ItemOutOfStockError(CommerceError):
    """Raised when an item or variant requested in update_cart is not in stock."""
    def __init__(self, spin_id: str, available_quantity: int = 0):
        super().__init__(
            message=f"Item variant {spin_id} is out of stock (available: {available_quantity}).",
            code="ITEM_OUT_OF_STOCK",
        )
        self.spin_id = spin_id
        self.available_quantity = available_quantity


class MinOrderNotMetError(CommerceError):
    """Raised when cart grand total is below minimum order threshold."""
    def __init__(self, current_total: float, min_required: float = 99.0):
        super().__init__(
            message=f"Cart total ₹{current_total:.2f} is below the minimum order threshold of ₹{min_required:.2f}.",
            code="MIN_ORDER_NOT_MET",
        )
        self.current_total = current_total
        self.min_required = min_required


class CartExpiredError(CommerceError):
    """Raised when the session or cart has timed out."""
    def __init__(self, cart_id: str):
        super().__init__(
            message=f"Cart {cart_id} has expired. Please rebuild your cart.",
            code="CART_EXPIRED",
        )
        self.cart_id = cart_id


class ProviderAuthError(CommerceError):
    """Raised on authentication or token expiration from provider MCP endpoint (HTTP 401, RPC -32001)."""
    def __init__(self, message: str = "Authentication failed with upstream commerce provider."):
        super().__init__(message=message, code="UNAUTHENTICATED")


class ProviderSessionRevokedError(ProviderAuthError):
    """Raised when the session has been revoked server-side (HTTP 419)."""
    def __init__(self, message: str = "Swiggy session has been revoked. Full re-authentication required."):
        super().__init__(message=message)
        self.code = "SESSION_REVOKED"


class UpstreamTimeoutError(CommerceError):
    """Raised on upstream provider 504 gateway timeout."""
    def __init__(self, message: str = "Upstream commerce provider timed out."):
        super().__init__(message=message, code="UPSTREAM_TIMEOUT")


class OrderStateUnknownError(CommerceError):
    """Raised when checkout failed ambiguously (5xx/timeout) and order verification is pending."""
    def __init__(self, message: str = "Checkout status unknown. Verification required before retrying."):
        super().__init__(message=message, code="ORDER_STATE_UNKNOWN")
