# PRD.md — Grocer v1.0 Product Requirements Document

> **Product:** Grocer — Instamart on WhatsApp  
> **Status:** Agreed & Authoritative Product Requirements for v1.  
> **This is the v1 target, not current state.** What works today lives in `STATUS.md`.  
> **Target Audience:** Indian urban households & quick-commerce shoppers managing their entire Swiggy Instamart account on WhatsApp  
> **Product goal (2026-10-27):** Bring Swiggy Instamart to WhatsApp. Chat is the front door to everything the Instamart MCP allows. If Swiggy has a tool for it, a customer should be able to ask for it in plain language and get the real result.  
> **How to read this document:** the journeys in §3 are examples of what people can do. They are not a checklist and not extra features to build. Scope is the tool surface in `ARCHITECTURE.md` §4. Anything no Swiggy tool backs is not v1 scope.

---

## 1. Product Vision: Instamart on WhatsApp

Grocer brings the entire Swiggy Instamart quick-commerce service and account lifecycle directly into WhatsApp chat.

Grocer is not limited to pasting grocery lists. It is your personal Instamart concierge on WhatsApp:
- **Shop & Discover:** Send grocery lists in natural language (English, Hindi, Hinglish), ask what is in stock, find snacks, or say *"Reorder my usual groceries"*.
- **Full Address Management:** Ask *"What addresses do I have saved?"*, say *"Delete my old office address"*, or drop a WhatsApp location pin to add a new home.
- **Order History & Live GPS Tracking:** Ask *"Where is my order?"* for a live rider map, check past orders from the last 15 days, or view an itemized bill.
- **Champion the Wallet:** Automatically find and apply the best valid Swiggy coupon without ever increasing your final payable total.
- **Check Store Status & Availability:** Inquire about delivery fees, store operating hours, item stock, or available alternatives.

---

## 2. Universal Non-Negotiables & Invariants

1. **Live Swiggy Data, No Production Mocks:**
   - Every product search, stock count, price, address book entry, coupon, and payment link MUST come directly from live Swiggy Instamart MCP tools (`https://mcp.swiggy.com/im`).
   - Production code has no fake Swiggy, WhatsApp, database, or LLM branches. Contract tests may use recorded real Swiggy responses. Gate proof and behavior claims require live calls.

2. **Full Account & Address Lifecycle:**
   - **View Addresses:** Call `get_addresses` to surface saved places (paginated 10 per page) with labels (Home, Work, Other).
   - **Switch Address:** Set `selectedAddressId` to re-ground catalog search and cart availability with 1-tap list pickers.
   - **Add Address:** Use `create_address` and `recommend_address` to geocode WhatsApp GPS pins or free-text addresses, automatically parsing street, building, city, and postal code.
   - **Delete Address:** Call `delete_address` only after explicit customer confirmation (`[Confirm Delete: Address]`).

3. **Zero Assumptions & Radical Truth:**
   - Never assume what a customer wants. If the request is unclear, or the system is unsure, Grocer answers with read-only information or asks a question. It never changes the basket, an address, or money on a guess.
   - If an item is specific (*"The Health Factory zero maida brown bread"*), never substitute with white bread or another brand.
   - If an item is out of stock, if a dark store is closed, or if an API error occurs, communicate the exact truth in plain, human English. Never silently omit items from a basket. Show dropped items under a dedicated *"Not added (Out of stock)"* receipt section and suggest available alternatives from Swiggy's `similarProducts`.

4. **Customer Advocate Engine (Champion the Wallet):**
   - Automatically discover (`list_coupons`) and test the top 2 applicable coupons to keep turn latency under 4 seconds.
   - **Critical Guardrail:** Never apply a coupon if the final payable total increases (e.g. dropping below a free-delivery cutoff and triggering surge/delivery fees).
   - Display verified rupee savings clearly on every receipt card (*"🎉 You saved ₹X on this order!"*).

5. **Sensible Defaults on Vague Items & 1-Tap Reorders:**
   - When a request is completely unqualified (e.g. *"milk"*, *"bread"*, *"eggs"*), pick the active dark store's #1 standard staple (e.g. 500ml toned milk) and provide a 1-tap `[Change Items]` button.
   - When a customer asks to reorder (*"reorder my usuals"*, *"buy what I got last time"*), call `your_go_to_items` and `get_orders` to surface frequently ordered SKUs for 1-tap re-addition.
   - When a request involves high-variety snacks or drinks (*"chips"*, *"cold coffee"*), present 2–3 in-stock options conversationally rather than guessing a random flavor.

6. **The 3-Lock Checkout Safety Gate:**
   - The LLM interprets natural language and evaluates candidates. It never calls Swiggy itself. Python deterministically enforces math, budget caps, cart SHA-256 fingerprints, safety classes, and checkout gates.
   - **Lock 1 (Authority):** An order can ONLY be placed if the customer physically taps a WhatsApp button (`pay:<approval_id>:<option>`). Typing text ("yes", "confirm", "proceed") is strictly rejected from spending money.
   - **Lock 2 (Truth):** Live cart re-verification confirms 100% stock, zero unserviceable items, and exact integer paise math matching the approved receipt before checkout.
   - **Lock 3 (Exactly-Once):** Atomic PostgreSQL CAS prevents double-debiting on mobile retries or double taps.

