# PRD.md — Grocer Master Product Requirements Document

> **Status:** Official Master Product Requirements Document (Single Source of Truth)  
> **Version:** 2.0  
> **Target:** Complete Swiggy Instamart Concierge on WhatsApp  

---

## 1. What Grocer Is About

Grocer is a complete Swiggy Instamart concierge on WhatsApp. 

Instead of opening a mobile app, searching for items one by one, scrolling through endless product grids, and manually assembling a cart, the customer simply messages what they need naturally on WhatsApp. Grocer turns ordinary conversational shopping requests into real, verified grocery carts in the customer's local dark store.

Grocer is not a generic chitchat bot or an experimental recipe generator. It is a direct, full-powered conversational shopping concierge built to make on-demand grocery ordering, 1-tap reordering, address management, and live order tracking effortless, fast, and reliable.

---

## 2. Target User & Core Problem

### Whom It Is For
* **Busy Urban Consumers**: Working professionals, parents, and students who already spend their day on WhatsApp and want groceries without the friction of opening, searching, and tapping through an app.
* **Friction-Sensitive Shoppers**: Anyone tired of scrolling through 40 varieties of bread or dealing with confusing search results just to buy daily essentials.
* **Budget-Conscious Households**: Shoppers who want to set a spending limit (e.g., *"under ₹500"*) and be guaranteed that their basket stays within that limit.
* **Natural Planners**: Customers who think in dishes, cravings, or multi-item lists (*"party snacks for 4"*, *"milk, bread, and butter"*) rather than category catalogs.

### The Problem It Solves
Grocery shopping apps force users through high cognitive friction: search pagination, variant selection traps, unnotified item out-of-stock drops, missed coupon applications, and slow manual checkouts. Grocer automates all of this through a single WhatsApp chat turn.

---

## 3. What Grocer Does

1. **Conversational Grocery Intake**: Understands plain-English shopping lists, meal recipes, single staples, or cravings without requiring rigid commands or special formatting. Understands Hinglish grocery terms (*doodh, dahi, atta, aloo*) and voice notes/grocery photos, always responding in clean, natural English.
2. **Real Dark-Store Sourcing**: Finds real products and verifies live stock availability at the customer's local Swiggy Instamart store.
3. **Smart Brand & Variant Selection**: Picks standard, popular in-stock items automatically (e.g., standard 500ml toned milk or white bread) instead of interrogating the customer with brand surveys.
4. **Transparent Basket Summaries**: Delivers a clear, itemized receipt directly in WhatsApp showing product names, pack sizes, individual prices in Indian Rupees (₹), taxes, packaging fees, delivery fees, and the grand total.
5. **Customer-Controlled Adjustments**: Allows customers to easily modify items, adjust quantities, or swap brands with a simple text reply or a 1-tap "Change Items" button before anything is finalized.
6. **Server-Gated Order Confirmation**: Guarantees that no order is ever placed and no payment is ever initiated until the customer explicitly inspects the bill and taps "Confirm Order" (backed by the cryptographic 3-lock checkout latch).
7. **One-Tap Payment**: Delivers an official Swiggy dynamic UPI payment link (`upi://pay`) directly into the chat for seamless 1-tap mobile payment in GPay/PhonePe/Paytm, with cash on delivery where supported.
8. **Customer Advocate Savings**: Automatically hunts and applies the best Swiggy coupons, suggests staples to beat delivery fee thresholds, and displays total rupees saved with celebration badges. Guardrail: never applies a coupon if the final grand total increases.
9. **Full Swiggy Concierge Features**: Supports 1-tap reordering from past purchase history (`get_orders`), live delivery tracking with rider ETA in chat (`track_order`), and in-chat address creation via text or WhatsApp location pin (`create_address`).

---

## 4. Universal Non-Negotiables & System Invariants

