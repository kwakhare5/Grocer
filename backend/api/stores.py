"""Stores REST API — spec §32.3.

Endpoints:
    GET /api/stores                          — list all dark stores
    GET /api/stores/{store_id}               — store details
    GET /api/stores/{store_id}/inventory     — inventory with batch breakdown
    GET /api/stores/{store_id}/forecasts     — forecasts scoped to a store
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Store, Inventory, Batch, Product, Forecast, Risk
from backend.api.schemas import (
    StoreResponse,
    StoreDetailResponse,
    StoreInventoryResponse,
    InventoryItemResponse,
    BatchResponse,
    ForecastResponse,
    RiskResponse,
)

router = APIRouter(prefix="/api/stores", tags=["stores"])


def _naive_now() -> datetime:
    """Return current UTC time as a naive datetime (timezone stripped).

    SQLite stores datetimes as naive strings. Using naive now lets us compare
    against SQLite batch.expires_at values without a TypeError.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hours_remaining(expires_at: datetime) -> float:
    """Compute hours remaining until expiry, handling naive/aware mismatch."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # If expires_at is timezone-aware, strip it for comparison
    if expires_at.tzinfo is not None:
        expires_naive = expires_at.replace(tzinfo=None)
    else:
        expires_naive = expires_at
    delta = expires_naive - now
    return max(0.0, delta.total_seconds() / 3600)


@router.get("", response_model=list[StoreResponse])
async def list_stores(db: AsyncSession = Depends(get_db)) -> list[StoreResponse]:
    """List all 5 dark stores."""
    result = await db.execute(select(Store).order_by(Store.name))
    return result.scalars().all()


@router.get("/{store_id}", response_model=StoreDetailResponse)
async def get_store(store_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StoreDetailResponse:
    """Get a single store by ID."""
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}/inventory", response_model=StoreInventoryResponse)
async def get_store_inventory(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StoreInventoryResponse:
    """Get inventory summary and active batch breakdown for a store."""
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    now = _naive_now()  # SQLite stores naive datetimes; use naive now for comparison

    # Inventory records
    inv_result = await db.execute(
        select(Inventory, Product)
        .join(Product, Inventory.product_id == Product.product_id)
        .where(Inventory.store_id == store_id)
        .order_by(Product.name)
    )
    inv_rows = inv_result.all()

    inventory_items = [
        InventoryItemResponse(
            product_id=row.Product.product_id,
            product_name=row.Product.name,
            category=row.Product.category.value if hasattr(row.Product.category, "value") else str(row.Product.category),
            quantity=row.Inventory.quantity,
            unit=row.Product.unit,
        )
        for row in inv_rows
    ]

    # Active (non-expired) batches
    batch_result = await db.execute(
        select(Batch)
        .where(Batch.store_id == store_id)
        .where(Batch.expires_at > now)
        .order_by(Batch.expires_at)
    )
    batch_rows = batch_result.scalars().all()

    batches = [
        BatchResponse(
            batch_id=b.batch_id,
            product_id=b.product_id,
            quantity=b.quantity,
            received_at=b.received_at,
            expires_at=b.expires_at,
            hours_remaining=_hours_remaining(b.expires_at),
        )
        for b in batch_rows
    ]

    return StoreInventoryResponse(
        store_id=store.store_id,
        store_name=store.name,
        inventory=inventory_items,
        batches=batches,
    )


@router.get("/{store_id}/forecasts", response_model=list[ForecastResponse])
async def get_store_forecasts(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ForecastResponse]:
    """Get all forecasts for a given store, newest first."""
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    result = await db.execute(
        select(Forecast)
        .where(Forecast.store_id == store_id)
        .order_by(Forecast.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{store_id}/risks", response_model=list[RiskResponse])
async def get_store_risks(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[RiskResponse]:
    """Get all risks for a given store, newest first."""
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    result = await db.execute(
        select(Risk)
        .where(Risk.store_id == store_id)
        .order_by(Risk.created_at.desc())
    )
    risks = result.scalars().all()
    return [
        RiskResponse(
            risk_id=r.risk_id,
            store_id=r.store_id,
            product_id=r.product_id,
            risk_type=r.risk_type.value if hasattr(r.risk_type, "value") else str(r.risk_type),
            severity=r.severity.value if hasattr(r.severity, "value") else str(r.severity),
            probability=r.probability,
            expected_time=r.expected_time,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            created_at=r.created_at,
        )
        for r in risks
    ]

