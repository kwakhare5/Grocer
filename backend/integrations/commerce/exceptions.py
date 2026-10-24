"""Canonical exception taxonomy for CommercePort and Swiggy Instamart integration."""
from __future__ import annotations


class CommerceError(Exception):
    """Base exception for all commerce adapter failures."""
    def __init__(
        self,
        message: str,
        provider: str = "commerce",
        code: str = "COMMERCE_ERROR",
        report_id: str | None = None,
        report_hint: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.code = code
        self.report_id = report_id
        self.report_hint = report_hint


class UnconfirmedCheckoutError(CommerceError):
    """Raised when checkout is attempted without explicit human/user confirmation.

    In accordance with Spec Section 28.3 & Section 39.15, consequential actions require explicit
    confirmation to prevent unintended production charges or inventory mutations.
    """
    def __init__(self, message: str = "Checkout requires explicit customer confirmation."):
        super().__init__(message=message, code="UNCONFIRMED_CHECKOUT")


class StoreClosedError(CommerceError):
    """Raised when the local dark store or pod is currently closed."""
    def __init__(self, message: str = "The local dark store is currently closed."):
        super().__init__(message=message, code="STORE_CLOSED")


class DarkStoreOfflineError(StoreClosedError):
    """Raised when the dark store pod is temporarily offline."""
    def __init__(self, message: str = "The dark store is temporarily offline."):
        super().__init__(message=message)
        self.code = "POD_OFFLINE"


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


class ProviderRateLimitedError(CommerceError):
    """Raised when the provider asks this customer to stop sending requests."""

    def __init__(self, retry_after_seconds: int | None = None):
        super().__init__("Swiggy is temporarily limiting requests.", provider="swiggy", code="RATE_LIMITED")
        self.retry_after_seconds = retry_after_seconds


class OrderStateUnknownError(CommerceError):
    """Raised when checkout failed ambiguously (5xx/timeout) and order verification is pending."""
    def __init__(self, message: str = "Checkout status unknown. Verification required before retrying."):
        super().__init__(message=message, code="ORDER_STATE_UNKNOWN")


class ProviderInternalError(CommerceError):
    """Raised on upstream provider internal error (JSON-RPC -32603)."""
    def __init__(self, message: str = "Upstream provider encountered an internal error.", report_id: str | None = None, report_hint: str | None = None):
        super().__init__(message=message, provider="swiggy", code="PROVIDER_INTERNAL_ERROR", report_id=report_id, report_hint=report_hint)


class CartChangedError(CommerceError):
    """Raised when cart contents, prices, or store inventory changed during checkout."""
    def __init__(self, message: str = "Cart state changed during checkout. Please review updated cart.", report_id: str | None = None, report_hint: str | None = None):
        super().__init__(message=message, provider="swiggy", code="CART_CHANGED", report_id=report_id, report_hint=report_hint)


class DuplicateOrderError(CommerceError):
    """Raised when upstream flags a possible duplicate order within short timeframe."""
    def __init__(self, message: str = "A matching order was recently placed. Explicit duplicate confirmation required."):
        super().__init__(message=message, provider="swiggy", code="DUPLICATE_ORDER")
