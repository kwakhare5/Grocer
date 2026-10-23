# Grocer Domain Model

Grocer brings Swiggy Instamart's full quick-commerce catalogue, account management, and ordering directly to WhatsApp chat.

## Core Concepts

**Customer**:
An end user interacting with Grocer over WhatsApp using their linked Swiggy account.
_Avoid_: User, buyer, client

**Dark Store**:
A hyper-local Swiggy fulfillment warehouse stocking groceries for 10–15 minute delivery within a specific geofence.
_Avoid_: Warehouse, shop, supermarket, hub

**Active Address**:
The customer's currently selected Swiggy delivery location that anchors catalog search, stock availability, and dark store assignment.
_Avoid_: Default address, current location, shipping address

**Basket**:
The transient, unconfirmed list of grocery items the customer is currently assembling locally or in Swiggy's cart API.
_Avoid_: Cart, bag, order list

**Product Variation (`spinId`)**:
The specific pack size, weight, or unit variant of a grocery product that maps directly to Swiggy's orderable SKU.
_Avoid_: Item, SKU, product ID

**Approval Latch (3-Lock Gate)**:
The deterministic Python security barrier ensuring an order is verified for authority (physical button tap), truth (live stock and paise math), and idempotency before checkout.
_Avoid_: Payment gate, order validation, checkout lock

**Bridge URL**:
An authoritative Swiggy HTTPS web payment link rendered in a WhatsApp CTA URL button where the customer completes mobile UPI or card payment.
_Avoid_: Deep link, UPI intent, payment gateway

**Split Order**:
An order that Swiggy automatically splits into multiple fulfillments when items originate from separate dark stores or partner nodes.
_Avoid_: Multi-order, partial order, batch order

**Customer Care Escalation**:
The protocol directing a customer to call Swiggy Customer Care (080-67466729) with their Order ID for operations not supported by MCP, such as order cancellation.
_Avoid_: Support ticket, bot cancellation

**Go-To Items**:
Frequently or recently ordered grocery items fetched for a customer's active address that can be reordered in 1 tap.
_Avoid_: Favorites, frequent items, recurring orders

**Location Pin Onboarding**:
The two-step flow capturing geographic coordinates from a WhatsApp location pin and pairing them with user-provided flat/building details to form a complete Swiggy delivery address.
_Avoid_: GPS tracking, location sharing, address autofill

**One-Time Destination Order**:
An order intentionally routed to a specific alternative address (e.g., family or work) that fulfills without altering the customer's primary home default.
_Avoid_: Guest delivery, remote order, secondary address checkout

**Recipe Checklist**:
A conversational proposal listing required dish ingredients before adding to basket, distinguishing fresh items from assumed pantry staples.
_Avoid_: Meal kit, recipe bundle, auto-add recipe

**Small-Cart Fee Threshold**:
The point where Swiggy delivery, handling, and surge fees exceed 35% of item value, triggering a proactive alert to add essentials and unlock free delivery.
_Avoid_: Delivery fee penalty, minimum order surge, surge warning

**JIT Re-Auth Latch**:
The state-recovery mechanism that parks an active basket or checkout when a 5-day Swiggy OAuth token expires mid-flight and resumes execution instantly upon re-authentication.
_Avoid_: Session refresher, token relink, auth interceptor

**Cold-Start Onboarding**:
The initial welcoming flow for a new user with zero saved Swiggy addresses, prompting for a WhatsApp GPS pin or address before browsing groceries.
_Avoid_: Sign-up flow, registration, account creation
