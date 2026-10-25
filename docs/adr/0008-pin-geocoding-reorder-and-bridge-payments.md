# ADR 0008: WhatsApp Location Pin Onboarding, 1-Tap Go-To Reordering, and Universal BridgeUrl Payments

## Context
1. Receiving a native WhatsApp location attachment provides geographic coordinates via `recommend_address`, but lacks essential sub-premises (flat, house number, floor) needed for dark-store rider dispatch.
2. Returning grocery customers frequently repeat weekly staples; navigating search menus introduces friction.
3. Swiggy MCP allows inline wallet debits (`paymentMethod: "SwiggyPay"`), but rejects transactions with unrecoverable errors if the customer's balance is insufficient to cover the total bill.

## Decision
1. **Two-Step Pin Geocoding Onboarding**: When a customer drops a WhatsApp GPS pin, Grocer reverse-geocodes coordinates to street and locality, then asks a single targeted follow-up for flat/house number and building name. On response, `create_address` saves the complete address directly to Swiggy.
2. **1-Tap Reordering via "Your Go-To Items"**: Grocer surfaces the customer's top 3–5 frequently ordered SKUs from `your_go_to_items` in a structured card with an `[Add All to Basket]` primary button, providing an immediate 1-tap reordering loop.
3. **Universal HTTPS BridgeUrl Payment Surface**: Grocer standardizes on Swiggy's authoritative `bridgeUrl` CTA URL button (`[Pay ₹X (UPI / Card)]`) for all non-COD checkouts. Swiggy's secure web payment screen natively surfaces UPI intent apps, dynamic QR codes, credit/debit cards, and Swiggy Money balances without chat-level balance failures.

## Consequences
- 100% address accuracy for dark-store delivery riders.
- Zero-friction repeat shopping for everyday staples.
- Zero payment rejection anomalies from insufficient wallet balances in chat.
