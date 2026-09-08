"""High-fidelity mock commerce adapter for local simulation and testing."""
from __future__ import annotations

import copy
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
    PaymentStatusResult,
    DeliveryStatusResult,
    OrderDetails,
    OrderLineItem,
    OrderSummary,
)
from backend.integrations.commerce.exceptions import (
    CommerceError,
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
    """Deterministic in-memory commerce simulation adapter with failure injection."""

    def __init__(self) -> None:
        self._carts: dict[str, CommerceCart] = {}
        self._orders: dict[str, CommerceOrderResult] = {}
        self._injected_oos: set[str] = set()
        self._price_overrides: dict[str, float] = {}
        self._injected_stale: bool = False
        self._transient_errors_remaining: int = 0
        self._partial_drop_spins: set[str] = set()
        self._min_order_threshold: Optional[float] = None
        self.call_count: int = 0
        self.successful_call_count: int = 0
        self._init_catalog()

    def _init_catalog(self) -> None:
        """Initialize instance-isolated catalog copies."""
        self._products: list[CommerceProductItem] = copy.deepcopy(MOCK_PRODUCTS)
        self._catalog_by_spin: dict[str, tuple[CommerceProductItem, ProductVariant]] = {}
        for prod in self._products:
            for variant in prod.variants:
                self._catalog_by_spin[variant.spin_id] = (prod, variant)

    # -----------------------------------------------------------------------
    # Deterministic Failure Injection Hooks (Spec §15, §20)
    # -----------------------------------------------------------------------

    def inject_out_of_stock(self, spin_id: str) -> None:
        """Simulate an item variant going out of stock in real-time."""
        self._injected_oos.add(spin_id)
        if spin_id in self._catalog_by_spin:
            _prod, variant = self._catalog_by_spin[spin_id]
            variant.in_stock = False

        # Flag existing cart items as unavailable
        for cart in self._carts.values():
            for item in cart.items:
                if item.spin_id == spin_id:
                    item.is_available = False

    def inject_price_change(self, spin_id: str, new_price: float) -> None:
        """Simulate a supplier or store-level price surge."""
        self._price_overrides[spin_id] = new_price
        if spin_id in self._catalog_by_spin:
            _prod, variant = self._catalog_by_spin[spin_id]
            variant.price = new_price

        # Update cart items and recalculate grand total
        for cart in self._carts.values():
            for item in cart.items:
                if item.spin_id == spin_id:
                    item.unit_price = new_price
                    item.total_price = round(new_price * item.quantity, 2)
            item_total = sum(it.total_price for it in cart.items)
            cart.item_total = round(item_total, 2)
            cart.delivery_fee = 0.0 if (item_total >= 199.0 or not cart.items) else 30.0
            cart.grand_total = round(item_total + cart.packaging_fee + cart.delivery_fee, 2)

    def inject_stale_cart(self, is_stale: bool = True) -> None:
        """Simulate session expiry or store becoming unserviceable."""
        self._injected_stale = is_stale
        for cart in self._carts.values():
            cart.is_serviceable = not is_stale

    def inject_transient_error(self, count: int = 1) -> None:
        """Simulate transient upstream provider failure (e.g. 503 or network drop)."""
        self._transient_errors_remaining = count

    def inject_partial_cart_drop(self, spin_id: str) -> None:
        """Simulate partial cart success where provider drops an item during mutation."""
        self._partial_drop_spins.add(spin_id)
        for cart in self._carts.values():
            original_count = len(cart.items)
            cart.items = [item for item in cart.items if item.spin_id != spin_id]
            if len(cart.items) == original_count:
                continue
            cart.item_total = round(sum(item.total_price for item in cart.items), 2)
            cart.packaging_fee = 5.0 if cart.items else 0.0
            cart.delivery_fee = (
                0.0 if cart.item_total >= 199.0 or not cart.items else 30.0
            )
            cart.grand_total = round(
                cart.item_total + cart.packaging_fee + cart.delivery_fee, 2
            )
            cart.cart_warning = "PARTIAL_SUCCESS"

    def inject_min_order_threshold(self, min_amount: float) -> None:
        """Set a minimum order threshold for checkout / basket validation."""
        self._min_order_threshold = min_amount

    def inject_brand_mismatch(self, cart_id: str, spin_id: str, substitute_name: str) -> None:
        """Simulate upstream provider substituting a non-compliant brand in cart."""
        cid = cart_id or "default-cart"
        if cid in self._carts:
            for it in self._carts[cid].items:
                if it.spin_id == spin_id:
                    it.name = substitute_name
                    it.brand = substitute_name.split(maxsplit=1)[0]

    def reset_injections(self) -> None:
        """Restore pristine catalog and clear all simulated faults."""
        self._injected_oos.clear()
        self._price_overrides.clear()
        self._injected_stale = False
        self._transient_errors_remaining = 0
        self._partial_drop_spins.clear()
        self._min_order_threshold = None
        self.call_count = 0
        self.successful_call_count = 0
        self._init_catalog()

    # -----------------------------------------------------------------------
    # CommercePort Methods
    # -----------------------------------------------------------------------

    async def get_addresses(self, customer_id: str) -> list[DeliveryAddress]:
        self.call_count += 1
        self.successful_call_count += 1
        return list(MOCK_ADDRESSES)

    async def get_go_to_items(self, address_id: str) -> list[CommerceProductItem]:
        self.call_count += 1
        self.successful_call_count += 1
        return [p for p in self._products if p.product_id in ["prod-milk", "prod-bread", "prod-eggs"]]

    async def search_products(self, address_id: str, query: str) -> list[CommerceProductItem]:
        self.call_count += 1
        q = query.strip().lower()
        res = list(self._products) if not q else [
            p for p in self._products
            if q in p.name.lower() or q in p.category.lower() or any(q in v.name.lower() for v in p.variants)
        ]
        self.successful_call_count += 1
        return res

    async def get_cart(self, cart_id: Optional[str] = None) -> CommerceCart:
        self.call_count += 1
        if self._transient_errors_remaining > 0:
            self._transient_errors_remaining -= 1
            raise CommerceError("Simulated upstream transient network timeout", code="TRANSIENT_TIMEOUT")

        cid = cart_id or "default-cart"
        if cid not in self._carts:
            self._carts[cid] = CommerceCart(
                cart_id=cid,
                min_order_threshold=self._min_order_threshold if self._min_order_threshold is not None else 0.0,
            )

        cart = self._carts[cid]
        if self._min_order_threshold is not None:
            cart.min_order_threshold = self._min_order_threshold
        # Ensure availability matches injected state
        for item in cart.items:
            if item.spin_id in self._injected_oos:
                item.is_available = False
        if self._injected_stale:
            cart.is_serviceable = False

        self.successful_call_count += 1
        return cart

    async def update_cart(
        self, items: list[CartItemUpdate], cart_id: Optional[str] = None, address_id: Optional[str] = None
    ) -> CommerceCart:
        self.call_count += 1
        if self._transient_errors_remaining > 0:
            self._transient_errors_remaining -= 1
            raise CommerceError("Simulated upstream transient network timeout", code="TRANSIENT_TIMEOUT")

        cid = cart_id or "default-cart"
        cart_items: list[CartItem] = []
        item_total = 0.0
        partial_drop_detected = any(
            update.quantity > 0 and update.spin_id in self._partial_drop_spins
            for update in items
        )

        for update in items:
            if update.quantity <= 0 or update.spin_id in self._partial_drop_spins:
                continue
            if update.spin_id not in self._catalog_by_spin:
                raise ItemOutOfStockError(spin_id=update.spin_id, available_quantity=0)

            prod, variant = self._catalog_by_spin[update.spin_id]
            if not variant.in_stock or update.spin_id in self._injected_oos:
                raise ItemOutOfStockError(spin_id=update.spin_id, available_quantity=0)

            price = self._price_overrides.get(variant.spin_id, variant.price)
            total_price = round(price * update.quantity, 2)
            cart_items.append(
                CartItem(
                    spin_id=variant.spin_id,
                    name=variant.name,
                    pack_size=variant.pack_size,
                    unit_price=price,
                    quantity=update.quantity,
                    total_price=total_price,
                    is_available=True,
                    product_id=prod.product_id,
                    category=prod.category,
                    brand=prod.brand,
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
            is_serviceable=not self._injected_stale,
            min_order_threshold=self._min_order_threshold if self._min_order_threshold is not None else 0.0,
            cart_warning="PARTIAL_SUCCESS" if partial_drop_detected else None,
        )
        self._carts[cid] = cart
        self.successful_call_count += 1
        return cart

    async def clear_cart(self, cart_id: Optional[str] = None) -> bool:
        self.call_count += 1
        cid = cart_id or "default-cart"
        self._carts[cid] = CommerceCart(cart_id=cid)
        self.successful_call_count += 1
        return True


    async def get_payment_options(
        self, cart_id: Optional[str] = None, address_id: Optional[str] = None
    ) -> list[PaymentOption]:
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
        self.call_count += 1
        if not explicit_confirmation:
            raise UnconfirmedCheckoutError(
                "Checkout rejected: explicit confirmation is strictly required."
            )

        cart = await self.get_cart(cart_id)
        min_required = self._min_order_threshold or 99.0
        if not cart.items:
            raise MinOrderNotMetError(current_total=0.0, min_required=min_required)
        if self._min_order_threshold and cart.grand_total < self._min_order_threshold:
            raise MinOrderNotMetError(current_total=cart.grand_total, min_required=self._min_order_threshold)

        # Resolve address
        addr = next((a for a in MOCK_ADDRESSES if a.id == address_id), MOCK_ADDRESSES[0])

        order_id = f"OD-{uuid.uuid4().hex[:8].upper()}"
        order_result = CommerceOrderResult(
            order_id=order_id,
            cart_id=cart_id,
            status="ORDER_PLACED",
            raw_status="SIMULATED_ORDER_PLACED",
            items=list(cart.items),
            payment_method=payment_method,
            grand_total=cart.grand_total,
            delivery_address=addr,
            placed_at=datetime.now(timezone.utc),
            tracking_url=f"/orders/{order_id}/track",
            order_count=1,
            success_count=1,
            all_succeeded=True,
        )
        self._orders[order_id] = order_result
        # Clear cart on successful order
        await self.clear_cart(cart_id)
        self.successful_call_count += 1
        return order_result

    async def check_payment_status(
        self, paas_id: str, order_id: Optional[str] = None
    ) -> PaymentStatusResult:
        return PaymentStatusResult(
            paas_id=paas_id,
            order_id=order_id,
            status="SIMULATED_SUCCESS",
            normalized_status="PAYMENT_CONFIRMED",
            terminal=True,
            confirmed=True,
            order_status="ORDER_PLACED",
        )

    async def confirm_order(self, order_id: str, paas_id: str) -> CommerceOrderResult:
        order = self._orders.get(order_id)
        if order is None:
            raise CommerceError("Simulated order not found", code="ORDER_NOT_FOUND")
        return order

    async def get_orders(
        self, count: int = 10, active_only: bool = False
    ) -> list[OrderSummary]:
        del active_only
        recent = list(self._orders.values())[-max(1, count) :]
        return [
            OrderSummary(
                order_id=order.order_id or "",
                raw_status=order.raw_status,
                normalized_status=order.status,
                total_amount=order.grand_total,
                payment_method=order.payment_method,
                is_active=order.status == "ORDER_PLACED",
                item_count=len(order.items),
                items=[
                    OrderLineItem(name=item.name, quantity=item.quantity)
                    for item in order.items
                ],
            )
            for order in recent
            if order.order_id
        ]

    async def get_order_details(self, order_id: str) -> OrderDetails:
        order = self._orders.get(order_id)
        if order is None:
            raise CommerceError("Simulated order not found", code="ORDER_NOT_FOUND")
        return OrderDetails(
            order_id=order_id,
            raw_status=order.raw_status,
            normalized_status=order.status,
            total_bill=order.grand_total,
            has_refunds=False,
            items=[
                OrderLineItem(
                    name=item.name,
                    quantity=item.quantity,
                    final_price=item.total_price,
                    removed=False,
                )
                for item in order.items
            ],
        )

    async def get_delivery_status(
        self, order_id: str, address_id: str
    ) -> DeliveryStatusResult:
        if order_id not in self._orders:
            raise CommerceError("Simulated order not found", code="ORDER_NOT_FOUND")
        del address_id
        return DeliveryStatusResult(
            order_id=order_id,
            eta_text="12 minutes",
            cancelled=False,
            delivered=False,
            status_text="Simulated packing",
            poll_interval_sec=10,
        )

    async def track_order(self, order_id: str) -> DeliveryTrackingStatus:
        if order_id not in self._orders:
            raise CommerceError("Simulated order not found", code="ORDER_NOT_FOUND")

        return DeliveryTrackingStatus(
            order_id=order_id,
            status="PACKING",
            raw_status="SIMULATED_PACKING",
            eta_minutes=12,
            driver_name="Ramesh Kamble",
            driver_phone="+91 98201 12345",
        )
