"""Products REST API — spec §32.4.

Endpoints:
    GET /api/products              — list all catalog products
    GET /api/products/{product_id} — product detail with supplier info
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Product
from backend.api.schemas import ProductResponse, ProductDetailResponse

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db)) -> list[ProductResponse]:
    """List all 25 catalog products."""
    result = await db.execute(select(Product).order_by(Product.category, Product.name))
    products = result.scalars().all()
    return [
        ProductResponse(
            product_id=p.product_id,
            name=p.name,
            category=p.category.value if hasattr(p.category, "value") else str(p.category),
            unit=p.unit,
            shelf_life_hours=p.shelf_life_hours,
            base_price=float(p.base_price),
            substitution_group=p.substitution_group,
        )
        for p in products
    ]


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    """Get a single product by ID."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductDetailResponse(
        product_id=product.product_id,
        name=product.name,
        category=product.category.value if hasattr(product.category, "value") else str(product.category),
        unit=product.unit,
        shelf_life_hours=product.shelf_life_hours,
        base_price=float(product.base_price),
        substitution_group=product.substitution_group,
        supplier_id=product.supplier_id,
    )
