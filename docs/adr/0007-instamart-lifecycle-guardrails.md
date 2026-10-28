# ADR 0007: Instamart Lifecycle Guardrails: Address Switching, Split Orders, Deletion, and Cancellation

> **Status 2026-10-27:** Active. Address switch warns, clears and rebuilds the basket at the new store and names anything the new store cannot fill. The active-delivery delete guard runs on the real delete path. Split orders poll every order id. See `STATUS.md`.

## Context
Expanding Grocer from a shopping list bot to a full WhatsApp Instamart concierge introduces four critical lifecycle edge cases:
1. Customers changing delivery addresses while holding an uncommitted basket.
2. Orders fulfilled across multiple micro-stores or partner nodes.
3. Accidental or hazardous deletion of addresses tied to active deliveries.
4. Customer requests to cancel in-flight orders where Swiggy provides no automated MCP tool.

## Decision
1. **Address Switching Mid-Basket**: When a customer switches their active delivery address while holding items in their basket, Grocer warns that dark-store inventory differs and presents interactive buttons: `[Switch & Rebuild Basket]` or `[Keep Current Address]`. On confirmation, Grocer clears the previous cart, sets the new address, and attempts to re-add in-stock items.
2. **Unified Billing with Split Tracking**: Multi-store split orders are presented as a single consolidated WhatsApp receipt with a note (*"Items will arrive from 2 nearby stores"*). Post-payment, Grocer sends discrete real-time tracking links for each fulfillment leg.
3. **Address Deletion Guardrails**: Deleting an address is strictly prohibited while an active delivery is dispatched to it. Deletion always requires tapping an interactive WhatsApp button (`[Confirm Delete: <Label>]`).
4. **Phone Escalation for Cancellations**: When a customer requests order cancellation, Grocer looks up their active order ID and outputs Swiggy Customer Care's phone number (`080-67466729`) with their Order ID, complying with Swiggy's operational protocol.

## Consequences
- Prevents cross-store SKU mismatches and checkout crashes.
- Clean customer billing experience without confusing multi-charge notifications.
- Guaranteed address safety during live deliveries.
- Full compliance with Swiggy Instamart operational boundaries.
