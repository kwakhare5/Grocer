# ADR 0009: Product Experience Guardrails: Destinations, Recipes, Post-Order Additions, and Fee Shock

> **Status 2026-10-27:** Not built yet. Pieces exist for the fee warning and post-order copy, but no flow is wired. Do not describe any of them as live. See `STATUS.md` §5.
> **Amendment 2026-10-27 (Karan):** Recipes are in v1 as a plan-confirm-add flow: propose the checklist and pack counts, wait for a tap, then write. The fee warning and the post-order truth reply are Phase 7. One-time destination is parked pending Karan's decision. Proactivity stays limited to money and truth; no upsell.

## Context
Real-world WhatsApp grocery shopping introduces critical behavioral edge cases where standard commerce bots fail user trust:
1. Ordering groceries for relatives or alternative locations ("Send to Mom in Delhi") risks permanently overwriting the user's home delivery address.
2. Recipe queries ("make Aglio Olio") risk dumping unnecessary expensive kitchen staples into the basket without user consent.
3. Users attempting to append forgotten items to an active order cannot be fulfilled because Swiggy dark stores lock orders immediately upon placement.
4. Small orders (e.g. ₹14 Maggi) incur delivery, handling, and small-cart fees that can exceed the item price 3x to 5x.

## Decision
1. **One-Time Destination Anchoring**: When a customer specifies an explicit delivery destination for another recipient or address, Grocer fulfills that order against the specified address's dark store, but preserves the customer's primary address as the default for subsequent turns.
2. **Conversational Recipe Checklists**: For recipe or meal inquiries, Grocer presents an ingredient checklist first, assuming standard kitchen pantry staples (salt, water, common spices) are present, and provides interactive buttons: `[Add All Ingredients]` and `[Let Me Pick]`.
3. **Radical Truth on Post-Order Additions**: Because Swiggy MCP locks placed orders, Grocer explains that the dark store is actively packing the order and offers an immediate 1-tap separate order for the forgotten item to the same address.
4. **Small-Cart Fee Shock Protection**: When delivery, handling, or small-order fees exceed 35% of the item total, Grocer issues a friendly heads-up showing the exact fee breakdown and suggests common staples (milk, eggs) to hit the dark store's free-delivery threshold, offering `[Add Essentials]` alongside `[Proceed with Fees]`.

## Consequences
- Prevents accidental misdeliveries to past one-time addresses.
- Protects customers from unexpected recipe cart totals.
- Eliminates false promises regarding in-flight order changes.
- Maximizes customer trust and saves money by avoiding punitive small-cart fees.
