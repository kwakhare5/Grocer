# ADR 0004: Vague Staples, Disambiguation, Button-Only Checkout, and Parked Replay

## Context
Real-world customer behavior on WhatsApp diverges into high-frequency edge cases:
1. Customers use vague grocery keywords ("milk", "bread", "atta") without specifying pack size or brand.
2. Customers request high-variety snack or beverage categories ("chips", "cold coffee") with dozens of competing flavors and pack sizes.
3. Inbound conversational messages containing "yes" or "proceed" were previously intercepted to trigger checkout, leading to accidental order placements when customers typed sentences like "yes, but remove the butter".
4. Swiggy v1.0 OAuth tokens expire after 5 days with zero refresh tokens, causing returning customers to lose typed shopping lists when prompted to re-authenticate.

## Decision
1. **Vague Staple Auto-Selection**: For completely unqualified staple requests ("milk", "bread", "eggs"), Grocer auto-selects the active dark store's #1 in-stock staple variant (e.g. 500ml toned milk) and provides a 1-tap "Change Items" button. If the customer specifies any brand, pack size, or attribute, Grocer strictly adheres to it without substituting.
2. **Snack/Beverage Disambiguation**: For high-variety categories lacking a single universal staple, Gemini presents 2–3 in-stock brand/flavor options conversationally rather than guessing blindly.
3. **Button-Only Checkout Latch (Lock 1 Authority)**: Orders can ONLY be placed via physical interactive button taps (`pay:<approval_id>:<option>`). Natural language text ("yes", "confirm", "proceed") is strictly rejected from triggering financial transactions, preventing prompt injections and accidental charges.
4. **Parked Message Replay**: When an unauthenticated or expired customer texts a shopping list, Grocer durably records the message with status `awaiting_link` in PostgreSQL and presents a WhatsApp CTA login button. Upon successful OAuth callback, Grocer automatically replays the parked message without requiring the customer to retype it.

## Consequences
- Fast, zero-friction flow for common daily staples.
- High accuracy for snacking/beverage requests without wrong-item drops.
- 100% financial safety: Gemini cannot be tricked by text into spending money.
- Seamless re-authentication UX across 5-day Swiggy token boundaries.
