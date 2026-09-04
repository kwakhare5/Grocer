import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Float, Numeric, DateTime, Text, JSON, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.enums import (
    StoreStatus, ProductCategory, OrderStatus, SupplierStatus,
    RiskType, RiskSeverity, ActionType, ActionStatus,
    RecommendationStatus, SimulationStatus, RiskStatus
)

class Store(Base):
    __tablename__ = 'store'
    
    store_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    operating_status: Mapped[StoreStatus]
    
    customers: Mapped[list["Customer"]] = relationship(back_populates="home_store")

class Supplier(Base):
    __tablename__ = 'supplier'
    
    supplier_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    lead_time_hours: Mapped[int]
    status: Mapped[SupplierStatus]
    
    products: Mapped[list["Product"]] = relationship(back_populates="supplier")

class Product(Base):
    __tablename__ = 'product'
    
    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    category: Mapped[ProductCategory]
    unit: Mapped[str]
    shelf_life_hours: Mapped[int]
    base_price: Mapped[float] = mapped_column(Numeric(10, 2))
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('supplier.supplier_id'))
    substitution_group: Mapped[Optional[str]]
    
    supplier: Mapped[Supplier] = relationship(back_populates="products")

class Customer(Base):
    __tablename__ = 'customer'
    
    customer_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    home_store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('store.store_id'))
    
    home_store: Mapped[Store] = relationship(back_populates="customers")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

class Order(Base):
    __tablename__ = 'order'
    
    order_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('customer.customer_id'))
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('store.store_id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[OrderStatus]
    
    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")

class OrderItem(Base):
    __tablename__ = 'order_item'
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('order.order_id'))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('product.product_id'))
    quantity: Mapped[int]
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    
    order: Mapped[Order] = relationship(back_populates="items")

class Inventory(Base):
    __tablename__ = 'inventory'
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('store.store_id'))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('product.product_id'))
    quantity: Mapped[int]
    
    __table_args__ = (UniqueConstraint('store_id', 'product_id', name='uq_inventory_store_product'),)

class Batch(Base):
    __tablename__ = 'batch'
    
    batch_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('store.store_id'))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('product.product_id'))
    quantity: Mapped[int]
    received_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Forecast(Base):
    __tablename__ = 'forecast'
    
    forecast_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('store.store_id'))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('product.product_id'))
    forecast_window_hours: Mapped[int]
    predicted_demand: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Risk(Base):
    __tablename__ = 'risk'
    
    risk_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('store.store_id'))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('product.product_id'))
    risk_type: Mapped[RiskType]
    severity: Mapped[RiskSeverity]
    probability: Mapped[float] = mapped_column(Float)
    expected_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[RiskStatus]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="risk")

class Recommendation(Base):
    __tablename__ = 'recommendation'
    
    recommendation_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('risk.risk_id'))
    action_type: Mapped[ActionType]
    quantity: Mapped[int]
    source_store_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey('store.store_id'))
    destination_store_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey('store.store_id'))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    reason_codes: Mapped[Any] = mapped_column(JSON)
    alternatives: Mapped[Any] = mapped_column(JSON)
    status: Mapped[RecommendationStatus]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    risk: Mapped[Risk] = relationship(back_populates="recommendations")

class Action(Base):
    __tablename__ = 'action'
    
    action_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('recommendation.recommendation_id'))
    action_type: Mapped[ActionType]
    approved_by: Mapped[Optional[str]]
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[ActionStatus]
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)

class Event(Base):
    __tablename__ = 'event'
    
    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    entity_type: Mapped[str]
    entity_id: Mapped[uuid.UUID]
    payload: Mapped[Any] = mapped_column(JSON)

class Scenario(Base):
    __tablename__ = 'scenario'
    
    scenario_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    configuration: Mapped[Any] = mapped_column(JSON)

class Simulation(Base):
    __tablename__ = 'simulation'
    
    simulation_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey('scenario.scenario_id'))
    seed: Mapped[int]
    current_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[SimulationStatus]
    configuration: Mapped[Any] = mapped_column(JSON)
