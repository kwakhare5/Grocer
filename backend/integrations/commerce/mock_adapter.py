"""High-fidelity mock commerce adapter for local simulation and testing."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.models import (
    DeliveryAddress,
    CommerceProductItem,
    ProductVariant,
    CartItemUpdate,
    CartItem,
    CommerceCart,
    PaymentOption,
    CommerceOrderResult,
    DeliveryTrackingStatus,
)
from backend.integrations.commerce.exceptions import (
    UnconfirmedCheckoutError,
    AddressNotServiceableError,
    ItemOutOfStockError,
    MinOrderNotMetError,
)

# Standard mock catalog mapped to Grocer staples
MOCK_PRODUCTS: list[CommerceProductItem] = [
    CommerceProductItem(
        product_id="prod-milk",
        name="Amul Taaza Fresh Toned Milk",
        category="dairy",
        variants=[
            ProductVariant(
                spin_id="SPIN-MILK-1L",
                name="Amul Taaza Milk 1L Pouch",
                pack_size="1 L",
                price=66.0,
                mrp=68.0,
                in_stock=True,
            ),
            ProductVariant(
                spin_id="SPIN-MILK-500ML",
                name="Amul Taaza Milk 500ml Pouch",
                pack_size="500 ml",
                price=34.0,
                mrp=35.0,
                in_stock=True,
            ),
        ],
    ),
    CommerceProductItem(
        product_id="prod-bread",
        name="Whole Wheat Brown Bread",
        category="bakery",
        variants=[
            ProductVariant(
                spin_id="SPIN-BREAD-400G",
                name="Whole Wheat Bread 400g",
                pack_size="400 g",
                price=50.0,
                mrp=55.0,
                in_stock=True,
            ),
        ],
    ),
    CommerceProductItem(
        product_id="prod-eggs",
        name="Farm Fresh White Eggs",
        category="poultry",
        variants=[
            ProductVariant(
                spin_id="SPIN-EGGS-12",
                name="Farm Fresh Eggs (12 pcs)",
                pack_size="12 pcs",
                price=90.0,
                mrp=95.0,
                in_stock=True,
            ),
            ProductVariant(
                spin_id="SPIN-EGGS-6",
                name="Farm Fresh Eggs (6 pcs)",
                pack_size="6 pcs",
                price=48.0,
                mrp=52.0,
                in_stock=True,
            ),
        ],
    ),
    CommerceProductItem(
        product_id="prod-tomato",
        name="Fresh Farm Hybrid Tomatoes",
        category="produce",
        variants=[
            ProductVariant(
                spin_id="SPIN-TOMATO-500G",
                name="Hybrid Tomatoes 500g",
                pack_size="500 g",
                price=32.0,
                mrp=36.0,
                in_stock=True,
            ),
            ProductVariant(
                spin_id="SPIN-TOMATO-1KG",
                name="Hybrid Tomatoes 1kg",
                pack_size="1 kg",
                price=60.0,
                mrp=70.0,
                in_stock=True,
            ),
        ],
    ),
]

MOCK_ADDRESSES = [
    DeliveryAddress(
        id="addr-bandra-1",
        label="Home",
        street="14 Pali Hill Road, Bandra West",
        city="Mumbai",
        postal_code="400050",
        latitude=19.0596,
        longitude=72.8295,
        is_serviceable=True,
    ),
    DeliveryAddress(
        id="addr-andheri-1",
        label="Work",
        street="Solitaire Corporate Park, Andheri East",
        city="Mumbai",
        postal_code="400093",
        latitude=19.1136,
        longitude=72.8697,
        is_serviceable=True,
    ),
]


class MockCommerceAdapter(CommercePort):
    """Deterministic in-memory commerce simulation adapter."""

    def __init__(self) -> None:
        self._carts: dict[str, CommerceCart] = {}
        self._orders: dict[str, CommerceOrderResult] = {}
        self._catalog_by_spin: dict[str, tuple[CommerceProductItem, ProductVariant]] = {}
        for prod in MOCK_PRODUCTS:
            for variant in prod.variants:
                self._catalog_by_spin[variant.spin_id] = (prod, variant)

    async def get_addresses(self, customer_id: str) -> list[DeliveryAddress]:
        return list(MOCK_ADDRESSES)

    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        # Return Milk, Bread, and Eggs as frequent staples
        return [p for p in MOCK_PRODUCTS if p.product_id in ["prod-milk", "prod-bread", "prod-eggs"]]

    async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
        q = query.strip().lower()
        if not q:
            return list(MOCK_PRODUCTS)
        return [
            p for p in MOCK_PRODUCTS
            if q in p.name.lower() or q in p.category.lower() or any(q in v.name.lower() for v in p.variants)
        ]

    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        cid = cart_id or "default-cart"
        if cid not in self._carts:
            self._carts[cid] = CommerceCart(cart_id=cid)
        return self._carts[cid]

    async def update_cart(
        self, items: list[CartItemUpdate], cart_id: Optional[str] = None, address_id: Optional[str] = None
    ) -> CommerceCart:
        cid = cart_id or "default-cart"
        cart_items: list[CartItem] = []
        item_total = 0.0

        for update in items:
            if update.quantity <= 0:
                continue
            if update.spin_id not in self._catalog_by_spin:
                raise ItemOutOfStockError(spin_id=update.spin_id, available_quantity=0)

            prod, variant = self._catalog_by_spin[update.spin_id]
            total_price = round(variant.price * update.quantity, 2)
            cart_items.append(
                CartItem(
                    spin_id=variant.spin_id,
                    name=variant.name,
                    pack_size=variant.pack_size,
                    unit_price=variant.price,
                    quantity=update.quantity,
                    total_price=total_price,
                )
            )
            item_total += total_price

        packaging_fee = 5.0 if cart_items else 0.0
        delivery_fee = 0.0 if (item_total >= 199.0 or not cart_items) else 30.0
        grand_total = round(item_total + packaging_fee + delivery_fee, 2)

        cart = CommerceCart(
            cart_id=cid,
            address_id=address_id or (MOCK_ADDRESSES[0].id if MOCK_ADDRESSES else None),
            items=cart_items,
            item_total=round(item_total, 2),
            packaging_fee=packaging_fee,
            delivery_fee=delivery_fee,
            grand_total=grand_total,
            is_serviceable=True,
        )
        self._carts[cid] = cart
        return cart

    async def clear_cart(self, cart_id: Optional[str] = None) -> bool:
        cid = cart_id or "default-cart"
        self._carts[cid] = CommerceCart(cart_id=cid)
        return True

    async def get_payment_options(self, cart_id: Optional[str] = None) -> list[PaymentOption]:
        return [
            PaymentOption(
                method="UPI",
                label="UPI Instant Pay (GPay / PhonePe / Paytm)",
                is_available=True,
                description="Instant authorization via UPI Intent or scan QR",
            ),
            PaymentOption(
                method="COD",
                label="Cash on Delivery",
                is_available=True,
                description="Pay in cash or UPI to delivery partner upon arrival",
            ),
        ]

    async def checkout(
        self,
        cart_id: str,
        payment_method: str = "UPI",
        explicit_confirmation: bool = False,
        address_id: Optional[str] = None,
    ) -> CommerceOrderResult:
        if not explicit_confirmation:
            raise UnconfirmedCheckoutError(
                "Checkout rejected: explicit confirmation is strictly required."
            )

        cart = await self.get_cart(cart_id)
        if not cart.items:
            raise MinOrderNotMetError(current_total=0.0, min_required=99.0)

        # Resolve address
        addr = next((a for a in MOCK_ADDRESSES if a.id == address_id), MOCK_ADDRESSES[0])

        order_id = f"OD-{uuid.uuid4().hex[:8].upper()}"
        order_result = CommerceOrderResult(
            order_id=order_id,
            cart_id=cart_id,
            status="ORDER_CONFIRMED",
            items=list(cart.items),
            payment_method=payment_method,
            grand_total=cart.grand_total,
            delivery_address=addr,
            placed_at=datetime.now(timezone.utc),
            tracking_url=f"/orders/{order_id}/track",
        )
        self._orders[order_id] = order_result
        # Clear cart on successful order
        await self.clear_cart(cart_id)
        return order_result

    async def track_order(self, order_id: str) -> DeliveryTrackingStatus:
        if order_id not in self._orders:
            # Generate deterministic fallback for tracking any order
            return DeliveryTrackingStatus(
                order_id=order_id,
                status="PACKING",
                eta_minutes=14,
                driver_name="Ramesh Kamble",
                driver_phone="+91 98201 12345",
            )

        return DeliveryTrackingStatus(
            order_id=order_id,
            status="PACKING",
            eta_minutes=12,
            driver_name="Ramesh Kamble",
            driver_phone="+91 98201 12345",
        )