"""FastAPI Customer Endpoints for Phase 9 (Spec §22 & §32.8).

Provides:
- GET  /api/customers: List customers with home store linkage and pantry status
- GET  /api/customers/{id}: Detail customer profile and pantry staples
- GET  /api/customers/{id}/messages: Proactive WhatsApp replenishment alert history
- POST /api/customers/{id}/messages: Process user response / interactive chat
- POST /api/customers/{id}/reorder: 1-tap reorder with dark store inventory deduction
- POST /api/customers/{id}/remind: Schedule simulated replenishment reminder
- POST /api/customers/{id}/skip: Record customer skip decision
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.customer.service import CustomerService
from backend.api.schemas import (
    CustomerListItemResponse,
    CustomerDetailResponse,
    CustomerMessagesListResponse,
    CustomerMessageRequest,
    CustomerMessageResponse,
    CustomerReorderRequest,
    CustomerReorderResponse,
    CustomerRemindRequest,
    CustomerRemindResponse,
    CustomerSkipRequest,
    CustomerSkipResponse,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])
service = CustomerService()


@router.get("", response_model=list[CustomerListItemResponse])
@router.get("/", response_model=list[CustomerListItemResponse], include_in_schema=False)
async def list_customers(db: AsyncSession = Depends(get_db)):
    """List all customers with home store linkage and current pantry status."""
    return await service.list_customers(db)


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get customer details and pantry depletion state."""
    data = await service.get_customer(db, customer_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    return data


@router.get("/{customer_id}/messages", response_model=CustomerMessagesListResponse)
async def get_customer_messages(
    customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Fetch conversational context and proactive alert for customer."""
    data = await service.get_whatsapp_messages(db, customer_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    return data


@router.post("/{customer_id}/messages", response_model=CustomerMessageResponse)
async def send_customer_message(
    customer_id: uuid.UUID,
    payload: CustomerMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Process user message in the WhatsApp simulation."""
    return await service.process_user_message(db, customer_id, payload.message)


@router.post("/{customer_id}/reorder", response_model=CustomerReorderResponse)
async def reorder_customer(
    customer_id: uuid.UUID,
    payload: Optional[CustomerReorderRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Execute 1-tap WhatsApp customer replenishment. Deducts store inventory and creates order."""
    try:
        items_payload = (
            [it.model_dump() for it in payload.items] if payload and payload.items else None
        )
        res = await service.reorder(db, customer_id, items_payload)
        return {
            "order_id": str(res.order_id),
            "customer_id": str(res.customer_id),
            "customer_name": res.customer_name,
            "store_id": str(res.store_id),
            "store_name": res.store_name,
            "items": res.items,
            "total_amount": res.total_amount,
            "status": res.status,
            "created_at": res.created_at,
            "pantry_restored": res.pantry_restored,
            "store_inventory_updated": res.store_inventory_updated,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{customer_id}/remind", response_model=CustomerRemindResponse)
async def remind_customer(
    customer_id: uuid.UUID,
    payload: Optional[CustomerRemindRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Schedule a simulated restock reminder."""
    delay = payload.delay_hours if payload else 24
    try:
        return await service.remind(db, customer_id, delay)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{customer_id}/skip", response_model=CustomerSkipResponse)
async def skip_customer(
    customer_id: uuid.UUID,
    payload: Optional[CustomerSkipRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Record customer skip decision."""
    reason = payload.reason if payload else None
    try:
        return await service.skip(db, customer_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
