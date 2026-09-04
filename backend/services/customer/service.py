"""Customer service for Phase 9 Customer / WhatsApp replenishment simulation.

Handles customer retrieval, household pantry depletion forecasting,
WhatsApp conversational alert generation, 1-tap reorder execution with dark store
inventory deduction, reminder scheduling, and skip tracking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.core import (
    Customer, Store, Product, Inventory, Order, OrderItem,
)
from backend.models.enums import OrderStatus, StoreStatus
from backend.events.bus import bus
from backend.services.customer.models import (
    PantryStapleState, CustomerState, WhatsAppInteractionMessage,
    CustomerReorderResult,
)


class CustomerService:
    """Core service for customer household simulation and WhatsApp replenishment."""

    async def list_customers(self, db: AsyncSession) -> list[dict[str, Any]]:
        """List all customers with home store linkage and quick pantry status."""
        stmt = (
            select(Customer, Store.name.label("store_name"))
            .join(Store, Customer.home_store_id == Store.store_id)
            .order_by(Customer.name)
        )
        results = (await db.execute(stmt)).all()

        customers: list[dict[str, Any]] = []
        for row in results:
            cust: Customer = row[0]
            store_name: str = row[1]
            
            # Fetch latest order to determine days since last delivery
            latest_order_stmt = (
                select(Order.created_at)
                .where(Order.customer_id == cust.customer_id)
                .order_by(desc(Order.created_at))
                .limit(1)
            )
            latest_order_time = (await db.execute(latest_order_stmt)).scalar_one_or_none()

            # Default staple depletion (milk low by default for simulation demo)
            customers.append({
                "customer_id": str(cust.customer_id),
                "name": cust.name,
                "home_store_id": str(cust.home_store_id),
                "home_store_name": store_name,
                "staple_count": 4,
                "critical_staple": "Amul Milk 1L",
                "days_left": 1.0,
                "fill_pct": 15,
                "last_order_at": latest_order_time.isoformat() if latest_order_time else None,
            })

        return customers

    async def get_customer(self, db: AsyncSession, customer_id: uuid.UUID) -> Optional[dict[str, Any]]:
        """Get detailed customer profile with current pantry depletion state."""
        stmt = (
            select(Customer, Store.name.label("store_name"))
            .join(Store, Customer.home_store_id == Store.store_id)
            .where(Customer.customer_id == customer_id)
        )
        row = (await db.execute(stmt)).first()
        if not row:
            return None

        cust: Customer = row[0]
        store_name: str = row[1]

        # Fetch products to construct pantry items
        prod_stmt = select(Product).limit(10)
        products = (await db.execute(prod_stmt)).scalars().all()
        
        # Build pantry staple states
        staples = self._build_pantry_staples(products)

        return {
            "customer_id": str(cust.customer_id),
            "name": cust.name,
            "home_store_id": str(cust.home_store_id),
            "home_store_name": store_name,
            "staples": staples,
        }

    async def get_whatsapp_messages(
        self, db: AsyncSession, customer_id: uuid.UUID
    ) -> Optional[dict[str, Any]]:
        """Generate conversational WhatsApp context and proactive alert for customer."""
        customer_data = await self.get_customer(db, customer_id)
        if not customer_data:
            return None

        customer_name = customer_data["name"]
        first_name = customer_name.split()[0]

        messages = [
            {
                "sender": "bot",
                "text": (
                    f"👋 Good morning, {first_name}!\n\n"
                    "Prophet ML detected your 1L Amul Milk 🥛 is running out tomorrow morning "
                    "(15% stock left).\n\n"
                    "Would you like to restock now before breakfast?"
                ),
                "timestamp": "08:00 AM",
                "quick_actions": [
                    "Confirm 1-Tap Restock 🥛",
                    "Add Bread (+₹50) 🍞",
                    "Remind Tomorrow ⏰",
                    "Skip This Week ✕",
                ],
            }
        ]

        return {
            "customer_id": str(customer_id),
            "customer_name": customer_name,
            "home_store_name": customer_data["home_store_name"],
            "messages": messages,
        }

    async def process_user_message(
        self, db: AsyncSession, customer_id: uuid.UUID, message_text: str
    ) -> dict[str, Any]:
        """Process conversational reply in the WhatsApp simulator."""
        customer_data = await self.get_customer(db, customer_id)
        first_name = customer_data["name"].split()[0] if customer_data else "there"
        normalized = message_text.strip().lower()

        timestamp = datetime.now(timezone.utc).strftime("%I:%M %p")

        if "bread" in normalized:
            return {
                "reply": "➕ Added 1× Whole Wheat Bread 400g (₹50) to your restock batch.\n\n🛒 Subtotal: ₹116 (Delivery: FREE)\nTap below to confirm via UPI or Cash on Delivery.",
                "stage": "breakdown",
                "timestamp": timestamp,
                "quick_actions": ["Pay via UPI (₹116) ⚡", "Cash on Delivery 💵"],
            }
        elif "remind" in normalized or "later" in normalized or "tomorrow" in normalized:
            await bus.publish(
                db,
                "CUSTOMER_REMINDER_SCHEDULED",
                "customer",
                customer_id,
                {"customer_id": str(customer_id), "delay_hours": 24},
            )
            return {
                "reply": f"⏰ Scheduled reminder! We will alert you tomorrow at 08:00 AM before breakfast.",
                "stage": "reminded",
                "timestamp": timestamp,
                "quick_actions": ["View Pantry Health 📊"],
            }
        elif "skip" in normalized:
            await bus.publish(
                db,
                "CUSTOMER_RESTOCK_SKIPPED",
                "customer",
                customer_id,
                {"customer_id": str(customer_id), "reason": "user_skipped"},
            )
            return {
                "reply": f"👍 Got it, {first_name}. Restock alert skipped for this week. Your pantry forecast has been updated.",
                "stage": "skipped",
                "timestamp": timestamp,
                "quick_actions": ["View Pantry Health 📊"],
            }
        elif "yes" in normalized or "confirm" in normalized or "pay" in normalized:
            return {
                "reply": "🛒 Ready to confirm! Select payment method below to dispatch directly from your local dark store.",
                "stage": "breakdown",
                "timestamp": timestamp,
                "quick_actions": ["Pay via UPI (₹116) ⚡", "Cash on Delivery 💵"],
            }
        else:
            return {
                "reply": f"I can help restock your household essentials, check pantry levels, or schedule 1-tap reorders. What would you like to do?",
                "stage": "initial",
                "timestamp": timestamp,
                "quick_actions": ["Confirm 1-Tap Restock 🥛", "Add Bread (+₹50) 🍞", "Remind Tomorrow ⏰"],
            }

    async def reorder(
        self,
        db: AsyncSession,
        customer_id: uuid.UUID,
        items: Optional[list[dict[str, Any]]] = None,
    ) -> CustomerReorderResult:
        """Execute 1-tap WhatsApp customer replenishment.

        - Deducts stock from customer's home Dark Store inventory.
        - Creates Order and OrderItem records.
        - Publishes ORDER_PLACED and INVENTORY_CHANGED events.
        - Restores customer pantry state to 100%.
        """
        # 1. Fetch customer and home store
        cust_stmt = (
            select(Customer, Store)
            .join(Store, Customer.home_store_id == Store.store_id)
            .where(Customer.customer_id == customer_id)
        )
        row = (await db.execute(cust_stmt)).first()
        if not row:
            raise ValueError(f"Customer {customer_id} not found")

        cust: Customer = row[0]
        store: Store = row[1]

        # 2. Resolve items to order
        resolved_items: list[dict[str, Any]] = []
        total_amount = 0.0

        if items and len(items) > 0:
            for it in items:
                prod_id = uuid.UUID(str(it["product_id"])) if isinstance(it["product_id"], str) else it["product_id"]
                qty = int(it.get("quantity", 1))
                prod = await db.get(Product, prod_id)
                if prod:
                    resolved_items.append({
                        "product_id": prod.product_id,
                        "product_name": prod.name,
                        "quantity": qty,
                        "price": float(prod.base_price),
                    })
                    total_amount += float(prod.base_price) * qty
        else:
            # Default replenishment items: Milk + Bread
            prod_stmt = select(Product).where(Product.category.in_(["dairy", "bakery"])).limit(2)
            prods = (await db.execute(prod_stmt)).scalars().all()
            for prod in prods:
                qty = 1
                resolved_items.append({
                    "product_id": prod.product_id,
                    "product_name": prod.name,
                    "quantity": qty,
                    "price": float(prod.base_price),
                })
                total_amount += float(prod.base_price) * qty

        # 3. Create Order
        order_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        order = Order(
            order_id=order_id,
            customer_id=customer_id,
            store_id=store.store_id,
            created_at=now,
            status=OrderStatus.DELIVERED,
        )
        db.add(order)

        # 4. Create OrderItems & Deduct Store Inventory
        store_inventory_updated: dict[str, int] = {}
        for item in resolved_items:
            order_item = OrderItem(
                id=uuid.uuid4(),
                order_id=order_id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                price=item["price"],
            )
            db.add(order_item)

            # Deduct from Inventory
            inv_stmt = select(Inventory).where(
                Inventory.store_id == store.store_id,
                Inventory.product_id == item["product_id"],
            )
            inv = (await db.execute(inv_stmt)).scalar_one_or_none()
            if inv:
                inv.quantity = max(0, inv.quantity - item["quantity"])
                store_inventory_updated[str(item["product_id"])] = inv.quantity

        await db.flush()

        # 5. Publish events to event bus
        await bus.publish(
            db,
            "ORDER_PLACED",
            "order",
            order_id,
            {
                "order_id": str(order_id),
                "customer_id": str(customer_id),
                "customer_name": cust.name,
                "store_id": str(store.store_id),
                "store_name": store.name,
                "items": [
                    {
                        "product_id": str(it["product_id"]),
                        "product_name": it["product_name"],
                        "quantity": it["quantity"],
                        "price": it["price"],
                    }
                    for it in resolved_items
                ],
                "total_amount": total_amount,
                "timestamp": now.isoformat(),
            },
        )

        await bus.publish(
            db,
            "INVENTORY_CHANGED",
            "store",
            store.store_id,
            {
                "store_id": str(store.store_id),
                "store_name": store.name,
                "updated_quantities": store_inventory_updated,
            },
        )

        await db.commit()

        return CustomerReorderResult(
            order_id=order_id,
            customer_id=customer_id,
            customer_name=cust.name,
            store_id=store.store_id,
            store_name=store.name,
            items=[
                {
                    "product_id": str(it["product_id"]),
                    "product_name": it["product_name"],
                    "quantity": it["quantity"],
                    "price": it["price"],
                }
                for it in resolved_items
            ],
            total_amount=total_amount,
            status="confirmed",
            created_at=now,
            pantry_restored=True,
            store_inventory_updated=store_inventory_updated,
        )

    async def remind(
        self, db: AsyncSession, customer_id: uuid.UUID, delay_hours: int = 24
    ) -> dict[str, Any]:
        """Schedule a proactive reminder for the customer."""
        customer = await db.get(Customer, customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=delay_hours)

        await bus.publish(
            db,
            "CUSTOMER_REMINDER_SCHEDULED",
            "customer",
            customer_id,
            {
                "customer_id": str(customer_id),
                "customer_name": customer.name,
                "delay_hours": delay_hours,
                "scheduled_time": scheduled_time.isoformat(),
            },
        )
        await db.commit()

        return {
            "customer_id": str(customer_id),
            "status": "scheduled",
            "delay_hours": delay_hours,
            "scheduled_time": scheduled_time.isoformat(),
            "message": f"Reminder scheduled for {scheduled_time.strftime('%b %d, %I:%M %p')}",
        }

    async def skip(
        self, db: AsyncSession, customer_id: uuid.UUID, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Record customer skip decision."""
        customer = await db.get(Customer, customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        await bus.publish(
            db,
            "CUSTOMER_RESTOCK_SKIPPED",
            "customer",
            customer_id,
            {
                "customer_id": str(customer_id),
                "customer_name": customer.name,
                "reason": reason or "user_skipped",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        await db.commit()

        return {
            "customer_id": str(customer_id),
            "status": "skipped",
            "reason": reason or "user_skipped",
            "message": "Restock alert skipped for current cycle.",
        }

    def _build_pantry_staples(self, products: list[Product]) -> list[dict[str, Any]]:
        """Construct standard simulated household pantry staple items."""
        return [
            {
                "id": "milk",
                "name": "Amul Taaza Milk 1L",
                "category": "dairy",
                "daily_rate": 0.48,
                "unit": "L",
                "days_left": 1.0,
                "fill_pct": 15,
                "price": 66.0,
            },
            {
                "id": "tomatoes",
                "name": "Fresh Hybrid Tomatoes 500g",
                "category": "produce",
                "daily_rate": 0.14,
                "unit": "kg",
                "days_left": 1.0,
                "fill_pct": 14,
                "price": 32.0,
            },
            {
                "id": "eggs",
                "name": "Farm Fresh Eggs (12 pcs)",
                "category": "poultry",
                "daily_rate": 2.4,
                "unit": "pcs",
                "days_left": 2.0,
                "fill_pct": 35,
                "price": 90.0,
            },
            {
                "id": "bread",
                "name": "Whole Wheat Bread 400g",
                "category": "bakery",
                "daily_rate": 0.24,
                "unit": "loaf",
                "days_left": 3.0,
                "fill_pct": 65,
                "price": 50.0,
            },
        ]
