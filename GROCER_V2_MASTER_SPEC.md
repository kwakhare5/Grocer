# GROCER Master Product Specification

> Version: 1.0  
> Status: Official Product Definition and Customer Experience Target  

---

## 1. What Grocer Is About

Grocer is Swiggy Instamart with a WhatsApp interface. 

Instead of opening a mobile app, searching for items one by one, scrolling through endless product grids, and manually assembling a cart, the customer simply messages what they need naturally on WhatsApp. Grocer turns ordinary conversational shopping requests into real, verified grocery carts in the customer's local dark store.

Grocer is not a generic chitchat bot, a dark-store warehouse tool, or an experimental recipe generator. It is a direct, conversational shopping assistant built to make on-demand grocery ordering effortless, fast, and reliable.

---

## 2. Whom It Is For

Grocer is built for:
* **Busy Urban Consumers**: Working professionals, parents, and students who already spend their day on WhatsApp and want groceries without the friction of opening, searching, and tapping through an app.
* **Friction-Sensitive Shoppers**: Anyone tired of scrolling through 40 varieties of bread or dealing with confusing search results just to buy daily essentials.
* **Budget-Conscious Households**: Shoppers who want to set a spending limit (e.g., *"under ₹500"*) and be guaranteed that their basket stays within that limit.
* **Natural Planners**: Customers who think in dishes, cravings, or multi-item lists (*"party snacks for 4"*, *"milk, bread, and butter"*) rather than category catalogs.

---

## 3. What Grocer Does

1. **Conversational Item Intake**: Understands plain-English shopping lists, meal ingredients, single staples, or cravings without requiring rigid commands or special formatting.
2. **Real Dark-Store Sourcing**: Finds real products and verifies live stock availability at the customer's local Swiggy Instamart store.
3. **Smart Brand & Variant Selection**: Picks standard, popular in-stock items automatically (e.g., standard milk or bread) instead of interrogating the customer with brand surveys.
4. **Transparent Basket Summaries**: Delivers a clear, itemized receipt directly in WhatsApp showing product names, pack sizes, individual prices in rupees, taxes, packaging fees, delivery fees, and the grand total.
5. **Customer-Controlled Adjustments**: Allows customers to easily modify items, adjust quantities, or swap brands with a simple text reply before anything is finalized.
6. **Server-Gated Order Confirmation**: Guarantees that no order is ever placed and no payment is ever initiated until the customer explicitly inspects the bill and taps "Confirm Order".
7. **One-Tap Payment**: Delivers an official Swiggy dynamic UPI payment link (`upi://pay`) directly into the chat for seamless 1-tap mobile payment.
8. **Customer Advocate Savings**: Automatically hunts and applies the best Swiggy coupons, suggests staples to beat delivery fee thresholds, and displays total rupees saved.

---

## 4. Core Objectives

* **Conversational Simplicity**: Shopping on WhatsApp should feel as effortless as texting a family member or personal assistant.
* **Deterministic Intent Preservation**: The customer's requested items and budget are strictly preserved:
  * Zero silent drops: If an item is missing or out of stock, Grocer must explicitly say so; it never pretends the item was never asked for.
  * Budget adherence: The customer's stated spending limit is respected.
  * Real-world accuracy: Every item, price, and fee shown is 100% verified against live store inventory, never hallucinated or estimated.
* **Safety First (Zero Surprise Orders)**: Order placement is strictly gated. The customer always sees the final bill and must explicitly confirm before an order is placed.
* **Plain-Language Transparency**: If an item is sold out, delivery is unavailable, or a store is closed, Grocer explains the situation in plain, friendly English with zero technical jargon.

---

## 5. Scope

