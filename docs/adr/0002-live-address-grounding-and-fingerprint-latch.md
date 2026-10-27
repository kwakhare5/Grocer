# ADR 0002: Customer Trust Contract: Radical Price Guarantee and Live Location Grounding

> **Status 2026-10-27:** Active with deviation. Grounding currently uses the first saved address, not Swiggy's default. The fingerprint includes payable paise, so any paise change fails Lock 2. See `STATUS.md` P1.

## Context
In quick-commerce grocery, two critical trust breakdowns frequently ruin customer confidence:
1. **The Price Fluctuation Trap:** A customer reviews a receipt card for ₹250 at 2:00 PM, steps away, and taps pay at 2:30 PM. In the interim, vegetable prices increased or a flash sale expired, shifting the true store cost to ₹270. Silently charging ₹270 feels deceptive and destroys customer trust.
2. **The Fictitious Location Hazard:** Grocery availability, stock counts, and prices differ between dark stores. Guessing or hardcoding delivery addresses results in charging customers for items unserviceable at their real door.

## Decision
1. **The Radical Price Guarantee**: A customer must NEVER be charged a single rupee more than what was written on the receipt they reviewed. Grocer cryptographically verifies the live Swiggy cart (using integer paise: `to_pay_paise`) at the exact second the customer taps to pay. If prices increase or items sell out—even by ₹1—checkout immediately halts, and Grocer messages: *"Hey, the price of [Item] changed at your store (+₹X). Your updated total is ₹Y. Here is your new payment link if you'd still like to proceed."*
2. **Strict Live Location Grounding**: Every catalog search, item price, and cart is anchored strictly in the customer's live Swiggy account addresses (`get_addresses`) or newly verified location pins (`create_address`). Zero addresses are ever assumed or mocked.
3. **Pure Integer Paise Financial Layer**: All prices, subtotals, delivery fees, and discount calculations are enforced strictly in integer paise (₹1 = 100 paise), permanently banning floating-point numbers from the pricing and cryptographic hashing logic.

## Consequences
- Total customer trust: customers never pay a single paisa different from their agreed receipt.
- 100% store fulfillment accuracy anchored to real physical locations.
- Zero floating-point rounding bugs.
