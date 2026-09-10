"""Domain models for the CommercePort abstraction layer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field


class DeliveryAddress(BaseModel):
    """Customer delivery destination matching Swiggy get_addresses schema."""
    id: str
    label: str = ""
    street: str = ""
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_serviceable: Optional[bool] = None
    phone_number: Optional[str] = None
    address_category: Optional[str] = None
    address_tag: Optional[str] = None


class ProductVariant(BaseModel):
    """SKU-level variant with provider-specific spinId and skuId."""
    spin_id: str
    name: str
    pack_size: str
    price: float
    mrp: float
    in_stock: Optional[bool] = None
    sku_id: Optional[str] = None
    offer_price: Optional[float] = None
    image_url: Optional[str] = None
    max_quantity: Optional[int] = None
    max_quantity_message: Optional[str] = None


class CommerceProductItem(BaseModel):
    """Catalogue product item containing one or more pack-size variations."""
    product_id: str
    name: str
    category: str
    variants: list[ProductVariant] = Field(default_factory=list)
    image_url: Optional[str] = None
    brand: Optional[str] = None
    similar_products: list[CommerceProductItem] = Field(default_factory=list)


class CartItemUpdate(BaseModel):
    """Request to modify quantity of a variant in the cart."""
    spin_id: str
    quantity: int = Field(ge=0)
    sku_id: Optional[str] = None


class CartItem(BaseModel):
    """Item present in active commerce cart."""
    spin_id: str
    name: str
    pack_size: str
    unit_price: float
    quantity: int
    total_price: float
    is_available: Optional[bool] = None
    sku_id: Optional[str] = None
    mrp: Optional[float] = None
    product_id: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    max_quantity: Optional[int] = None
    max_quantity_message: Optional[str] = None


class CommerceCart(BaseModel):
    """Active customer cart with bill breakdown and serviceability."""
    cart_id: Optional[str] = None
    address_id: Optional[str] = None
    items: list[CartItem] = Field(default_factory=list)
    item_total: float = 0.0
    delivery_fee: float = 0.0
    packaging_fee: float = 0.0
    discount: float = 0.0
    grand_total: float = 0.0
    is_serviceable: Optional[bool] = None
    min_order_threshold: float = 99.0
    unserviceable_items: list[CartItem] = Field(default_factory=list)
    reduced_quantity_items: list[dict[str, Any]] = Field(default_factory=list)
    cart_absent: Optional[bool] = None
    cart_warning: Optional[str] = None
    address_warning: Optional[str] = None
    available_payment_methods: list[str] = Field(default_factory=list)


class PaymentOption(BaseModel):
    """Available payment method."""
    method: str
    label: str
    is_available: bool = True
    description: Optional[str] = None
    id: Optional[str] = None
    kind: Optional[str] = None  # "intent" or "qr"


class OrderChildResult(BaseModel):
    """One provider child order in a potentially multi-store checkout."""

    order_id: Optional[str] = None
    status: str = "ORDER_STATE_UNKNOWN"
    raw_status: Optional[str] = None
    success: Optional[bool] = None
    grand_total: Optional[float] = None
    error: Optional[str] = None


class PaymentStatusResult(BaseModel):
    """Normalized result of the provider's payment-status observation."""

    paas_id: str
    order_id: Optional[str] = None
    transaction_id: Optional[str] = None
    status: Optional[str] = None
    normalized_status: Literal[
        "PAYMENT_PENDING", "PAYMENT_CONFIRMED", "PAYMENT_FAILED", "PAYMENT_UNKNOWN"
    ] = "PAYMENT_UNKNOWN"
    terminal: bool = False
    is_terminal_success: bool = False
    is_terminal_failure: bool = False
    confirmed: bool = False
    order_status: Optional[str] = None


