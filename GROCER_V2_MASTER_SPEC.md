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
7. **One-Tap Payment**: Delivers an official Swiggy dynamic UPI payment link or QR code directly into the chat for instant payment.

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
* Primary delivery address selection and easy switching between saved addresses.
* Budget cap enforcement and itemized price breakdown in Indian Rupees (₹).
* Explicit confirmation controls via interactive WhatsApp buttons.
* Dynamic UPI payment link and QR generation for order settlement.
* Plain-English out-of-stock reporting and alternative suggestions.

### Out of Scope
* Dark-store warehouse operations, picker software, supplier tools, or merchant dashboards.
* Delivery fleet logistics, driver assignment, or live GPS bike tracking on maps.
* Prescription drugs, medical products, or pharmacy fulfillment.
* Unsolicited automatic ordering or autonomous payment deduction without explicit approval.
* Background replenishment reminders or automated subscription cron jobs.
* Generic open-ended chitchat unrelated to groceries and household shopping.

---

## 6. Customer Experience Principles

* **Smart Defaults Over Interrogation**: When a customer asks for milk, pick the standard popular in-stock option and show it on the receipt. Never ask 5 questions when 1 sensible default solves the customer's need.
* **Immediate Out-of-Stock Honesty**: If an item cannot be found or is out of stock, add the remaining items, report the missing item clearly, and give the customer the choice to swap or proceed.
* **Everything in Rupees**: Every price shown reflects the exact live store price including applicable taxes and delivery charges. No hidden surprises at checkout.
* **You Stay in Control**: The cart is always reviewable, editable, and clearable. The final step is always a clear **Confirm & Pay** prompt.