7. **1-Tap Mobile Payment via Swiggy HTTPS `bridgeUrl`:**
   - Swiggy's `checkout` tool returns an authoritative HTTPS `bridgeUrl` in `data.bridgeUrl`.
   - UPI is the first payment path. The code must read `get_payment_options` and pass the chosen `intentApp` (mobile app) or `generateUPIQR=true` (desktop QR) to `checkout`. Cash on Delivery is the second path. SwiggyPay is later, only when the live response supports it.
   - `checkout` is not idempotent. On a 5xx or network failure, call `get_orders` and compare against the pre-checkout order snapshot before retrying. Never blind-retry.
   - Meta WhatsApp CTA buttons only support `https://`. Checkout delivers this link as a `[Pay ₹X (UPI / Card)]` button, rendering Swiggy's secure web payment screen where the customer taps to open GPay, PhonePe, Paytm, or scans a QR code.

8. **Live GPS Rider Tracking & Order History:**
   - `get_orders` surfaces order history from the last 15 days, with `activeOnly=true` for ongoing deliveries.
   - For in-flight deliveries, `track_order` delivers real-time rider name, ETA, and live GPS map tracking links.
   - Notifications are sent at 3 discrete milestones: Confirmed & Packing, Out for Delivery with Live Map, and Delivered.

9. **Swiggy MCP Real-World Boundaries:**
   - **Order Cancellation:** Swiggy MCP does not support automated order cancellation. When a customer asks to cancel, Grocer instructs: *"To cancel your Instamart order, please call Swiggy customer care directly at 080-67466729."*
   - **Multi-Store Orders:** Swiggy dark stores can split orders if items come from different facilities. Grocer communicates split orders and tracking separately.
   - **Token Renewal:** When the Swiggy access token expires, Grocer refreshes it silently with the stored refresh token and retries once. Only if the refresh fails does it park the active shopping list, present a 1-tap `[Connect Swiggy]` button, and execute the list after login.

10. **DPDP Compliance & 24-Hour Data Minimization:**
    - Personal customer delivery addresses and basket snapshots are permanently deleted from database storage 24 hours post-order. Minimal transaction audit metadata (transaction ID, paise total, timestamp) is retained for 90 days.
    - An explicit inbound message `"delete my data"` instantly purges all customer records and revokes active Swiggy OAuth tokens.

---

## 3. Example Journeys (illustrations, not requirements)

These show the kind of thing a person can ask for. They are not a build checklist. The bar is: every tool in `ARCHITECTURE.md` §4 is reachable by chat, and anything without a tool gets an honest answer instead of an invented one.

