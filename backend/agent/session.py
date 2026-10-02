"""Atomic per-customer session state for GROCER."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


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
        self.history.clear()
        self.reset_order_address()
        self.last_active_ts = 0.0
