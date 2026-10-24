# Grocer

WhatsApp consumer grocery concierge for Swiggy Instamart with deterministic intent verification and wallet advocacy.

## Language

**Basket**:
The active set of grocery items the customer intends to purchase from Swiggy Instamart.  
_Avoid_: Cart, bag, order list

**Receipt Card**:
The deterministic WhatsApp message displaying itemized prices, delivery and packaging fees, taxes, discounts, and grand total in Indian Rupees (₹).  
_Avoid_: Bill, invoice, checkout summary

**Fast Button Router**:
A pure-Python dispatcher executing WhatsApp interactive button taps (confirm order, clear basket, select address) in under 50ms without LLM overhead.  
_Avoid_: Action handler, webhook dispatcher

**Three-Lock Checkout**:
A cryptographic gate requiring a verified delivery address, non-empty basket, and matching SHA-256 cart fingerprint before generating a payment link.  
_Avoid_: Checkout validation, purchase check

**Customer Advocate**:
The engine that automatically applies the highest-saving Swiggy coupon and proactively recommends small staples to cross free-delivery thresholds when it saves the customer net money.  
_Avoid_: Discount engine, coupon bot

**Live Address Grounding**:
Grounding delivery exclusively in the customer's real Swiggy address book, with direct in-chat address creation via text or WhatsApp GPS pins.  
_Avoid_: Hardcoded locations, default areas, simulated addresses
