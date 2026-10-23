# PRD.md — Grocer v5.0 Product Requirements Document

> **Product:** Grocer — Swiggy Instamart WhatsApp Concierge  
> **Status:** Agreed & Authoritative Product Requirements (v5.0 Clean-Slate)  
> **Target Audience:** Indian urban households & quick-commerce grocery shoppers on WhatsApp  

---

## 1. Product Vision & Overview

Grocer is a conversational WhatsApp grocery concierge connected directly to live Swiggy Instamart dark stores. 

It allows customers to send grocery lists in natural everyday language (including Hindi and Hinglish terms), recipes, or vague requests, and get their exact groceries delivered in 10–15 minutes with zero friction, radical honesty, and maximum rupee savings.

---

## 2. Universal Non-Negotiables & Invariants

1. **Real Data Over Speed & Zero Mocks:**
   - Every dark-store product search, live stock count, price, address book entry, coupon, and payment link MUST come directly from live Swiggy Instamart MCP servers (`https://mcp.swiggy.com/im`).
   - Zero mocking of commerce adapters, databases, or pricing logic in production or automated tests.
2. **Zero Assumptions & Radical Truth:**
   - Never assume what a customer wants. If an item is specific (*"The Health Factory zero maida brown bread"*), never substitute with white bread or another brand.
   - If an item is out of stock, if a dark store is closed, or if an API error occurs, communicate the exact truth in plain, human English. Never silently omit items from a basket.
3. **Customer Advocate Engine (Champion the Wallet):**
   - Automatically find and apply the best valid Swiggy coupon.
   - **Critical Guardrail:** Never apply a coupon if the final payable total increases (e.g. dropping below a free-delivery cutoff).
   - Display verified rupee savings clearly on the receipt (*"Total Saved: ₹X"*).
4. **Sensible Defaults on Vague Requests:**
   - When a request is completely unqualified (e.g. *"milk"*, *"bread"*, *"eggs"*), pick the active dark store's #1 standard staple (e.g. 500ml toned milk) and provide a 1-tap "Change Items" button.
5. **Conversational Disambiguation for High-Variety Items:**
   - When a request involves high-variety snacks or drinks (e.g. *"chips"*, *"cold coffee"*), present 2–3 in-stock options conversationally rather than guessing a random flavor.
6. **1-Tap Mobile Payment via Swiggy HTTPS `bridgeUrl`:**
   - Meta WhatsApp CTA buttons only support `https://`. Checkout delivers Swiggy's secure HTTPS `bridgeUrl`, allowing 1-tap payment via Google Pay, PhonePe, Paytm, or COD where supported.
7. **Python Muscle vs. Gemini Brain (The 3-Lock Safety Latch):**
   - Gemini interprets language, resolves multi-item lists, and drafts conversational summaries.
   - Python deterministically enforces math, budget caps, cart SHA-256 fingerprints, and checkout gates.
   - **Lock 1 (Authority):** An order can ONLY be placed if the customer physically taps a WhatsApp button. Typing text ("yes", "confirm", "proceed") is strictly rejected from spending money.
   - **Lock 2 (Truth):** Live cart re-verification confirms 100% stock and exact paise math before checkout.
   - **Lock 3 (Exactly-Once):** Atomic PostgreSQL CAS prevents double-debiting on mobile retries.
8. **5-Day Token Expiry & Parked Message Replay:**
   - Swiggy v1.0 OAuth tokens expire after 5 days with zero refresh tokens.
   - When an expired session texts a grocery list, Grocer parks the list in PostgreSQL, presents a 1-tap `[Connect Swiggy]` button, and immediately replays the list upon login completion without asking the user to retype it.
9. **DPDP Compliance & 24-Hour Data Minimization:**
   - Personal customer delivery addresses and basket snapshots are permanently deleted from database storage 24 hours post-order. Minimal transaction metadata is kept for 90 days.
   - Typing `"delete my data"` instantly wipes all customer history and revokes tokens.
10. **Strict English Voice:**
    - The bot understands customer inputs in any style (English, Hindi, Hinglish), but always responds in clear, warm, conversational English.

---

## 3. Core Customer Journeys

### Journey 1: Vague & Specific Grocery Lists
- Customer texts *"Get 1L toned milk, brown bread, and 6 eggs"*.
- Grocer searches the dark store, matches variants, builds the cart, and outputs a clear WhatsApp receipt with exact prices and a `[Pay ₹X via UPI]` button.

### Journey 2: Conversational Questions (No Forced Checkout)
- Customer asks *"Wait, do you have sourdough bread?"* or *"What is the delivery fee?"*.
- Grocer answers the question naturally without forcing a cart receipt or checkout button.

### Journey 3: Out-of-Stock Radical Honesty
- Customer requests an item that is sold out.
- Grocer adds what is in stock, leaves the unavailable item out, and prominently highlights it on the receipt: *"Not added (Out of stock at your store): X. Available alternative: Y."*

### Journey 4: 1-Tap Checkout & Milestone Tracking
- Customer taps `[Pay ₹X via UPI]`. Swiggy's secure web payment screen opens.
- After payment, Grocer sends 3 milestone notifications:
  1. *Order confirmed & packed*
  2. *Rider picked up & on the way* (with live GPS tracking map link)
  3. *Order delivered*

---

## 4. Release Gates & Success Metrics

1. **Staging Contract Gate:** 100% of commerce parsers validated against real Swiggy staging fixtures.
2. **Deterministic Safety Gate:** 0 duplicate orders and 0 unapproved checkouts across 500 simulated stress turns.
3. **Turn Latency Gate:** Average turn latency under 3.5 seconds.
4. **Wallet Advocacy Gate:** Verified 100% coupon accuracy with 0 cases of coupon application increasing the net total.
