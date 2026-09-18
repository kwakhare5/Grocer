# GROCER reviewer walkthrough

GROCER is an English-only WhatsApp grocery agent. This walkthrough is the release target for the durable ShoppingTask route; that route is implemented but not yet live. It uses Swiggy Instamart through the `CommercePort` boundary and preserves the user's stated shopping intent when commerce conditions change.

## Before a reviewer starts

Use a Swiggy account and a Meta WhatsApp test number that have been connected to
the configured deployment. The landing page is only the explanation and Swiggy
connection entry point; the shopping conversation happens in WhatsApp.

`CHECKOUT_MODE=review` is the submission default. It exercises the real cart,
address, payment, verification, and confirmation journey, then truthfully stops
before a chargeable order is created.

## Review paths

### 1. Normal basket

Send: `Please get 2 litres of milk, one bread, and 12 eggs under ₹500.`

Expected: GROCER resolves the complete desired basket, shows a basket preview, and waits for approval before changing the provider cart. If the linked Swiggy cart already has items, GROCER first offers Keep it, Start fresh, or Cancel. After an approved, verified cart update, it presents address and payment choices, then shows an explicit checkout confirmation. It must not checkout before the reviewer confirms.

### 2. Product decision

Ask for a named brand or pack size, then choose a different product from a
WhatsApp list. Expected: the choice is bound to the active session and product
option; an old list selection is rejected safely rather than applied to the new
cart.

### 3. Stockout or changed price

Request an item with a strict budget or brand instruction. When the provider
cannot satisfy that instruction, GROCER explains the situation in plain English
and asks for a decision. It must not silently change the item, budget, brand,
pack, quantity, address, payment method, or checkout result.

### 4. Change before checkout

When the confirmation prompt is visible, send: `Add one more bread.`

Expected: the previous confirmation becomes invalid, the basket is rebuilt and
re-verified, and GROCER asks for confirmation again. A prior button cannot place
the changed basket.

### 5. Provider interruption

Use the supplied mock/evaluation scenario for timeout, stale cart, partial cart,
or payment-pending behavior. Expected: GROCER never invents a success, ETA, or
tracking link. It either retries only an operation known to be safe, checks the
provider's authoritative state, or clearly tells the user that the action is not
complete.

## Evidence and limits

- Run `pytest backend/tests`, `npm run lint`, and `npm run build` for local
  regression evidence. GitHub Actions runs the same checks.
- The reliability harness uses the same `CommercePort` contract with a controlled
  mock provider; it is not presented as a live order.
- Local files are development-only state. A production/live-checkout deployment
  requires a durable encrypted PostgreSQL store for sessions, OAuth tokens,
  webhook idempotency, and checkout locks.
- Live checkout remains disabled until that store and a controlled real-provider
  test have been verified.