1. **Real Data Over Speed**: Never chase speed with hardcoded shortcuts, fake heuristics, or temporary caching. Every catalog search, price, stock check, address, and coupon MUST use live Swiggy MCP data.
2. **Zero Assumptions About Customer Purchases**: Never assume customers only buy milk, bread, or staples. Search the real Swiggy dark-store catalog for whatever item the user asks for (produce, snacks, dairy, personal care, OTC first-aid).
3. **Zero Assumptions About Geography (Real Address Grounding & In-Chat Creation)**: Never assume customer geography or hardcode specific area names. Delivery is strictly grounded in the customer's real Swiggy address book. If multiple match, present 1-tap quick buttons or list menus. If zero addresses exist or the user wants a new location, let them add and save it directly in chat via text or a WhatsApp GPS pin (`create_address`).
4. **Customer Advocate Engine (Champion the Wallet)**: Always auto-apply the best valid Swiggy coupon (`list_coupons`). Proactively suggest 1-2 small real staples to cross free-delivery thresholds if it saves net fees. Critical Guardrail: Never apply a coupon if the final grand total increases. Proudly show `Total Saved: ₹...` on receipts.
5. **Sensible Defaults on Vague Requests**: When a request is completely unqualified (e.g., "milk" or "bread"), pick the store's #1 standard staple (500ml toned milk / standard white bread) and provide a 1-tap "Change Items" button. Never substitute specific requests (e.g., "almond milk", "Amul Gold 1L", "gluten-free bread").
6. **1-Tap Mobile UPI Checkout**: Default to clickable `upi://pay` deep links formatted into WhatsApp interactive buttons so users can pay with 1 tap in GPay/PhonePe directly on the same phone, with secondary COD button where supported.
7. **Zero Regex & Zero Keyword Dictionaries for Domain Logic**: Absolutely NO regex word-lists, hardcoded drug lists, symptom dictionaries (`bukhar`, `sirdard`), city arrays, or item name matchers anywhere in business logic. Product safety is governed strictly by Swiggy catalog metadata (`category == "Pharmacy"` / `"Prescription"`). OTC first-aid (Band-Aids, ORS, cotton) is allowed. Conversational symptom nuance is handled by Gemini without keyword interceptors.
8. **Python Muscle vs Gemini Brain**: Gemini handles fuzzy natural language, recipes, and user intent. Python deterministically enforces math, budget caps, cart SHA-256 fingerprints, and checkout gates. The LLM can never place an order or deduct money.
9. **Zero Silent Drops & Radical Truth**: If an item is out of stock or restricted, never quietly omit it. Honestly explain the missing item and offer alternatives. If an error occurs, communicate the exact truth in plain English (e.g., *"Dark store is closed"*, *"Swiggy system is temporarily down"*).
10. **High-Cohesion Architecture**: Code that changes together lives together. No duplicate modules, no obsolete adapters, no 30-file over-fragmentation, and no corrupted line-ending bloat (`\r\r\n`).

---

## 5. Scope Boundaries

### In Scope
* Natural-language grocery requests, single-item additions, multi-item lists, and meal ingredient deduction.
* Real-time dark-store catalog lookup, live inventory verification, and live cart management.
* Full Swiggy address management: selecting saved addresses, in-chat address creation via text or WhatsApp location pin (`create_address`), and address deletion (`delete_address`).
* Past order lookup and 1-tap reordering (`get_orders`, `get_order_details`, `get_go_to_items`).
* Live order tracking and delivery status with rider ETA in chat (`track_order`, `get_delivery_status`).
* Customer Advocate Engine: automatic coupon hunting, free delivery threshold optimization, and total savings badge.
* Budget cap enforcement and itemized price breakdown in Indian Rupees (₹).
* Explicit dual confirmation controls via interactive WhatsApp buttons (`confirm_order:<fingerprint>`) or verified natural language.
* Dynamic 1-tap mobile UPI payment links (`upi://pay`) for Google Pay / PhonePe / Paytm, and Cash on Delivery where supported.
* Plain-English out-of-stock reporting and alternative suggestions.
* Direct issue reporting (`report_error`) and Swiggy customer care contact sharing (`080-67466729`).

### Out of Scope
* Dark-store warehouse operations, picker software, supplier tools, or merchant dashboards.
* Custom fleet logistics or custom driver dispatch systems (we rely strictly on Swiggy's dark-store fleet).
* Prescription drugs, Schedule H/X medical products, or prescription advice.
* Unsolicited automatic ordering or autonomous payment deduction without explicit approval.
* Background replenishment reminders or automated subscription cron jobs (ADR 0001).
* Generic open-ended chitchat unrelated to groceries and household shopping.

---

## 6. Success Metrics & Verification Gate

* **User Journey Proof**: A customer can send a raw grocery list, receive a verified receipt with best coupon applied, tap "Confirm Order", and receive a clickable `upi://pay` link.
* **Verification Proof**: All unit, integration, and E2E tests run cleanly under `.\verify.ps1`, exiting 0 with zero failures and zero skipped tests.