class CommerceOrderResult(BaseModel):
    """Consequential result of a confirmed checkout."""
    order_id: Optional[str] = None
    cart_id: Optional[str] = None
    status: Literal[
        "PAYMENT_PENDING",
        "PAYMENT_CONFIRMED",
        "ORDER_PLACED",
        "PARTIAL_ORDER",
        "ORDER_STATE_UNKNOWN",
        "FAILED",
    ] = "ORDER_STATE_UNKNOWN"
    raw_status: Optional[str] = None
    items: list[CartItem] = Field(default_factory=list)
    payment_method: Optional[str] = None
    grand_total: Optional[float] = None
    delivery_address: Optional[DeliveryAddress] = None
    placed_at: Optional[datetime] = None
    tracking_url: Optional[str] = None
    orders: list[OrderChildResult] = Field(default_factory=list)
    order_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    all_succeeded: bool = False
    paas_id: Optional[str] = None
    transaction_id: Optional[str] = None
    bridge_url: Optional[str] = None
    upi_intent_url: Optional[str] = None
    is_qr_flow: bool = False
    polling_interval_ms: Optional[int] = None
    max_time_to_poll_ms: Optional[int] = None
    provider_message: Optional[str] = None


class TrackingLocation(BaseModel):
    """Provider-neutral geographic point returned by order tracking."""

    latitude: float
    longitude: float


class TrackingLineItem(BaseModel):
    """Provider-returned item summary for a tracked order."""

    name: str
    quantity: int
    price: Optional[str] = None


class DeliveryTrackingStatus(BaseModel):
    """Live status and ETA of an in-flight order."""

    order_id: str
    status: Literal[
        "UNKNOWN",
        "ORDER_PLACED",
        "PACKING",
        "RIDER_ASSIGNED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
        "CANCELLED",
    ] = "UNKNOWN"
    raw_status: Optional[str] = None
    sub_status_message: Optional[str] = None
    eta_minutes: Optional[int] = None
    eta_text: Optional[str] = None
    order_title: Optional[str] = None
    order_subtitle: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    status_message: Optional[str] = None
    store_name: Optional[str] = None
    store_address: Optional[str] = None
    delivery_address_label: Optional[str] = None
    delivery_address: Optional[str] = None
    items: list[TrackingLineItem] = Field(default_factory=list)
    item_count: Optional[int] = None
    placed_at: Optional[str] = None
    payment_message: Optional[str] = None
    payment_amount: Optional[str] = None
    store_location: Optional[TrackingLocation] = None
    store_annotation: Optional[str] = None
    delivery_location: Optional[TrackingLocation] = None
    delivery_annotation: Optional[str] = None
    rider_location: Optional[TrackingLocation] = None
    polling_interval_seconds: Optional[int] = None
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderLineItem(BaseModel):
    """Provider-returned item facts from an existing order."""

    name: str
    quantity: int
    item_id: Optional[str] = None
    final_price: Optional[float] = None
    removed: Optional[bool] = None


class OrderSummary(BaseModel):
    """One order-history entry with unknown provider fields left nullable."""

    order_id: str
    raw_status: Optional[str] = None
    normalized_status: str = "ORDER_STATE_UNKNOWN"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    estimated_delivery_time: Optional[str] = None
    item_count: Optional[int] = None
    total_amount: Optional[float] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    refund_status: Optional[str] = None
    order_type: Optional[str] = None
    is_active: Optional[bool] = None
    status_message: Optional[str] = None
    store_name: Optional[str] = None
    address_id: Optional[str] = None
    items: list[OrderLineItem] = Field(default_factory=list)


class OrderBillLine(BaseModel):
    name: str
    amount: str


class OrderDetails(BaseModel):
    """Detailed provider order response without inferred commerce facts."""

    order_id: str
    raw_status: Optional[str] = None
    normalized_status: str = "ORDER_STATE_UNKNOWN"
    total_bill: Optional[float] = None
    has_refunds: Optional[bool] = None
    items: list[OrderLineItem] = Field(default_factory=list)
    bill_lines: list[OrderBillLine] = Field(default_factory=list)
    grand_total_text: Optional[str] = None


class DeliveryStatusResult(BaseModel):
    """Structured delivery refresh returned by get_delivery_status."""

    order_id: str
    delivery_by_ms: Optional[int] = None
    server_now_ms: Optional[int] = None
    eta_text: Optional[str] = None
    cancelled: Optional[bool] = None
    delivered: Optional[bool] = None
    status_text: Optional[str] = None
    poll_interval_sec: Optional[int] = None
