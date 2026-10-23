# ADR 0004: Smart Kirana Defaults, Physical Button Checkout Authority, and Parked Replay

## Context
Real-world customer behavior on WhatsApp diverges into high-frequency edge cases:
1. **Lazy Messaging:** Shoppers text vague keywords (*"milk"*, *"bread"*, *"atta"*). Inquiring about 5 different attributes (brand, fat, pack size) creates friction and causes user abandonment.
2. **Accidental Spending via Text:** In natural conversation, users send messages like *"yes, but please remove the butter"* or *"confirm, but change the address"*. If an AI triggers checkout on the word "yes", the customer is charged prematurely for unwanted items.
3. **Session Expiration Frustration:** Swiggy OAuth tokens expire after 5 days with zero refresh tokens. Losing a carefully typed grocery list upon session expiry creates severe frustration.

## Decision
1. **Smart Kirana Defaults for Vague Staples**: For unqualified staple requests (*"milk"*, *"bread"*, *"eggs"*), Grocer auto-selects the local dark store's #1 bestselling staple (e.g. 500ml toned milk) and provides a 1-tap `[Change Items]` button. If the customer specifies any brand or attribute, Grocer adheres strictly to it.
2. **Snack/Beverage Disambiguation**: For high-variety categories lacking a single universal staple (*"chips"*, *"cold coffee"*), Grocer presents 2–3 in-stock brand/flavor options conversationally rather than guessing blindly.
3. **Physical Button Tap Only (Lock 1 Authority)**: An order can ONLY be authorized if the customer physically taps a WhatsApp button (`pay:<approval_id>:<option>`). Natural language text ("yes", "confirm", "proceed") is strictly rejected from triggering financial transactions, eliminating accidental charges and prompt injection risks.
4. **Parked Message Replay**: When an expired or unauthenticated customer texts a grocery list, Grocer durably records the message in PostgreSQL and delivers a 1-tap `[Connect Swiggy]` button. Upon successful login callback, Grocer automatically replays the list without requiring the customer to retype it.

## Consequences
- Fast, effortless ordering experience for daily essentials.
- Zero accidental orders caused by natural language ambiguities.
- Complete financial safety: AI cannot be tricked by text into spending money.
- Seamless re-authentication without losing shopping context.
