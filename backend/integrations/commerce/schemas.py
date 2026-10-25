"""Grocer v1.0 — Swiggy Instamart Pydantic Contract Schemas.

Strictly typed models for all 20 Swiggy Instamart MCP tools based on
official Swiggy Builders Club specifications (JSON-RPC 2.0 / MCP).
Zero mocks; validated directly against committed staging fixtures.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ToolEnvelope(BaseModel, Generic[T]):
    """Standard Swiggy MCP tool response envelope."""

    model_config = ConfigDict(extra="ignore")
    success: bool
    data: T | None = None
    message: str | None = None
    error: dict[str, Any] | None = None


# 1. Address Models
class SavedAddress(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    addressLine: str
    phoneNumber: str | None = None
    addressCategory: str | None = None
    addressTag: str | None = None


class AddressPagination(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasMore: bool


class AddressResolution(BaseModel):
    model_config = ConfigDict(extra="ignore")
    defaultAddressId: str | None = None
    resolutionSource: str
    needsUserClarification: bool = False
    candidateAddressIds: list[str] = Field(default_factory=list)
    scoreUsed: float | None = None


class GetAddressesData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    addresses: list[SavedAddress]
    pagination: AddressPagination
    resolution: AddressResolution


class CreateAddressData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    addressId: str


class DeleteAddressData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    statusCode: int
    statusMessage: str


class RecommendAddressData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    latitude: float
    longitude: float
    formattedAddress: str


# 2. Catalog & Product Search Models
class ProductPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mrp: float
    offerPrice: float
    unitLevelPrice: str | None = None

    @property
    def mrp_paise(self) -> int:
        """Integer paise value of MRP (₹1 = 100 paise)."""
        return round(self.mrp * 100)

    @property
    def offer_price_paise(self) -> int:
        """Integer paise value of offer price (₹1 = 100 paise)."""
        return round(self.offerPrice * 100)


class ProductVariation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    spinId: str
    skuId: str
    quantityDescription: str
    displayName: str
    brandName: str | None = None
    price: ProductPrice
    isInStockAndAvailable: bool
    imageUrl: str | None = None
    maxQuantity: int | None = None
    maxQuantityMessage: str | None = None


class SearchProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")
    displayName: str
    brand: str | None = None
    inStock: bool
    isAvail: bool
    productId: str
    parentProductId: str | None = None
    isPromoted: bool | None = False
    variations: list[ProductVariation] = Field(default_factory=list)


class SearchProductsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    nextOffset: str = ""
    products: list[SearchProduct] = Field(default_factory=list)
    similarProducts: list[SearchProduct] | None = Field(default_factory=list)


# 3. Cart & Bill Breakdown Models
class CartItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    spinId: str
    storeId: str | None = None
    skuId: str
    productId: str
    itemName: str
    itemVariant: str | None = None
    quantity: int
    isInStockAndAvailable: bool
    mrp: float
    discountedFinalPrice: float
    maxQuantity: int | None = None

    @property
    def mrp_paise(self) -> int:
        """Integer paise value of MRP (₹1 = 100 paise)."""
        return round(self.mrp * 100)

    @property
    def discounted_final_price_paise(self) -> int:
        """Integer paise value of discounted price (₹1 = 100 paise)."""
        return round(self.discountedFinalPrice * 100)


class BillLineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: str


class BillBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lineItems: list[BillLineItem]
    toPay: BillLineItem


class CartData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cartId: str | None = None
    selectedAddress: str | None = None
    cartTotalAmount: str
    items: list[CartItem] = Field(default_factory=list)
    billBreakdown: BillBreakdown
    availablePaymentMethods: list[str] | None = Field(default_factory=list)
    reducedQuantityItems: list[dict[str, Any]] | None = Field(default_factory=list)
    removedOutOfStockItems: list[CartItem] | None = Field(default_factory=list)


class ClearCartData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verified: bool | None = None
    acknowledged: bool | None = None


# 4. Coupon Models
class AvailableCoupon(BaseModel):
    model_config = ConfigDict(extra="ignore")
    couponCode: str
    title: str
    description: str | None = None
    isApplicable: bool
    applicabilityStatus: str
    applicabilityMessage: str | None = None
    offerId: str | None = None


class ListCouponsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    availableCoupons: list[AvailableCoupon] = Field(default_factory=list)


# 5. Payment & Checkout Models
class PaymentMethodItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    groupName: str | None = None
    displayName: str | None = None
    kind: str | None = None
    enabled: bool | None = True


class PaymentOptionsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    platforms: dict[str, Any] | None = None
    cod: dict[str, Any] | None = None
    swiggyMoney: dict[str, Any] | None = None
    allMethods: list[PaymentMethodItem] = Field(default_factory=list)
    paymentAmount: str | None = None
    placeOrderToolName: str = "checkout"


class CheckoutData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    paymentMethod: str
    status: str
    transactionId: str | None = None
    paasId: str | None = None
    upiIntentUrl: str | None = None
    bridgeUrl: str | None = None
    isQrFlow: bool | None = False
    pollingIntervalInMs: int | None = 3000
    maxTimeToPollForInMs: int | None = 300000
    addressId: str | None = None
    cartTotal: float | None = None
    deliveryAddress: str | None = None
    deliveryLabel: str | None = None


class PaymentStatusData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    paasId: str
    status: str
    terminal: bool
    isTerminalSuccess: bool
    isTerminalFailure: bool
    confirmed: bool | None = None
    orderStatus: str | None = None
    cartTotal: float | None = None
    orderId: str | None = None
    addressId: str | None = None
    cartId: str | None = None


class ConfirmOrderData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    paasId: str | None = None
    orderStatus: str | None = None
    result: str


# 6. Order History & Tracking Models
class OrderHistoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    status: str
    createdAt: str
    updatedAt: str | None = None
    estimatedDeliveryTime: str | None = None
    itemCount: int
    totalAmount: float
    deliveryAddress: dict[str, Any] | None = None
    paymentMethod: str | None = None
    orderType: str | None = "INSTAMART"
    isActive: bool | None = False
    storeName: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def total_amount_paise(self) -> int:
        """Integer paise value of order total (₹1 = 100 paise)."""
        return round(self.totalAmount * 100)


class OrdersListData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orders: list[OrderHistoryItem] = Field(default_factory=list)
    hasMore: bool = False


class OrderDetailsItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    quantity: int
    finalPrice: float
    removed: bool = False


class OrderDetailsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    status: str
    totalBill: float
    hasRefunds: bool = False
    items: list[OrderDetailsItem] = Field(default_factory=list)
    bill: dict[str, Any] | None = None

    @property
    def total_bill_paise(self) -> int:
        """Integer paise value of total bill (₹1 = 100 paise)."""
        return round(self.totalBill * 100)


class DeliveryStatusData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    deliveryBy: int | None = None
    serverNow: int | None = None
    etaText: str | None = None
    cancelled: bool | None = False
    delivered: bool | None = False
    statusText: str | None = None
    pollIntervalSec: int = 15


class TrackOrderStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    statusMessage: str
    subStatusMessage: str | None = None
    etaMinutes: int | None = None
    etaText: str | None = None


class TrackOrderData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    orderTitle: str
    orderSubtitle: str
    status: TrackOrderStatus
    storeInfo: dict[str, Any] | None = None
    deliveryInfo: dict[str, Any] | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    itemCount: int
    placedAt: str | None = None
    paymentInfo: dict[str, Any] | None = None
    mapInfo: dict[str, Any] | None = None
    pollingIntervalSeconds: int = 10


class ReportErrorData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reportLink: str
    supportEmail: str
    summary: str
