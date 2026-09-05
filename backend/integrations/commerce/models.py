"""Domain models for the CommercePort abstraction layer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field


class DeliveryAddress(BaseModel):
    """Customer delivery destination."""
    id: str
    label: str = "Home"
    street: str
    city: str = "Mumbai"
    postal_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_serviceable: bool = True


class ProductVariant(BaseModel):
    """SKU-level variant with provider-specific spinId."""
    spin_id: str
    name: str
    pack_size: str
    price: float
    mrp: float
    in_stock: bool = True


class CommerceProductItem(BaseModel):
    """Catalogue product item containing one or more pack-size variations."""
    product_id: str
    name: str
    category: str
    variants: list[ProductVariant] = Field(default_factory=list)
    image_url: Optional[str] = None


class CartItemUpdate(BaseModel):
    """Request to modify quantity of a variant in the cart."""
    spin_id: str
    quantity: int = Field(ge=0)


class CartItem(BaseModel):
    """Item present in active commerce cart."""
    spin_id: str
    name: str
    pack_size: str
    unit_price: float
    quantity: int
    total_price: float


class CommerceCart(BaseModel):
    """Active customer cart with bill breakdown."""
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


class PaymentOption(BaseModel):
    """Available payment method."""
    method: Literal["UPI", "COD"]
    label: str
    is_available: bool = True
    description: Optional[str] = None


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


class DeliveryTrackingStatus(BaseModel):
    """Live status and ETA of an in-flight order."""
    order_id: str
    status: Literal["ORDER_CONFIRMED", "PACKING", "OUT_FOR_DELIVERY", "DELIVERED"]
    eta_minutes: int
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))