"""Stage 3: Payment Stage.

Handles smart payment method grouping (collapsing 11 gateways into clean consumer categories),
choice resolution, persistence, and non-trapping grocery modification fallback.
"""
from __future__ import annotations

from typing import Optional

from backend.integrations.commerce.models import PaymentOption


def _msg_payment_choice(options: list[PaymentOption]) -> str:
    lines = ["Which payment method would you like to use?"]
    lines.extend(f"{index}. {option.label}" for index, option in enumerate(options, 1))
    lines.append("Reply with the number or name of your choice.")
    return "\n".join(lines)


def _payment_option_key(option: PaymentOption) -> str:
    return option.id or option.method


def _group_payment_options(options: list[PaymentOption]) -> list[PaymentOption]:
    """Collapse provider's raw payment options into clean, high-level consumer categories.

    Categories:
    1. UPI (GPay, PhonePe, Paytm, BHIM)
    2. Pay on Delivery (Cash)
    3. Credit / Debit Card
    4. Net Banking & Wallets

    If the list is already short (<= 4 options) and has no redundant multi-gateway duplicates,
    preserve it as is.
    """
    if len(options) <= 4:
        return options

    upi_opts: list[PaymentOption] = []
    cod_opts: list[PaymentOption] = []
    card_opts: list[PaymentOption] = []
    netbanking_opts: list[PaymentOption] = []
    other_opts: list[PaymentOption] = []

    for opt in options:
        lowered_label = opt.label.lower()
        lowered_id = (opt.id or "").lower()
        lowered_method = opt.method.lower()

        if (
            opt.method.upper() == "UPI"
            or opt.kind in ("intent", "qr")
            or "upi" in lowered_id
            or "upi" in lowered_label
            or any(
                brand in lowered_label or brand in lowered_id
                for brand in ("gpay", "google pay", "phonepe", "paytm", "bhim", "cred", "super.money", "famapp", "qr")
            )
        ):
            upi_opts.append(opt)
        elif (
            "cash" in lowered_method
            or "cod" in lowered_method
            or "pay on delivery" in lowered_label
            or "cash on delivery" in lowered_label
            or "cash" in lowered_label
        ):
            cod_opts.append(opt)
        elif "card" in lowered_method or "card" in lowered_label:
            card_opts.append(opt)
        elif (
            "netbanking" in lowered_method
            or "wallet" in lowered_method
            or "swiggy" in lowered_label
            or "net banking" in lowered_label
            or "money" in lowered_label
        ):
            netbanking_opts.append(opt)
        else:
            other_opts.append(opt)

    grouped: list[PaymentOption] = []

    if upi_opts:
        pref_order = ("gpay", "phonepe", "bhim", "paytm")
        rep_upi = next(
            (
                o
                for pref in pref_order
                for o in upi_opts
                if pref in (o.id or "").lower() or pref in o.label.lower()
            ),
            upi_opts[0],
        )
        label = "UPI (GPay / PhonePe / Paytm / BHIM)" if len(upi_opts) > 1 else rep_upi.label
        grouped.append(
            PaymentOption(
                method="UPI",
                label=label,
                is_available=True,
                id=rep_upi.id or "UPI",
                kind=rep_upi.kind or "intent",
                description="Instant payment via any UPI app",
            )
        )

    if cod_opts:
        rep_cod = cod_opts[0]
        grouped.append(
            PaymentOption(
                method=rep_cod.method or "Cash",
                label="Pay on Delivery (Cash)",
                is_available=True,
                id=rep_cod.id or "Cash",
                kind=None,
                description="Pay with cash or UPI at delivery",
            )
        )

    if card_opts:
        rep_card = card_opts[0]
        grouped.append(
            PaymentOption(
                method=rep_card.method or "Card",
                label="Credit / Debit Card",
                is_available=True,
                id=rep_card.id or "Card",
                kind=None,
            )
        )

    if netbanking_opts:
        rep_nb = netbanking_opts[0]
        grouped.append(
            PaymentOption(
                method=rep_nb.method or "NetBanking",
                label="Net Banking & Wallets",
                is_available=True,
                id=rep_nb.id or "NetBanking",
                kind=None,
            )
        )

    grouped.extend(other_opts)
    return grouped or options
