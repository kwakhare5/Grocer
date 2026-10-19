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
    current_turn_original_message: Optional[str] = None
    dropped_requested_items: list[str] = field(default_factory=list)
    item_reasons: dict[str, str] = field(default_factory=dict)

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
            spin = p.get("spin_id") or p.get("sku_id")
            pid = p.get("product_id") or p.get("id")
            name = p.get("name")
            pack_size = p.get("pack_size")
            norm_name = " ".join(str(name).split()).casefold() if name else ""
            p_pack_norm = str(pack_size).strip().casefold() if pack_size and str(pack_size).strip() else None

            idx = -1
            for i, existing in enumerate(self.recent_product_facts):
                ex_spin = existing.get("spin_id") or existing.get("sku_id")
                ex_pid = existing.get("product_id") or existing.get("id")
                ex_name = existing.get("name")
                ex_pack_size = existing.get("pack_size")
                norm_ex_name = " ".join(str(ex_name).split()).casefold() if ex_name else ""
                ex_pack_norm = str(ex_pack_size).strip().casefold() if ex_pack_size and str(ex_pack_size).strip() else None

                if spin:
                    if ex_spin:
                        if ex_spin == spin:
                            idx = i
                            break
                    else:
                        # Existing fact saved with product_id only
                        if pid and ex_pid and pid == ex_pid:
                            name_compat = not norm_name or not norm_ex_name or norm_name == norm_ex_name
                            pack_compat = not p_pack_norm or not ex_pack_norm or p_pack_norm == ex_pack_norm
                            if name_compat and pack_compat:
                                idx = i
                                break
                else:
                    # New fact has no spin
                    if ex_spin:
                        # Existing fact has spin: match by same pid + normalized name + compatible pack size
                        if pid and ex_pid and pid == ex_pid:
                            name_compat = not norm_name or not norm_ex_name or norm_name == norm_ex_name
                            pack_compat = not p_pack_norm or not ex_pack_norm or p_pack_norm == ex_pack_norm
                            if name_compat and pack_compat:
                                idx = i
                                break
                    else:
                        # Existing fact has no spin either
                        if pid and ex_pid and pid == ex_pid:
                            name_compat = not norm_name or not norm_ex_name or norm_name == norm_ex_name
                            pack_compat = not p_pack_norm or not ex_pack_norm or p_pack_norm == ex_pack_norm
                            if name_compat and pack_compat:
                                idx = i
                                break
                        elif (not pid or not ex_pid) and norm_name and norm_name == norm_ex_name:
                            # In the no-pid name match, merge only when pack sizes are equal, or both are missing. Never merge when only one side has a pack size.
                            if p_pack_norm == ex_pack_norm:
                                idx = i
                                break

            if idx >= 0:
                merged = dict(self.recent_product_facts[idx])
                incoming_clean = {
                    k: v for k, v in p.items()
                    if v is not None and not (isinstance(v, str) and v.strip() == "")
                }
                for k, v in incoming_clean.items():
                    merged[k] = v
                self.recent_product_facts[idx] = merged
            else:
                self.recent_product_facts.append(dict(p))

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
        self.item_reasons.clear()

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
        self.current_turn_original_message = None
        self.dropped_requested_items.clear()
        self.item_reasons.clear()