### Journey 1: Full Address & Account Management
- **Customer:** *"What addresses do I have saved on Swiggy?"*  
  **Grocer:** Calls `get_addresses` and lists saved locations (Home, Work, Mom's Place) with the active address highlighted.
- **Customer:** *"Delete my Work address."*  
  **Grocer:** Presents an interactive button: `[Confirm Delete: Work]`. When tapped, calls `delete_address` and confirms deletion.
- **Customer:** Shares a WhatsApp GPS location pin or texts *"Add address: 402 Palm Grove, Bandra West, Mumbai 400050"*.  
  **Grocer:** Geocodes via `recommend_address`, parses lines through the LLM adapter, calls `create_address`, and saves it directly to the customer's Swiggy profile.

### Journey 2: Everyday Shopping & 1-Tap Reorders
- **Customer:** *"Reorder what I bought last time"* or *"Get 1L toned milk, brown bread, and 6 eggs"*.  
  **Grocer:** Calls `your_go_to_items` or `search_products`, matches variants, builds the full cart via `update_cart`, tests coupons, and outputs a clean WhatsApp receipt with exact paise math and a `[Pay ₹X via UPI]` button.

### Journey 3: Conversational Inquiries (No Forced Checkout)
- **Customer:** *"Wait, do you have sourdough bread in stock?"* or *"What is the delivery fee right now?"*.  
  **Grocer:** Answers the inquiry naturally using live dark store data without pushing an unwanted cart receipt or checkout button.

### Journey 4: Out-of-Stock Transparency
- **Customer:** Requests an item that is currently sold out.  
  **Grocer:** Assembles all available items into the cart and highlights the missing product under a prominent warning:  
  *⚠️ Not added (Out of stock at Bandra store): Amul Salted Butter 100g. Available alternative: Mother Dairy Table Butter 100g.*

### Journey 5: Safe 1-Tap Payment & Milestone Tracking
- **Customer:** Taps `[Pay ₹240 via UPI]`.  
- **Grocer:** Runs the 3-Lock gate and delivers Swiggy's secure `bridgeUrl`.  
- **Post-Payment:** A persistent background poller monitors `check_payment_status` (~19s intervals, up to 5 min) and sends 3 milestone updates:  
  1. *Order confirmed & dark store packing*  
  2. *Rider picked up & out for delivery (with live GPS map link)*  
  3. *Order delivered*

### Journey 6: One-Time Destination Orders ("Send to Mom")
- **Customer:** *"Send 2L milk and brown bread to Mom's house in Delhi."*  
- **Grocer:** Selects the Delhi address, queries Delhi dark store stock, and outputs: `📍 Delivering to: Mom's House (Delhi)`. Once completed, automatically retains the customer's primary Bangalore address as active for subsequent turns.

### Journey 7: Conversational Recipe Proposals ("Aglio Olio")

**Example only, not a v1 requirement.** No Instamart tool backs recipes. Grocer can answer a cooking question in chat, but only tool-backed actions are in scope.

- **Customer:** *"I want to make Aglio Olio pasta for 2 people tonight."*  
- **Grocer:** Proposes the recipe checklist conversationally (*"For Aglio Olio (2): Spaghetti 500g, Olive Oil 250ml, Garlic 100g, Parmesan 100g. Assuming you have salt & chili flakes!"*) and presents buttons: `[Add All 4 Items]` and `[Let Me Pick]`.

### Journey 8: Post-Order Modification Honesty & 1-Tap Add-On
- **Customer:** (2 mins post-payment) *"Wait, I forgot eggs! Can you add 6 eggs to my order?"*  
- **Grocer:** Explains: *"Your order #IM-123 is already being packed at the dark store and can't be changed. Would you like me to start a quick separate order for 6 eggs (₹55) to the same address?"* with buttons: `[Order Eggs Now]` and `[Never Mind]`.

### Journey 9: Small-Cart Fee Shock Protection
- **Customer:** *"Get 1 packet of Maggi (₹14)."*  
- **Grocer:** Warns: *"⚠️ Heads up: Your item is ₹14, but Swiggy delivery and small-cart fees add ₹60 (Total: ₹74). If you add ₹135 more in groceries, delivery becomes FREE. Would you like to add some daily essentials or proceed anyway?"* with buttons: `[Add Essentials]` and `[Proceed for ₹74]`.

---

## 4. Release Gates & Success Metrics

These are v1 acceptance bars, not current results. Current results live in `STATUS.md`. No live order is placed during the build. Checkout is proven with simulated failures and recorded responses; the first real order is Karan's own test after handoff.

1. **Staging Contract Gate:** 100% of commerce parsers validated against real Swiggy staging fixtures across all 20 Instamart MCP tools. The tool list is in `ARCHITECTURE.md` §4.
2. **Deterministic Safety Gate:** 0 duplicate orders and 0 unapproved checkouts across 500 simulated stress turns. Text "yes" never places an order.
3. **Turn Latency Gate:** Average reply latency under 3.5 seconds. Coupon trials capped at 2 to preserve speed.
4. **Wallet Advocacy Gate:** Verified 100% coupon accuracy with 0 cases of a coupon increasing the net total.
5. **Account Operations Accuracy:** Address creation, listing, switching, and deletion work with 100% reliability against Swiggy MCP.

---

## 5. V1 Delivery Constraints

These are fixed for this build. They override any conflicting assumption elsewhere.

1. **One Supabase project until launch.** The app uses the `grocer` schema in the `postgres` database. Tests use a separate `grocer_test` database in the same project and never write the real database.
2. **Groq is the development and test LLM.** Use `openai/gpt-oss-120b`. Gemini is optional, and its free quota is not a dependency.
3. **Swiggy OAuth redirect is allowlisted.** `https://grocerr.vercel.app/` is the exact redirect URI. The backend calls `https://mcp.swiggy.com/im` with the customer token.
4. **Real-order capable, live order locked.** `LIVE_CHECKOUT_ENABLED=false` by default. No live order during the build. Karan tests on WhatsApp and places the first real order himself after handoff.
5. **₹1,000 default cap.** Keep it unless Karan changes it.
6. **Landing page number.** The website displays the placeholder `+91 98765 43210`. The real WhatsApp link comes only from `NEXT_PUBLIC_WHATSAPP_NUMBER`. Karan's real number is never committed or published.
7. **Full tool coverage is the product bar.** Every one of the 20 Instamart MCP tools is reachable by chat or gets an honest "not supported" reply. The §3 journeys are examples, not scope.
8. **Address writes are testable.** One throwaway address on Karan's account may be created and deleted during testing. No other customer data is touched.
9. **No paid hosting.** Render stays on the free plan. Pollers reconcile from the database when the service wakes; no always-on instance.
10. **No phone-entry form on the landing page.** OAuth is a bot-sent bridge only. The page never asks a visitor for a phone number.
