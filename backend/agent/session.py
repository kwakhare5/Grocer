"""Atomic per-customer session state for GROCER."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from backend.agent.approval import PendingApproval


@dataclass
class CustomerSession:
    """Single source of truth for a customer's active shopping session."""

    customer_id: str
    history: list[dict[str, Any]] = field(default_factory=list)
    address_id: Optional[str] = None
    address_label: Optional[str] = None
    order_address_confirmed: bool = False
    awaiting_address_choice: Optional[list[dict[str, Any]]] = None
    last_active_ts: float = 0.0
    budget_inr: Optional[float] = None
    pending_approval: Optional[PendingApproval] = None
    pending_cart_clear: Optional[PendingApproval] = None
    unresolved_items: list[dict[str, Any]] = field(default_factory=list)
    budget_blocked_items: list[str] = field(default_factory=list)
    known_cart_fingerprint: Optional[str] = None
    external_cart_pending: bool = False
    pending_request_text: Optional[str] = None
    selected_payment_id: Optional[str] = None
    selected_payment_kind: Optional[str] = None
    selected_payment_method: Optional[str] = None
    selected_payment_label: Optional[str] = None
    recent_product_facts: list[dict[str, Any]] = field(default_factory=list)

    def set_address(self, address_id: str, label: str, confirmed: bool = True) -> None:
        """Atomically lock the active delivery address and label."""
        self.address_id = address_id
        self.address_label = label
        self.order_address_confirmed = confirmed
        self.awaiting_address_choice = None

    def update_product_facts(self, products: list[dict[str, Any]]) -> None:
        """Store or update recent product facts up to a cap of 50 items."""
        for p in products:
            if not isinstance(p, dict):
                continue
            pid = p.get("product_id") or p.get("id")
            spin = p.get("spin_id")

            idx = -1
            for i, existing in enumerate(self.recent_product_facts):
                ex_pid = existing.get("product_id") or existing.get("id")
                ex_spin = existing.get("spin_id")
                if (pid and ex_pid and pid == ex_pid) or (spin and ex_spin and spin == ex_spin):
                    idx = i
                    break
                if not pid and not spin and p.get("name") and existing.get("name") == p.get("name") and existing.get("pack_size") == p.get("pack_size"):
                    idx = i
                    break

            if idx >= 0:
                self.recent_product_facts[idx] = p
            else:
                self.recent_product_facts.append(p)

        if len(self.recent_product_facts) > 50:
            self.recent_product_facts = self.recent_product_facts[-50:]

    def clear_product_facts(self) -> None:
        """Clear session-bounded product facts."""
        self.recent_product_facts.clear()

    def reset_order_address(self) -> None:
        """Reset address confirmation after checkout or cart clear so next new order asks again."""
        self.address_id = None
        self.address_label = None
        self.order_address_confirmed = False
        self.awaiting_address_choice = None
        self.clear_product_facts()

    def clear_all(self) -> None:
        """Completely reset session history and address state."""
        if self.history is not None:
            self.history.clear()
        else:
            self.history = []
        self.reset_order_address()
        self.clear_product_facts()
        self.pending_approval = None
        self.pending_cart_clear = None
        self.unresolved_items.clear()
        self.budget_blocked_items.clear()
        self.known_cart_fingerprint = None
        self.external_cart_pending = False
        self.pending_request_text = None
        self.selected_payment_id = None
        self.selected_payment_kind = None
        self.selected_payment_method = None
        self.selected_payment_label = None
        self.last_active_ts = 0.0
        self.budget_inr = None
