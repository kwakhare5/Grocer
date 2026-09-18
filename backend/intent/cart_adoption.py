"""Provider-cart ownership gate for account-level commerce carts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.integrations.commerce.models import CommerceCart
from backend.intent.task_model import ShoppingTask, TaskOperation, TaskState


def cart_fingerprint(cart: CommerceCart) -> str:
    """Return a stable fingerprint for the provider cart content Grocer observed."""
    material = [
        {
            "spin_id": item.spin_id,
            "sku_id": item.sku_id,
            "quantity": item.quantity,
            "name": item.name,
        }
        for item in sorted(cart.items, key=lambda current: (current.spin_id, current.sku_id or ""))
    ]
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def require_cart_adoption(task: ShoppingTask, cart: CommerceCart) -> bool:
    """Record an external cart and require an explicit ownership decision when needed.

    Returns ``True`` only when the current task may safely continue using the
    provider cart. An empty cart is safe; a non-empty account cart is not owned
    by a new task until the customer explicitly adopts it.
    """
    fingerprint = cart_fingerprint(cart)
    task.provider_cart.cart_id = cart.cart_id
    task.provider_cart.fingerprint = fingerprint
    task.provider_cart.last_verified_at = datetime.now(timezone.utc)

    if not cart.items:
        return True
    if task.provider_cart.adopted_by_customer:
        return True

    task.state = TaskState.NEEDS_CART_ADOPTION
    task.pending_question = (
        "I found items already in your Swiggy basket. Would you like to keep them, "
        "start a fresh basket, or cancel?"
    )
    return False


def record_cart_adoption(task: ShoppingTask, operation: TaskOperation) -> ShoppingTask:
    """Record a customer's explicit keep/start-fresh choice without clearing a cart."""
    if task.state != TaskState.NEEDS_CART_ADOPTION:
        raise ValueError("There is no existing provider cart awaiting a decision.")
    if operation == TaskOperation.ADOPT_PROVIDER_CART:
        task.provider_cart.adopted_by_customer = True
        task.state = TaskState.READY
        task.pending_question = None
        return task
    if operation == TaskOperation.START_FRESH_CART:
        # This deliberately records intent only. The later approved full-basket
        # plan owns the provider mutation; nothing is silently cleared here.
        task.provider_cart.adopted_by_customer = False
        task.state = TaskState.READY
        task.pending_question = None
        return task
    raise ValueError("Expected an adopt-cart or start-fresh-cart decision.")
