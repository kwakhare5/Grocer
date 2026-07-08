from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class Household(Base):
    __tablename__ = "households"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(20))
    composition = Column(String(50))           # solo, couple, family_small, family_large
    composition_confidence = Column(Float)
    intelligence_consent = Column(Boolean, default=False)
    notifications_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    orders = relationship("Order", back_populates="household")

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index('ix_orders_household_placed_at', 'household_id', 'placed_at'),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), index=True)
    platform_order_id = Column(String(255), unique=True)
    platform = Column(String(50), nullable=False, server_default="instamart")
    placed_at = Column(DateTime(timezone=True), nullable=False)
    total_amount = Column(Float)
    raw_data = Column(JSONB)
    household = relationship("Household", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    item_id = Column(String(255), nullable=False, index=True)
    item_name = Column(String(500), nullable=False)
    category = Column(String(100))
    quantity = Column(Integer)
    unit = Column(String(50))
    standard_quantity = Column(Float)          # normalized (500ml → 0.5L)
    price = Column(Float)
    order = relationship("Order", back_populates="items")

class ConsumptionModel(Base):
    __tablename__ = "consumption_models"
    __table_args__ = (
        UniqueConstraint('household_id', 'item_id', name='uq_consumption_model_household_item'),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), index=True)
    item_id = Column(String(255))
    item_name = Column(String(500))
    category = Column(String(100))
    avg_daily_consumption = Column(Float)
    consumption_cycle_days = Column(Float)
    last_purchase_date = Column(DateTime(timezone=True))
    last_purchase_quantity = Column(Float)
    estimated_depletion_date = Column(DateTime(timezone=True))
    confidence_score = Column(Float)
    data_points = Column(Integer)
    is_anomaly_excluded = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class RestockAlert(Base):
    __tablename__ = "restock_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), index=True)
    item_ids = Column(JSONB)                         # list of item_id strings e.g. ["INS_001", "INS_003"]
    message_sent = Column(Text)                      # the WhatsApp message that was or will be sent
    sent_at = Column(DateTime(timezone=True))
    status = Column(String(50), default='pending')   # pending/sent/acted/dismissed
    acted_at = Column(DateTime(timezone=True))
    order_id_placed = Column(String(255))            # Platform order ID once acted upon

class PriceHistory(Base):
    __tablename__ = "price_history"
    # TimescaleDB hypertable — partitioned by recorded_at
    item_id = Column(String(255), primary_key=True)
    item_name = Column(String(500))
    recorded_at = Column(DateTime(timezone=True), primary_key=True)
    price = Column(Float)
    price_per_unit = Column(Float)

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"))
    name = Column(String(500))
    servings = Column(Integer)
    ingredients = Column(JSONB)
    cuisine = Column(String(100))
    pinned_for = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
