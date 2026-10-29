# ADR 0005: Cart Sync, Fast Coupons, Address Grounding, and WhatsApp Payment Buttons

> **Status 2026-10-27:** Partial. Current checkout buttons are Pay + Clear only. COD, Change Address and Change Items are target. Coupon trials are capped at 2, but savings is not displayed. See `STATUS.md`.
> **Amendment 2026-10-29:** add receipts carry Pay, View basket, Keep only new and Change item (max 3 buttons); the savings line is displayed; the clear button reads "Clear basket".

## Context
1. In high-velocity dark-store grocery commerce, product inventory fluctuates in real-time. Items in a customer's active basket can sell out between conversational turns.
2. Swiggy Instamart exposes applicable coupon codes without discount magnitudes and provides no "undo coupon" tool. Exhaustive trial-and-reset loops over 5+ coupons degrade turn latency to 10–15 seconds.
3. Requiring address selection upfront creates unnecessary friction for returning customers who deliver to their primary address 85%+ of the time.
4. Meta WhatsApp interactive messages enforce a hard maximum of 3 buttons per message.

## Decision
1. **Non-Blocking Out-of-Stock Reconciliation**: When an existing basket item becomes unavailable during an update, Grocer excludes it from the `update_cart` target list, preserves remaining items, and prominently outputs the dropped item under a dedicated **"Not added (Out of stock)"** card section on the receipt.
2. **Fast & Smart Coupon Bounding**: Grocer bounds coupon optimization to at most the **top 2 applicable coupons**. If the first coupon produces a net savings on the payable total, it is locked in. If neither improves the bill, the cart is reset to the uncouponed baseline. Turn latency is strictly prioritized (<4 seconds).
3. **Zero-Friction Home Address Auto-Grounding**: On cold start or session initiation, Grocer auto-grounds to the customer's primary ("Home") address. The destination is explicitly presented on the receipt (`📍 Delivering to: Home`), accompanied by a 1-tap `[Change Address]` button that surfaces a WhatsApp interactive list picker of saved addresses.
4. **Native Payment Buttons**: Grocer leverages WhatsApp's 3-button capacity for mobile-first checkout:
   - Button 1: `[Pay ₹X (UPI / Card)]` (URL button opening Swiggy HTTPS `bridgeUrl`)
   - Button 2: `[Cash on Delivery]` (if enabled for the active dark store) or `[More Ways to Pay]`
   - Button 3: `[Change Items]` (quick-reply button returning to conversational cart editing)

## Consequences
- Fast turn latency (<4s) without frozen shopping sessions.
- Maximum checkout conversion via 1-tap mobile payment buttons.
- Clear geographical grounding with zero upfront friction.
- Radical honesty: customers are never blindsided by dropped or missing products.
