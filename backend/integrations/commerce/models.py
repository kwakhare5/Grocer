"""Domain models for the CommercePort abstraction layer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field


class DeliveryAddress(BaseModel):
    """Customer delivery destination matching Swiggy get_addresses schema."""
    id: str
    label: str = "Home"
    street: str = ""
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_serviceable: bool = True
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
    in_stock: bool = True
    sku_id: Optional[str] = None
    offer_price: Optional[float] = None
    image_url: Optional[str] = None


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
    is_available: bool = True
    sku_id: Optional[str] = None
    mrp: Optional[float] = None
    product_id: Optional[str] = None
    max_quantity: Optional[int] = None


class CommerceCart(BaseModel):
    """Active customer cart with bill breakdown and serviceability."""
    cart_id: str
    address_id: Optional[str] = None
    items: list[CartItem] = Field(default_factory=list)
    item_total: float = 0.0
    delivery_fee: float = 0.0
    packaging_fee: float = 0.0
    discount: float = 0.0
    grand_total: float = 0.0
    is_serviceable: bool = True
    min_order_threshold: float = 99.0
    unserviceable_items: list[CartItem] = Field(default_factory=list)
    reduced_quantity_items: list[dict[str, Any]] = Field(default_factory=list)
    cart_absent: bool = False
    cart_warning: Optional[str] = None
    address_warning: Optional[str] = None
    available_payment_methods: list[str] = Field(default_factory=list)


class PaymentOption(BaseModel):
    """Available payment method."""
    method: Literal["UPI", "COD"]
    label: str
    is_available: bool = True
    description: Optional[str] = None
    id: Optional[str] = None
    kind: Optional[str] = None  # "intent" or "qr"


class CommerceOrderResult(BaseModel):
    """Consequential result of a confirmed checkout."""
    order_id: str
    cart_id: str
    status: Literal["ORDER_CONFIRMED", "PAYMENT_PENDING", "FAILED"] = "ORDER_CONFIRMED"
    items: list[CartItem] = Field(default_factory=list)
    payment_method: str
    grand_total: float
    delivery_address: DeliveryAddress
    placed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tracking_url: Optional[str] = None
    orders: list[dict[str, Any]] = Field(default_factory=list)
    order_count: int = 1
    success_count: int = 1
    failure_count: int = 0
    all_succeeded: bool = True
    paas_id: Optional[str] = None
    transaction_id: Optional[str] = None
    bridge_url: Optional[str] = None
    upi_intent_url: Optional[str] = None
    is_qr_flow: bool = False
    polling_interval_ms: Optional[int] = None
    max_time_to_poll_ms: Optional[int] = None


class DeliveryTrackingStatus(BaseModel):
    """Live status and ETA of an in-flight order."""
    order_id: str
    status: Literal["ORDER_CONFIRMED", "PACKING", "OUT_FOR_DELIVERY", "DELIVERED"]
    eta_minutes: int
    eta_text: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    status_message: Optional[str] = None
    store_name: Optional[str] = None
    polling_interval_seconds: int = 10
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))