"""Pydantic v2 response schemas for GROCER v2 API.

Covers: stores, products, inventory, batches, forecasts, events.
All schemas use ConfigDict for v2-style config.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Store schemas
# ---------------------------------------------------------------------------


class StoreResponse(BaseSchema):
    store_id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    operating_status: str


class StoreDetailResponse(StoreResponse):
    pass  # extend later for nested data


# ---------------------------------------------------------------------------
# Product schemas
# ---------------------------------------------------------------------------


class ProductResponse(BaseSchema):
    product_id: uuid.UUID
    name: str
    category: str
    unit: str
    shelf_life_hours: int
    base_price: float
    substitution_group: Optional[str] = None


class ProductDetailResponse(ProductResponse):
    supplier_id: uuid.UUID


# ---------------------------------------------------------------------------
# Inventory / Batch schemas
# ---------------------------------------------------------------------------


class InventoryItemResponse(BaseSchema):
    product_id: uuid.UUID
    product_name: str
    category: str
    quantity: int
    unit: str


class BatchResponse(BaseSchema):
    batch_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    received_at: datetime
    expires_at: datetime
    hours_remaining: float


class StoreInventoryResponse(BaseModel):
    store_id: uuid.UUID
    store_name: str
    inventory: list[InventoryItemResponse]
    batches: list[BatchResponse]


# ---------------------------------------------------------------------------
# Forecast schemas
# ---------------------------------------------------------------------------


class ForecastResponse(BaseSchema):
    forecast_id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    forecast_window_hours: int
    predicted_demand: float
    confidence: float
    model_name: str
    created_at: datetime


class ForecastGenerateRequest(BaseModel):
    horizon_hours: Optional[int] = 24
    horizons: Optional[list[int]] = None
    store_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None



class ForecastEvaluationResponse(BaseModel):
    model_name: str
    mae: float
    rmse: float
    mape: float
    n_samples: int


class ForecastSummaryResponse(BaseModel):
    store_id: uuid.UUID
    product_id: uuid.UUID
    model_name: str
    predicted_demand: float
    confidence: float
    forecast_window_hours: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Risk schemas
# ---------------------------------------------------------------------------


class RiskResponse(BaseSchema):
    risk_id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    risk_type: str
    severity: str
    probability: float
    expected_time: datetime
    status: str
    created_at: datetime


class RiskEvaluateResponse(BaseModel):
    risks_detected: int


class RiskResolveResponse(BaseModel):
    risk_id: uuid.UUID
    status: str


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------


class EventResponse(BaseSchema):
    event_id: uuid.UUID
    event_type: str
    timestamp: datetime
    entity_type: str
    entity_id: uuid.UUID
    payload: Any



# ---------------------------------------------------------------------------
# Recommendation schemas (Phase 5 - spec section 17)
# ---------------------------------------------------------------------------


class RecommendationResponse(BaseSchema):
    recommendation_id: uuid.UUID
    risk_id: uuid.UUID
    action_type: str
    quantity: int
    source_store_id: Optional[uuid.UUID] = None
    destination_store_id: Optional[uuid.UUID] = None
    score: float
    confidence: float
    reason_codes: Any
    alternatives: Any
    status: str
    created_at: datetime


class RecommendationBatchEvaluateResponse(BaseModel):
    recommendations_generated: int


class RecommendationEvaluateResponse(BaseModel):
    recommendation_id: uuid.UUID
    action_type: str
    score: float
    confidence: float
    reason_codes: Any
    status: str


class RecommendationApproveResponse(BaseModel):
    recommendation_id: uuid.UUID
    status: str


class RecommendationRejectResponse(BaseModel):
    recommendation_id: uuid.UUID
    status: str


# ---------------------------------------------------------------------------
# Agent execution schemas (Phase 6 - spec section 19-21)
# ---------------------------------------------------------------------------


class AgentRunResponse(BaseModel):
    run_id: str
    recommendation_id: str
    status: str
    action_type: Optional[str] = None
    events: Any
    error: Optional[str] = None
    new_recommendation_id: Optional[str] = None
    requires_human_review: bool = False
    started_at: datetime
    finished_at: datetime


class AgentRunStatusResponse(BaseModel):
    run_id: str
    status: str
    recommendation_id: str


# ---------------------------------------------------------------------------
# Customer / WhatsApp schemas (Phase 9 - spec section 22 & 32.8)
# ---------------------------------------------------------------------------


class CustomerListItemResponse(BaseModel):
    customer_id: str
    name: str
    home_store_id: str
    home_store_name: str
    staple_count: int
    critical_staple: str
    days_left: float
    fill_pct: int
    last_order_at: Optional[str] = None


class CustomerDetailResponse(BaseModel):
    customer_id: str
    name: str
    home_store_id: str
    home_store_name: str
    staples: list[dict[str, Any]]


class CustomerMessageRequest(BaseModel):
    message: str


class CustomerMessageResponse(BaseModel):
    reply: str
    stage: str
    timestamp: str
    quick_actions: list[str] = []


class CustomerMessagesListResponse(BaseModel):
    customer_id: str
    customer_name: str
    home_store_name: str
    messages: list[dict[str, Any]]


class CustomerReorderItem(BaseModel):
    product_id: str
    quantity: int = 1


class CustomerReorderRequest(BaseModel):
    items: Optional[list[CustomerReorderItem]] = None


class CustomerReorderResponse(BaseModel):
    order_id: str
    customer_id: str
    customer_name: str
    store_id: str
    store_name: str
    items: list[dict[str, Any]]
    total_amount: float
    status: str
    created_at: datetime
    pantry_restored: bool
    store_inventory_updated: dict[str, int]


class CustomerRemindRequest(BaseModel):
    delay_hours: int = 24


class CustomerRemindResponse(BaseModel):
    customer_id: str
    status: str
    delay_hours: int
    scheduled_time: str
    message: str


class CustomerSkipRequest(BaseModel):
    reason: Optional[str] = None


class CustomerSkipResponse(BaseModel):
    customer_id: str
    status: str
    reason: str
    message: str


# ---------------------------------------------------------------------------
# Phase 8: CommercePort schemas (Spec §5.1, §28, & §38.9)
# ---------------------------------------------------------------------------


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
    items: list[CommerceCartItemResponse]
    item_total: float
    delivery_fee: float
    packaging_fee: float
    discount: float
    grand_total: float
    is_serviceable: bool


class CartItemUpdatePayload(BaseModel):
    spin_id: str
    quantity: int


class CommerceCartUpdateRequest(BaseModel):
    items: list[CartItemUpdatePayload]
    address_id: Optional[str] = None


class CommercePaymentOptionResponse(BaseModel):
    method: str
    label: str
    is_available: bool
    description: Optional[str] = None


class CommerceCheckoutRequest(BaseModel):
    payment_method: str = "UPI"
    explicit_confirmation: bool = False
    address_id: Optional[str] = None


class CommerceOrderResultResponse(BaseModel):
    order_id: str
    cart_id: str
    status: str
    items: list[CommerceCartItemResponse]
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