### In Scope
* Natural-language grocery requests, single-item additions, multi-item lists, and meal ingredient deduction.
* Real-time dark-store catalog lookup, live inventory verification, and live cart management.
* Primary delivery address selection grounded strictly in real saved Swiggy addresses (`session.saved_addresses`).
* Customer Advocate Engine: automatic coupon hunting, free delivery threshold optimization, and total savings badge.
* Budget cap enforcement and itemized price breakdown in Indian Rupees (₹).
* Explicit dual confirmation controls via interactive WhatsApp buttons or verified natural language.
* Dynamic 1-tap mobile UPI payment links (`upi://pay`) for Google Pay / PhonePe / Paytm.
* Plain-English out-of-stock reporting and alternative suggestions.

### Out of Scope
* Dark-store warehouse operations, picker software, supplier tools, or merchant dashboards.
* Delivery fleet logistics, driver assignment, or live GPS bike tracking on maps.
* Prescription drugs, medical products, or pharmacy fulfillment.
* Unsolicited automatic ordering or autonomous payment deduction without explicit approval.
* Background replenishment reminders or automated subscription cron jobs.
* Generic open-ended chitchat unrelated to groceries and household shopping.

---

## 6. Customer Experience Principles & System Invariants

1. **Real Data Over Speed**: Never chase speed with hardcoded shortcuts, fake heuristics, or temporary caching. Every catalog search, price, stock check, address, and coupon MUST use real Swiggy MCP data.
2. **Zero Assumptions About Customer Purchases**: Never assume customers only buy milk, bread, or staples. Search the real Swiggy dark-store catalog for whatever item the user asks for.
3. **Zero Assumptions About Geography (The Sangvi Principle)**: Never assume customers live in famous hubs (BKC, Indiranagar, Powai). Match delivery locations strictly against the user's real saved Swiggy addresses (`session.saved_addresses`). If an address contains "Sangvi", use that real address. If multiple match, present 1-tap quick buttons. If zero addresses exist, ask the user to add one in Swiggy.
4. **Customer Advocate Engine (Champion the Wallet)**: Always auto-apply the best valid Swiggy coupon (`list_coupons`). Proactively suggest 1-2 small real staples to cross free-delivery thresholds if it saves net fees. Critical Guardrail: Never apply a coupon if the final grand total increases (e.g. dropping below free-delivery cutoff without adding a staple). Proudly show `Total Saved: ₹...` on receipts.
5. **Sensible Defaults on Vague Requests**: When a request is completely unqualified (e.g., "milk" or "bread"), pick the store's #1 standard staple (500ml toned milk / standard white bread) and provide a 1-tap "Change Items" button. Never substitute specific requests (e.g., "almond milk", "Amul Gold 1L", "gluten-free bread").
6. **1-Tap Mobile UPI Checkout**: Default to clickable `upi://pay` deep links formatted into WhatsApp interactive buttons so users can pay with 1 tap in GPay/PhonePe directly on the same phone.
7. **Zero Regex & Zero Keyword Dictionaries for Domain Logic**: Absolutely NO regex word-lists, hardcoded drug lists, symptom dictionaries (`bukhar`, `sirdard`), city arrays, or item name matchers anywhere in business logic. Product safety is governed strictly by Swiggy catalog metadata (`category == "Pharmacy"` / `"Prescription"`). OTC first-aid (Band-Aids, ORS, cotton) is allowed. Conversational symptom nuance is handled by Gemini without keyword interceptors. (Regex is permitted only for raw syntax format validation: phone numbers, UUIDs, stripping markdown fences).
8. **Python Muscle vs Gemini Brain**: Gemini handles fuzzy natural language, recipes, and user intent. Python deterministically enforces math, budget caps, cart SHA-256 fingerprints, and checkout gates. The LLM can never place an order or deduct money.
9. **Zero Silent Drops**: If an item is out of stock or restricted, never quietly omit it. Honestly explain the missing item and offer alternatives.
10. **High-Cohesion Architecture**: Code that changes together lives together. No duplicate modules, no obsolete adapters, no 30-file over-fragmentation, and no corrupted line-ending bloat (`\r\r\n`).
