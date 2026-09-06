"""Pydantic API schemas for GROCER's consumer Intent + commerce boundary."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommerceAdapterInfoResponse(BaseModel):
    adapter_type: str
    endpoint: str
    mode: str


class CommerceDeliveryAddressResponse(BaseModel):
    id: str
    label: str
    street: str
    city: str
    postal_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_serviceable: bool


class CommerceProductVariantResponse(BaseModel):
    spin_id: str
    name: str
    pack_size: str
    price: float
    mrp: float
    in_stock: bool


class CommerceProductItemResponse(BaseModel):
    product_id: str
    name: str
    category: str
    variants: list[CommerceProductVariantResponse]
    image_url: Optional[str] = None


class CommerceCartItemResponse(BaseModel):
    spin_id: str
    name: str
    pack_size: str
    unit_price: float
    quantity: int
    total_price: float


class CommerceCartResponse(BaseModel):
    cart_id: str
    address_id: Optional[str] = None
    items: list[CommerceCartItemResponse] = Field(default_factory=list)
    item_total: float = 0.0
    delivery_fee: float = 0.0
    packaging_fee: float = 0.0
    discount: float = 0.0
    grand_total: float = 0.0
    is_serviceable: bool = True


class CartItemUpdatePayload(BaseModel):
    spin_id: str
    quantity: int = Field(ge=0)


class CommerceCartUpdateRequest(BaseModel):
    items: list[CartItemUpdatePayload]
    address_id: Optional[str] = None


class CommercePaymentOptionResponse(BaseModel):
    method: str
    label: str
    is_available: bool = True
    description: Optional[str] = None


class CommerceCheckoutRequest(BaseModel):
    payment_method: str = "UPI"
    explicit_confirmation: bool = False
    address_id: Optional[str] = None


class CommerceOrderResultResponse(BaseModel):
    order_id: str
    cart_id: str
    status: str
    items: list[CommerceCartItemResponse] = Field(default_factory=list)
    payment_method: str
    grand_total: float
    delivery_address: CommerceDeliveryAddressResponse
    placed_at: datetime
    tracking_url: Optional[str] = None


class CommerceTrackingResponse(BaseModel):
    order_id: str
    status: str
    eta_minutes: int
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    last_updated_at: datetime


class IntentChatRequest(BaseModel):
    session_id: str
    customer_id: str
    message: str = Field(min_length=1)
    address_id: Optional[str] = None


class BasketItemSchema(BaseModel):
    spin_id: str
    name: str
    pack_size: str
    quantity: int
    unit_price: float
    line_total: float
    substituted: bool = False


class BasketSummarySchema(BaseModel):
    cart_id: str
    items: list[BasketItemSchema] = Field(default_factory=list)
    item_total: float
    delivery_fee: float
    grand_total: float
    budget: Optional[float] = None
    within_budget: bool
    recovery_notes: list[str] = Field(default_factory=list)


class ClarificationOptionSchema(BaseModel):
    index: int
    spin_id: str
    name: str
    pack_size: str
    price: float
    score: float = 0.0


class IntentChatResponse(BaseModel):
    session_id: str
    conversation_state: str
    user_message: str
    basket_summary: Optional[BasketSummarySchema] = None
    clarification_options: Optional[list[ClarificationOptionSchema]] = None
    requires_confirmation: bool = False
    order_id: Optional[str] = None
    order_total: Optional[float] = None
    events: list[str] = Field(default_factory=list)


class IntentChoiceRequest(BaseModel):
    chosen_spin_id: str = Field(min_length=1)


class IntentConfirmRequest(BaseModel):
    explicit_confirmation: bool = False
    payment_method: str = "UPI"
    address_id: Optional[str] = None


class IntentSessionStateResponse(BaseModel):
    session_id: str
    customer_id: str
    conversation_state: str
    cart_id: Optional[str] = None
    turn_count: int
    has_pending_clarification: bool
    order_id: Optional[str] = None
    order_total: Optional[float] = None
    events: list[str] = Field(default_factory=list)
