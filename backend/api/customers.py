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
    CommerceAdapterInfoResponse,
    CommerceDeliveryAddressResponse,
    CommerceProductItemResponse,
    CommerceCartResponse,
    CommerceCartUpdateRequest,
    CommercePaymentOptionResponse,
    CommerceCheckoutRequest,
    CommerceOrderResultResponse,
    CommerceTrackingResponse,
)
from backend.integrations.commerce.models import CartItemUpdate
from backend.integrations.commerce.exceptions import (
    UnconfirmedCheckoutError,
    CommerceError,
    ItemOutOfStockError,
    AddressNotServiceableError,
    MinOrderNotMetError,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])
service = CustomerService()


@router.get("/adapter-info", response_model=CommerceAdapterInfoResponse)
async def get_adapter_info():
    """Get active CommercePort provider status and endpoint details."""
    adapter_type = service.get_commerce_adapter_type()
    mode = "Live Instamart MCP" if adapter_type == "swiggy_mcp" else "Deterministic Fleet Simulation"
    endpoint = "https://mcp.swiggy.com/im" if adapter_type == "swiggy_mcp" else "in-memory://grocer/mumbai"
    return {
        "adapter_type": adapter_type,
        "endpoint": endpoint,
        "mode": mode,
    }


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


# ---------------------------------------------------------------------------
# Phase 8: CommercePort Endpoints (Spec §5.1, §28, & §38.9)
# ---------------------------------------------------------------------------


@router.get("/{customer_id}/addresses", response_model=list[CommerceDeliveryAddressResponse])
async def get_customer_addresses(customer_id: uuid.UUID):
    """Fetch saved delivery destinations for customer via active CommercePort."""
    try:
        addresses = await service.get_customer_addresses(customer_id)
        return [
            {
                "id": a.id,
                "label": a.label,
                "street": a.street,
                "city": a.city,
                "postal_code": a.postal_code,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "is_serviceable": a.is_serviceable,
            }
            for a in addresses
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{customer_id}/go-to-items", response_model=list[CommerceProductItemResponse])
async def get_customer_go_to_items(customer_id: uuid.UUID, address_id: Optional[str] = None):
    """Fetch frequently ordered staple items via active CommercePort."""
    try:
        items = await service.get_customer_go_to_items(customer_id, address_id)
        return [
            {
                "product_id": it.product_id,
                "name": it.name,
                "category": it.category,
                "variants": [v.model_dump() for v in it.variants],
                "image_url": it.image_url,
            }
            for it in items
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{customer_id}/products", response_model=list[CommerceProductItemResponse])
async def search_customer_products(
    customer_id: uuid.UUID, query: str = "", address_id: Optional[str] = None
):
    """Search products available at customer address via active CommercePort."""
    try:
        items = await service.search_customer_products(customer_id, query, address_id)
        return [
            {
                "product_id": it.product_id,
                "name": it.name,
                "category": it.category,
                "variants": [v.model_dump() for v in it.variants],
                "image_url": it.image_url,
            }
            for it in items
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{customer_id}/cart", response_model=CommerceCartResponse)
async def get_customer_cart(customer_id: uuid.UUID, cart_id: Optional[str] = None):
    """Fetch active customer cart and bill breakdown via active CommercePort."""
    try:
        cart = await service.get_customer_cart(customer_id, cart_id)
        return {
            "cart_id": cart.cart_id,
            "address_id": cart.address_id,
            "items": [it.model_dump() for it in cart.items],
            "item_total": cart.item_total,
            "delivery_fee": cart.delivery_fee,
            "packaging_fee": cart.packaging_fee,
            "discount": cart.discount,
            "grand_total": cart.grand_total,
            "is_serviceable": cart.is_serviceable,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{customer_id}/cart", response_model=CommerceCartResponse)
async def update_customer_cart(
    customer_id: uuid.UUID, payload: CommerceCartUpdateRequest, cart_id: Optional[str] = None
):
    """Update variant quantities in customer cart via active CommercePort."""
    try:
        items_update = [
            CartItemUpdate(spin_id=it.spin_id, quantity=it.quantity)
            for it in payload.items
        ]
        cart = await service.update_customer_cart(
            customer_id, items_update, cart_id=cart_id, address_id=payload.address_id
        )
        return {
            "cart_id": cart.cart_id,
            "address_id": cart.address_id,
            "items": [it.model_dump() for it in cart.items],
            "item_total": cart.item_total,
            "delivery_fee": cart.delivery_fee,
            "packaging_fee": cart.packaging_fee,
            "discount": cart.discount,
            "grand_total": cart.grand_total,
            "is_serviceable": cart.is_serviceable,
        }
    except (ItemOutOfStockError, AddressNotServiceableError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{customer_id}/cart")
async def clear_customer_cart(customer_id: uuid.UUID, cart_id: Optional[str] = None):
    """Clear customer cart via active CommercePort."""
    success = await service.clear_customer_cart(customer_id, cart_id)
    return {"cleared": success}


@router.get("/{customer_id}/payment-options", response_model=list[CommercePaymentOptionResponse])
async def get_customer_payment_options(customer_id: uuid.UUID, cart_id: Optional[str] = None):
    """Fetch live payment options via active CommercePort."""
    options = await service.get_customer_payment_options(customer_id, cart_id)
    return [opt.model_dump() for opt in options]


@router.post("/{customer_id}/checkout", response_model=CommerceOrderResultResponse)
async def checkout_customer(
    customer_id: uuid.UUID,
    payload: CommerceCheckoutRequest,
    cart_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Place and confirm customer order via active CommercePort.

    CRITICAL INVARIANT (Spec §28.3 & §39.15): Must reject unconfirmed requests with 400.
    """
    if not payload.explicit_confirmation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkout requires explicit confirmation.",
        )

    try:
        order_res = await service.checkout_customer(
            customer_id=customer_id,
            cart_id=cart_id,
            payment_method=payload.payment_method,
            explicit_confirmation=True,
            address_id=payload.address_id,
            db=db,
        )
        return {
            "order_id": order_res.order_id,
            "cart_id": order_res.cart_id,
            "status": order_res.status,
            "items": [it.model_dump() for it in order_res.items],
            "payment_method": order_res.payment_method,
            "grand_total": order_res.grand_total,
            "delivery_address": order_res.delivery_address.model_dump(),
            "placed_at": order_res.placed_at,
            "tracking_url": order_res.tracking_url,
        }
    except UnconfirmedCheckoutError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (MinOrderNotMetError, ItemOutOfStockError, AddressNotServiceableError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{customer_id}/orders/{order_id}/track", response_model=CommerceTrackingResponse)
async def track_customer_order(customer_id: uuid.UUID, order_id: str):
    """Fetch live delivery status and ETA via active CommercePort."""
    try:
        tracking = await service.track_customer_order(order_id)
        return tracking.model_dump()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
