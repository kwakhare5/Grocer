"""Durable, provider-independent shopping-task domain model.

Human language is translated into a proposed ``MessageUnderstanding``.  Only the
deterministic task reducer may turn that proposal into a desired basket or a
provider mutation plan.  The models deliberately distinguish Grocer's desired
basket from Swiggy's account-level cart.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskState(StrEnum):
    READY = "READY"
    NEEDS_CART_ADOPTION = "NEEDS_CART_ADOPTION"
    NEEDS_DETAILS = "NEEDS_DETAILS"
    NEEDS_PRODUCT_CHOICE = "NEEDS_PRODUCT_CHOICE"
    AWAITING_BASKET_APPROVAL = "AWAITING_BASKET_APPROVAL"
    SYNCHRONIZING_CART = "SYNCHRONIZING_CART"
    NEEDS_ADDRESS = "NEEDS_ADDRESS"
    NEEDS_PAYMENT = "NEEDS_PAYMENT"
    AWAITING_CHECKOUT_CONFIRMATION = "AWAITING_CHECKOUT_CONFIRMATION"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    ORDERED = "ORDERED"
    CANCELLED = "CANCELLED"


class TaskOperation(StrEnum):
    START_TASK = "START_TASK"
    ADD_ITEMS = "ADD_ITEMS"
    SET_ITEMS = "SET_ITEMS"
    KEEP_ONLY_ITEMS = "KEEP_ONLY_ITEMS"
    REMOVE_ITEMS = "REMOVE_ITEMS"
    REPLACE_ITEM = "REPLACE_ITEM"
    SET_QUANTITY = "SET_QUANTITY"
    SELECT_PRODUCT = "SELECT_PRODUCT"
    ADOPT_PROVIDER_CART = "ADOPT_PROVIDER_CART"
    START_FRESH_CART = "START_FRESH_CART"
    CANCEL_PENDING_STEP = "CANCEL_PENDING_STEP"
    SELECT_OPTION = "SELECT_OPTION"
    CHANGE_ADDRESS = "CHANGE_ADDRESS"
    SELECT_ADDRESS = "SELECT_ADDRESS"
    CHANGE_PAYMENT = "CHANGE_PAYMENT"
    SELECT_PAYMENT = "SELECT_PAYMENT"
    CONFIRM_BASKET = "CONFIRM_BASKET"
    CONFIRM_CHECKOUT = "CONFIRM_CHECKOUT"
    CANCEL_TASK = "CANCEL_TASK"
    TRACK_ORDER = "TRACK_ORDER"
    ASK_FOR_HELP = "ASK_FOR_HELP"
    CLARIFY = "CLARIFY"


class ResolutionStatus(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    EXACT = "EXACT"
    PREFERENCE_PROPOSED = "PREFERENCE_PROPOSED"
    AMBIGUOUS = "AMBIGUOUS"
    UNAVAILABLE = "UNAVAILABLE"


class DesiredBasketItem(BaseModel):
    """An item the customer wants, before a provider SKU is selected."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = "units"
    brand: str | None = None
    packaging: str | None = None
    preference_source: Literal["explicit", "confirmed_preference", "none"] = "none"
    quantity_is_explicit: bool = False
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    selected_spin_id: str | None = None
    selected_sku_id: str | None = None


class MessageUnderstanding(BaseModel):
    """Non-authoritative interpretation of one natural-language turn."""

    model_config = ConfigDict(extra="forbid")

    operation: TaskOperation
    items: list[DesiredBasketItem] = Field(default_factory=list)
    target_item: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    selection_value: str | None = None
    selected_sku_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    ambiguities: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    source: Literal["model", "rules", "interactive"]

    @property
    def needs_clarification(self) -> bool:
        return bool(self.ambiguities or self.missing_details or self.confidence < 0.8)


class ProviderCartBinding(BaseModel):
    """Observed binding between a ShoppingTask and a provider account cart."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "swiggy_instamart"
    cart_id: str | None = None
    fingerprint: str | None = None
    last_verified_at: datetime | None = None
    adopted_by_customer: bool = False


class BasketPlan(BaseModel):
    """A complete desired-basket proposal awaiting customer approval."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    items: list[DesiredBasketItem]
    cart_strategy: Literal["reuse", "start_fresh"] = "reuse"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: datetime | None = None


class ShoppingTask(BaseModel):
    """Authoritative persisted aggregate for one customer shopping task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    customer_id: str
    state: TaskState = TaskState.READY
    version: int = Field(default=1, ge=1)
    desired_basket: list[DesiredBasketItem] = Field(default_factory=list)
    provider_cart: ProviderCartBinding = Field(default_factory=ProviderCartBinding)
    pending_plan: BasketPlan | None = None
    pending_question: str | None = None
    selected_address_id: str | None = None
    selected_payment_method: str | None = None
    confirmation_valid: bool = False
    requested_action: TaskOperation | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
