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

    def set_address(self, address_id: str, label: str, confirmed: bool = True) -> None:
        """Atomically lock the active delivery address and label."""
        self.address_id = address_id
        self.address_label = label
        self.order_address_confirmed = confirmed
        self.awaiting_address_choice = None

    def reset_order_address(self) -> None:
        """Reset address confirmation after checkout or cart clear so next new order asks again."""
        self.address_id = None
        self.address_label = None
        self.order_address_confirmed = False
        self.awaiting_address_choice = None

    def clear_all(self) -> None:
        """Completely reset session history and address state."""
        if self.history is not None:
            self.history.clear()
        else:
            self.history = []
        self.reset_order_address()
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
