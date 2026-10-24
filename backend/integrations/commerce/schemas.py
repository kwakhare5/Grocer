"""Grocer v1.0 — Swiggy Instamart Pydantic Contract Schemas.

Strictly typed models for all 20 Swiggy Instamart MCP tools based on
official Swiggy Builders Club specifications (JSON-RPC 2.0 / MCP).
Zero mocks; validated directly against committed staging fixtures.
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ToolEnvelope(BaseModel, Generic[T]):
    """Standard Swiggy MCP tool response envelope."""
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[dict[str, Any]] = None


# 1. Address Models
class SavedAddress(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    addressLine: str
    phoneNumber: Optional[str] = None
    addressCategory: Optional[str] = None
    addressTag: Optional[str] = None


class AddressPagination(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasMore: bool


class AddressResolution(BaseModel):
    model_config = ConfigDict(extra="ignore")
    defaultAddressId: Optional[str] = None
    resolutionSource: str
    needsUserClarification: bool = False
    candidateAddressIds: List[str] = Field(default_factory=list)
    scoreUsed: Optional[float] = None


class GetAddressesData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    addresses: List[SavedAddress]
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
    unitLevelPrice: Optional[str] = None


class ProductVariation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    spinId: str
    skuId: str
    quantityDescription: str
    displayName: str
    brandName: Optional[str] = None
    price: ProductPrice
    isInStockAndAvailable: bool
    imageUrl: Optional[str] = None
    maxQuantity: Optional[int] = None
    maxQuantityMessage: Optional[str] = None


class SearchProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")
    displayName: str
    brand: Optional[str] = None
    inStock: bool
    isAvail: bool
    productId: str
    parentProductId: Optional[str] = None
    isPromoted: Optional[bool] = False
    variations: List[ProductVariation] = Field(default_factory=list)


class SearchProductsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    nextOffset: str = ""
    products: List[SearchProduct] = Field(default_factory=list)
    similarProducts: Optional[List[SearchProduct]] = Field(default_factory=list)


# 3. Cart & Bill Breakdown Models
class CartItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    spinId: str
    storeId: Optional[str] = None
    skuId: str
    productId: str
    itemName: str
    itemVariant: Optional[str] = None
    quantity: int
    isInStockAndAvailable: bool
    mrp: float
    discountedFinalPrice: float
    maxQuantity: Optional[int] = None


class BillLineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: str


class BillBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lineItems: List[BillLineItem]
    toPay: BillLineItem


class CartData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cartId: Optional[str] = None
    selectedAddress: Optional[str] = None
    cartTotalAmount: str
    items: List[CartItem] = Field(default_factory=list)
    billBreakdown: BillBreakdown
    availablePaymentMethods: Optional[List[str]] = Field(default_factory=list)
    reducedQuantityItems: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    removedOutOfStockItems: Optional[List[CartItem]] = Field(default_factory=list)


class ClearCartData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verified: Optional[bool] = None
    acknowledged: Optional[bool] = None


# 4. Coupon Models
class AvailableCoupon(BaseModel):
    model_config = ConfigDict(extra="ignore")
    couponCode: str
    title: str
    description: Optional[str] = None
    isApplicable: bool
    applicabilityStatus: str
    applicabilityMessage: Optional[str] = None
    offerId: Optional[str] = None


class ListCouponsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    availableCoupons: List[AvailableCoupon] = Field(default_factory=list)


# 5. Payment & Checkout Models
class PaymentMethodItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    groupName: Optional[str] = None
    displayName: Optional[str] = None
    kind: Optional[str] = None
    enabled: Optional[bool] = True


class PaymentOptionsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    platforms: Optional[dict[str, Any]] = None
    cod: Optional[dict[str, Any]] = None
    swiggyMoney: Optional[dict[str, Any]] = None
    allMethods: List[PaymentMethodItem] = Field(default_factory=list)
    paymentAmount: Optional[str] = None
    placeOrderToolName: str = "checkout"


class CheckoutData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    paymentMethod: str
    status: str
    transactionId: Optional[str] = None
    paasId: Optional[str] = None
    upiIntentUrl: Optional[str] = None
    bridgeUrl: Optional[str] = None
    isQrFlow: Optional[bool] = False
    pollingIntervalInMs: Optional[int] = 3000
    maxTimeToPollForInMs: Optional[int] = 300000
    addressId: Optional[str] = None
    cartTotal: Optional[float] = None
    deliveryAddress: Optional[str] = None
    deliveryLabel: Optional[str] = None


class PaymentStatusData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    paasId: str
    status: str
    terminal: bool
    isTerminalSuccess: bool
    isTerminalFailure: bool
    confirmed: Optional[bool] = None
    orderStatus: Optional[str] = None
    cartTotal: Optional[float] = None
    orderId: Optional[str] = None
    addressId: Optional[str] = None
    cartId: Optional[str] = None


class ConfirmOrderData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    paasId: Optional[str] = None
    orderStatus: Optional[str] = None
    result: str


# 6. Order History & Tracking Models
class OrderHistoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    status: str
    createdAt: str
    updatedAt: Optional[str] = None
    estimatedDeliveryTime: Optional[str] = None
    itemCount: int
    totalAmount: float
    deliveryAddress: Optional[dict[str, Any]] = None
    paymentMethod: Optional[str] = None
    orderType: Optional[str] = "INSTAMART"
    isActive: Optional[bool] = False
    storeName: Optional[str] = None
    items: List[dict[str, Any]] = Field(default_factory=list)


class OrdersListData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orders: List[OrderHistoryItem] = Field(default_factory=list)
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
    items: List[OrderDetailsItem] = Field(default_factory=list)
    bill: Optional[dict[str, Any]] = None


class DeliveryStatusData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    deliveryBy: Optional[int] = None
    serverNow: Optional[int] = None
    etaText: Optional[str] = None
    cancelled: Optional[bool] = False
    delivered: Optional[bool] = False
    statusText: Optional[str] = None
    pollIntervalSec: int = 15


class TrackOrderStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    statusMessage: str
    subStatusMessage: Optional[str] = None
    etaMinutes: Optional[int] = None
    etaText: Optional[str] = None


class TrackOrderData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    orderId: str
    orderTitle: str
    orderSubtitle: str
    status: TrackOrderStatus
    storeInfo: Optional[dict[str, Any]] = None
    deliveryInfo: Optional[dict[str, Any]] = None
    items: List[dict[str, Any]] = Field(default_factory=list)
    itemCount: int
    placedAt: Optional[str] = None
    paymentInfo: Optional[dict[str, Any]] = None
    mapInfo: Optional[dict[str, Any]] = None
    pollingIntervalSeconds: int = 10


class ReportErrorData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reportLink: str
    supportEmail: str
    summary: str
