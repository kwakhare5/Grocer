"""Customer domain models for Phase 9 Customer / WhatsApp simulation.

Defines data classes and response models for customer pantry state,
WhatsApp interaction messages, and replenishment action results.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class PantryStapleState:
    product_id: uuid.UUID
    product_name: str
    category: str
    daily_rate: float
    unit: str
    current_quantity: float
    capacity_quantity: float
    days_left: float
    fill_pct: int
    price: float


@dataclass
class CustomerState:
    customer_id: uuid.UUID
    name: str
    home_store_id: uuid.UUID
    home_store_name: str
    staples: list[PantryStapleState] = field(default_factory=list)
    last_order_at: Optional[datetime] = None


@dataclass
class WhatsAppInteractionMessage:
    sender: str  # "bot" | "user"
    text: str
    timestamp: str
    quick_actions: list[str] = field(default_factory=list)


@dataclass
class CustomerReorderResult:
    order_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    store_id: uuid.UUID
    store_name: str
    items: list[dict[str, Any]]
    total_amount: float
    status: str
    created_at: datetime
    pantry_restored: bool
    store_inventory_updated: dict[str, int]
