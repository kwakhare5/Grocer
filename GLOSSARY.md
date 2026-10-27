# Grocer Domain Model

Grocer brings Swiggy Instamart's full quick-commerce catalogue, account management, and ordering directly to WhatsApp chat.

## Core Concepts

**Customer**:
An end user interacting with Grocer over WhatsApp using their linked Swiggy account.
_Avoid_: User, buyer, client

**Dark Store**:
A hyper-local Swiggy fulfillment warehouse stocking groceries for 10–15 minute delivery within a specific geofence.
_Avoid_: Warehouse, shop, supermarket, hub

**Tool Coverage**:
The product bar for v1: every one of the 20 Instamart MCP tools is reachable by chat or gets an honest "not supported" reply. The journeys in `PRD.md` §3 are examples of what people can do, not scope.
_Avoid_: Feature list, roadmap, journey checklist

**Active Address**:
The customer's currently selected Swiggy delivery location that anchors catalog search, stock availability, and dark store assignment.
_Current_: if the session has no active address, the webhook grounds to the first saved address, not Swiggy's `defaultAddressId`.
_Avoid_: Default address, current location, shipping address

**Basket**:
The transient, unconfirmed list of grocery items the customer is currently assembling locally or in Swiggy's cart API. Swiggy calls it a cart; Grocer's customer-facing word is basket.
_Avoid_: Cart, bag, order list

**Product Variation (`spinId`)**:
The specific pack size, weight, or unit variant of a grocery product that maps directly to Swiggy's orderable SKU.
_Avoid_: Item, SKU, product ID

**Approval Latch (3-Lock Gate)**:
The deterministic Python security barrier ensuring an order is verified for authority (physical button tap), truth (live stock and paise math), and idempotency before checkout.
_Current_: the CAS and the external Swiggy checkout share a rollback-able transaction, so exactly-once is not proven. See `STATUS.md` P0 #1.
_Avoid_: Payment gate, order validation, checkout lock

**Bridge URL**:
An authoritative Swiggy HTTPS web payment link rendered in a WhatsApp CTA URL button where the customer completes mobile UPI or card payment.
_Avoid_: Deep link, UPI intent, payment gateway

**Split Order**:
An order that Swiggy automatically splits into multiple fulfillments when items originate from separate dark stores or partner nodes.
_Current_: the pollers look up only the first `swiggy_order_id`, so orders 2..n are not notified.
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
_Status_: target; not implemented.
_Avoid_: Guest delivery, remote order, secondary address checkout

**Recipe Checklist**:
A conversational proposal listing required dish ingredients before adding to basket, distinguishing fresh items from assumed pantry staples.
_Status_: target; the current recipe buttons are no longer emitted and the flow is not wired.
_Avoid_: Meal kit, recipe bundle, auto-add recipe

**Small-Cart Fee Threshold**:
The point where Swiggy delivery, handling, and surge fees exceed 35% of item value, triggering a proactive alert to add essentials and unlock free delivery.
_Status_: target; the helper exists but has no caller.
_Avoid_: Delivery fee penalty, minimum order surge, surge warning

**JIT Re-Auth Latch**:
The state-recovery mechanism for an expired Swiggy session. Grocer stores an access token plus a 30-day refresh token. On expiry or 401 it refreshes silently and retries once. It parks only if the refresh fails, then asks the customer to reconnect. Current replay is not wired end to end.
_Avoid_: Session refresher, token relink, auth interceptor

**Cold-Start Onboarding**:
The initial welcoming flow for a new user with zero saved Swiggy addresses, prompting for a WhatsApp GPS pin or address before browsing groceries.
_Avoid_: Sign-up flow, registration, account creation

**Ingestion Shield**:
The front-door validation and fast-dispatch gateway that verifies Meta HMAC-SHA256 signatures and drops duplicate webhooks. Target: HTTP 200 within 25ms. Current: the webhook is synchronous and waits for the turn.
_Avoid_: Webhook listener, incoming router, message receiver

**Per-Customer Advisory Lock**:
The non-blocking PostgreSQL transaction latch (`pg_try_advisory_xact_lock`) guarding a customer's active session to ensure rapid double-taps are serialized or dropped safely.
_Avoid_: Mutex, thread lock, queue barrier

**Stale Message Latch**:
The ingestion gate that silently drops any inbound WhatsApp webhook timestamped more than 15 minutes in the past.
_Avoid_: Message timeout, expired packet, drop filter

**Fast Button Dispatcher**:
The deterministic Python routing engine that executes interactive WhatsApp button actions (checkout, address selection, basket clearing) without the conversational LLM. Target: under 50ms. Current: the pay path still calls Swiggy.
_Avoid_: Fast path, button handler, direct action


**Capability**:
A single thing Grocer can do for a customer, named after the customer's goal (check price, list addresses, track order, add to basket). One capability may use several Swiggy tools.
_Avoid_: Intent, command, feature

**Safety Class**:
The permission level attached to every capability. Read never writes; Basket changes only the basket; Account changes only saved account data; Money spends money.
_Avoid_: Risk level, permission type, access mode

**Routing Decision**:
The LLM's structured answer for one customer message: the capability, the extracted details (item, address, order), and a confidence score. Python validates it before anything runs.
_Avoid_: Intent, classification, prediction

**Safe Path**:
What Grocer does when the capability is unknown or confidence is low: read-only options when there is something concrete to show, otherwise a clarifying question. It never writes.
_Avoid_: Fallback, default action, catch-all

**LLM Adapter**:
The single module allowed to call a model: `backend/agent/llm.py`. It returns one JSON object, validates that the answer is an object, retries once on a transient failure, and reports the provider. Groq `openai/gpt-oss-120b` is primary; Gemini is optional. Routing and candidate evaluation both use it. No provider SDK is imported anywhere else.
_Avoid_: Intent router, LLM pipeline, chat classifier, conversational orchestrator

**Extracted Item**:
A structured target grocery item parsed by the LLM from natural customer messages before catalog grounding.
_Avoid_: Search term, query token, raw item

**Test Database**:
The separate `grocer_test` database in the one pre-launch Supabase project. It has the same `grocer` schema, but no customer data. DB tests use it and never write the real database.
_Avoid_: Second Supabase, shared test schema, dev database

**Live Checkout Lock**:
The `LIVE_CHECKOUT_ENABLED=false` guard, enforced in `execute_3_lock_checkout` before any Swiggy call. The build stays real-order capable, but no order is placed during the build. Karan places the first real order after handoff.
_Avoid_: Disabled checkout, dry run, sandbox order

**Landing Page**:
The website at grocerr.vercel.app. It advertises the product and sends people to WhatsApp. It is not the product UI and holds no customer data.
_Avoid_: Dashboard, web app, frontend product
