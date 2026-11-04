# DESIGN.md — Grocer UI Specification

> **Two surfaces, two jobs.**
>
> - **Part A — WhatsApp:** the product UI. This is the only place a customer shops, taps, pays, tracks and talks.
> - **Part B — Website:** the advertisement and landing page. It explains the project, shows what is real, and sends people to WhatsApp. It is not a dashboard and not a second shopping UI.
>
> **Current vs target:** this document describes the target experience and marks the current gaps. `STATUS.md` is the only current truth.

---

# Part A — WhatsApp Product UI

## A1. Surface and hard limits

- Platform: WhatsApp Business Cloud API on Android and iOS.
- Maximum 3 quick-reply buttons per interactive message.
- Maximum 10 rows in a list picker.
- Maximum 1024 characters in an interactive body.
- Plain text, bold and monospace only. No HTML, tables or rich cards.
- Replies are in English. Grocer understands Hindi and Hinglish grocery words but writes back in English. Decided 2026-10-27.

## A2. Receipt card

Target template:

```
📍 *Delivering to:* Home (Bandra West)
-----------------------------------
🛒 *Your Basket (4 items)*
• Borges Penne Pasta (500g) x1 — ₹140
• Barilla Tomato Basilico (400g) x1 — ₹155
• D'lecta Grated Parmesan (100g) x1 — ₹220
• Fresh Button Mushrooms (200g) x1 — ₹65
-----------------------------------
*Item Total:* ₹580
*Coupon (INSTA50):* -₹50
*Delivery Fee:* FREE
*Handling & Taxes:* ₹25
-----------------------------------
*To Pay:* *₹555*
🎉 *You saved ₹50 on this order!*
```

Rules for every add receipt:

1. Show what was just added, not only the whole basket.
2. If the basket already had items, show the old total and the new total, and offer `[Keep only new]` (clears the old basket after a tap, keeps this turn) plus a clear action. Never call the old basket "added".
3. Name any Swiggy stock cap that changed the request ("Swiggy allows 2 of this item per order").
4. Never say "Basket updated" unless the verified cart matches the request.

Live since 2026-10-27: an add receipt shows only the change plus a delta line ("You already had N items (₹X). Basket now: M items."), and any Swiggy stock cap is printed with the capped quantity. A fresh-basket add still prints the whole basket.

Live since 2026-10-28: the receipt names the coupon and its rupee saving, coupons run on every cart write, and a receipt over the 1024-character button limit is sent whole as text with Pay/Clear in a short follow-up (`send_receipt`, `backend/channels/button_router.py`). The interactive body limit still truncates non-receipt bodies, which are short by design.

## A3. Out-of-stock and unserviceable items

Never drop an item silently. Put it under a warning section with alternatives:

```
⚠️ *Not added (Out of stock at Bandra store):*
• Amul Salted Butter (100g)
(Available alternative: Mother Dairy Table Butter 100g)
```

If Swiggy does not provide an alternative, say so. Do not invent one.

## A4. Button layouts

### A4.1 Checkout receipt

Live since 2026-10-27: the add receipt sends up to three quick replies, `[Pay ₹X]`, `[Keep only new]` (only when the basket already had items) and either `[Change item]` (one vague item) or `[Clear basket]`. After the pay tap, the bot sends a CTA URL button, `[Pay on Swiggy]`, using the HTTPS `bridgeUrl`.

Target: one CTA URL button `[Pay ₹X (UPI / Card)]`, plus up to two secondary actions:
1. `[Cash on Delivery]` when Swiggy offers it (parked for v1; UPI only).
2. `[Change Address]` or `[Change Items]`.

A CTA URL button opens Swiggy's payment page. A quick reply only sends a button ID back to Grocer. Do not mix them up.

### A4.2 Clear basket

Preview first, then two buttons, `[Clear basket]` (`cart:clear`) and `[Keep basket]` (`cart:keep`). Never clear on a text guess. A clear is permanent by decision 2026-10-27: no undo. The confirm copy must say that plainly.

### A4.3 Address switch and delete

- Switch: show the saved addresses, then confirm. Live since 2026-10-27: a short numbered card keeps the first and last segments of each address and offers up to 3 `[Use: <Label>]` buttons. The switch warns, clears and rebuilds the basket at the new store and names anything it could not move. A 10-row list picker is still the target for more than 3 addresses.
- Delete: `[Yes, delete]` and `[Cancel]`. The guard refuses deletion when an active delivery uses that address, and it runs again on the final tap.

### A4.4 Token expiry

Target copy:

> Your Swiggy login needs a security refresh. Tap below to reconnect. Your grocery list is saved and will resume automatically.

Button: `[Reconnect Swiggy]` (CTA URL to the allowlisted OAuth redirect).

Current: the webhook parks as `awaiting_link`, the callback stores the token and replays the saved message in the background. A failed replay restores the row instead of losing the list.

### A4.5 Recipe plan

A recipe request is a proposal, never a write.

1. Show the dish, the people count, and each ingredient with a pack count.
2. Say what it assumes the kitchen already has (salt, oil, spices).
3. Wait for `[Add all]` or `[Let me pick]`.
4. Respect Swiggy's `maxQuantity` and say when a cap changed the plan.

No plan is added from text alone. A customer who writes "make pizza for 5" must never get one surprise SKU in the basket.

Live in code since 2026-10-28: the model names the dish, people count and each ingredient's amount and unit (no hardcoded recipe list); Python searches the live store, turns amounts into whole packs from the store's pack size, prices each line and caps at `maxQuantity`. `[Add all]` re-checks stock and writes all ingredients or none. `[Let me pick]` accepts the item numbers as a tap or a typed reply ("1 and 3"); picks add the chosen in-stock rows and name the rest. The priced plan is stored server-side for 30 minutes, so the numbers always refer to the card the customer just saw.

### A4.6 Basket view

`What's in my basket?` always answers with the live cart, item count and total. There is no need to add something first. Live since 2026-10-27: the `view_basket` capability reads `get_cart` and never writes.

### A4.7 Presence and interim updates

- Every accepted inbound message is marked read (blue ticks) with a 25-second typing indicator, sent off the critical path. A send failure is logged and never blocks the reply.
- The typing indicator covers the first model and search call. It is not a promise of a live agent.
- Never send a fake "I'm still working" message. If work runs longer than the indicator, send the real result or the real failure.
- Reaction: at most one emoji per inbound message, chosen in code from the outcome, never by the model. 🏠 addresses, 🛒 basket, 📦 orders, 🛵 tracking, 🎟️ coupons, 💳 payments, 🍳 a recipe plan, ❓ when the bot needs a pick, 📍 when it asks for a pin. No reaction on chat, misses, lock refusals, auth or outages. Sent after the reply, fire-and-forget.
- Cards get at most one header emoji. Failure copy and money warnings get none. No emoji chains, no decorative emoji.

## A5. Tone and copy

- Friendly, direct, Indian neighborhood grocer. Not corporate, not academic.
- Never show internal variable names, HTTP codes, provider names or stack traces.
- Explain the customer outcome, not the mechanism.
- Bad: "ProviderAuthError: token expired at 1729837200"
- Good: "Your Swiggy login needs a quick refresh. Tap below to reconnect."
- Bad: "Cap exceeded"
- Good: "This order is above the ₹1,000 safety limit. Tap 'Raise Limit' if you want to continue."

## A6. Payment

- UPI is the first path. The customer taps the CTA, pays on Swiggy's HTTPS page, and Grocer polls `check_payment_status`.
- `checkout` is not idempotent. On a 5xx or network failure, check `get_orders` before retrying. Never blind-retry.
- UPI sends `generateUPIQR=true`, or `intentApp` when one is supplied. Fixed in Phase 3.
- UPI is the only path this build can place. COD and SwiggyPay are parked; the payment answer says they cannot be used yet.
- The ₹1,000 cap is a safety limit, not a product upsell. The customer must explicitly raise it.

## A7. Post-order messages

Target: exactly three milestones.

1. Confirmed and packing.
2. Picked up and out for delivery, with Swiggy's ETA when it is provided.
3. Delivered.

Current: every order id in a split checkout is polled, each order+milestone fires once via `notified_milestones`, and a 401 is caught per row. Fixed in Phase 4.

## A8. Error truth

Every error must say what happened and what the customer can do:

- Item out of stock: name it and offer a real alternative or skip it.
- Store closed: say it is closed and when it opens if Swiggy returns that.
- Price changed: say the price changed, by how much, and ask them to review the new receipt.
- Cap exceeded: say the cap, show the total, offer the explicit raise button.
- Swiggy or network failure: say it failed, do not claim the order was placed, and do not retry a non-idempotent checkout blindly.
- AI or model outage: say the assistant itself is unavailable, confirm nothing was changed, and offer one retry. Never turn an outage into "I didn't catch that". Live since 2026-10-27: `AI_OUTAGE_REPLY` names the outage, says the basket did not change, and asks the customer to resend in a minute. Each model call has an 8-second budget; a turn with routing plus evaluation can take about 16 seconds.
- WhatsApp send failure: log it and surface it. Never pretend the message was delivered.

## A9. Privacy

- `"delete my data"` must list what will be deleted, then delete it after confirmation.
- Target: delete the user row, onboarding context, display name, coordinates, address coordinates, approvals and checkouts, and revoke the Swiggy token.
- Current (2026-10-28): the handler deletes the token, inbound messages and cached geocodes, clears plan/onboarding/coordinates, and anonymizes the user row (`deleted-<uuid>`, no name, no Swiggy id). Live 24h scrub verification is pending. App queries run as the non-superuser `grocer_app` role (migration 007); RLS is intentionally absent because `anon` and `authenticated` have zero access to the schema (verified).

---

# Part B — Website Landing Page

## B1. Purpose

The website is the advertisement. A stranger should understand three things in under 30 seconds:

1. What Grocer is: a WhatsApp concierge for Swiggy Instamart.
2. What it can do for them: shop, ask, plan, manage addresses, track, pay.
3. How to try it: one tap to WhatsApp.

It is also the project showcase for reviewers: what is built, how the safety works, and what is proven.

It is **not** a dashboard. It does not show a customer's basket, addresses, orders or payments. It is not a second product UI.

## B2. CTA flow

Target:

1. The landing page has two primary actions: **Connect your number** (website handshake) and **Open WhatsApp** (direct chat).
2. The link is `https://wa.me/<NEXT_PUBLIC_WHATSAPP_NUMBER>`.
3. Website connect is number-first, ownership-proven. The visitor types a +91 mobile number; `POST /api/auth/whatsapp/start` validates it, rate-limits per IP and returns a signed 10-minute code. The page opens `wa.me` with `connect <code>`. The bot sends the Swiggy login link only when the sender's `wa_id` matches the code. No typed number is stored.
4. Swiggy OAuth remains a bot-sent bridge. The `?t=` link still works for reconnect.

Done 2026-11-04: the page now has a Connect section with the number-first form, backed by `/api/auth/whatsapp/start` and a `connect <code>` webhook branch. The signed `?t=` card still appears only for a bot link or a callback. A missing `NEXT_PUBLIC_WHATSAPP_NUMBER` disables the form with a visible note instead of linking to a placeholder.

## B3. Page sections

1. **Hero.** "Your Swiggy Instamart, on WhatsApp." Eyebrow, one line of support, **Connect your number** as the primary button, a "See how it works" anchor, three micro-facts, and a phone chat mockup stamped **Sample**. A "Built on" strip lists Swiggy Instamart tools, WhatsApp Cloud API, Groq and PostgreSQL, with the independent-app note.
2. **What it does.** Six plain cards with one coloured rule each: Build your basket, See live prices, Plan a meal, Switch addresses, Follow the order, Get help. The first card is tinted with the primary blue.
3. **How it works.** Three steps: Connect once, Send your list, Tap Pay. Each has a coloured top rule, no index numbers.
4. **Connect.** Left: the ownership explanation and three points (number not stored, 10-minute code, no password shared). Right: the number-first form. Success state shows an **Open WhatsApp** button carrying `connect <code>`.
5. **Demo.** Video section with three steps. Renders only when `public/demo.mp4` exists.
6. **Safety.** Surface band. Left: three checks (you tap, Grocer re-reads the basket, it runs once) and the ₹1,000 cap note. Right: a sample checkout with the bill, sample coupon, cap meter, a disabled Pay button and "Sample checkout · no payment taken".
7. **Under the hood.** Four facts: 20 Swiggy tools, 4 safety levels, 1 AI model, ₹1,000 cap, each with a coloured number. One line says every tool is reachable from chat or gets a clear "not supported".
8. **Privacy.** "Your address is not our inventory." Three points: deleted in 24 hours, protected Swiggy login, the typed number is not saved.
9. **Questions.** Six short FAQs: official Swiggy, connecting an account, paying, Grocer's fee, out of stock, data.
10. **Final CTA and footer.** A blue card with "Your next grocery run is a message away.", **Connect your number** and **Open WhatsApp**. Footer: brand, "Instamart, in your chats.", WhatsApp button, Privacy, Questions, trademark line and copyright.

Privacy lives at `/privacy`. `/proof` is kept as an internal evidence page and is not linked from the landing.

## B4. Claims policy

- No status badges on the landing. A capability is either described without a live claim, or the FAQ states its real status. Payment stays "not yet" until checkout opens.
- Sample baskets, coupons and checkout cards are stamped **Sample** and say no order or payment happened.
- No invented numbers, no "100%", no "best coupon" unless it is true.
- No "trusted by" logos, customer quotes or case studies. There are no customers to quote.
- No test counts, run dates or build statistics on the landing. The internal `/proof` page carries the evidence.
- No real customer data, order IDs, addresses or phone numbers.
- No fake screenshots. The hero phone is sample data, not a past order.
- Payment is never described as available. The FAQ says the chat, live prices and basket work today and payments open next.

## B5. Number policy

- The page renders no real phone number. The connect form's placeholder is the documented dummy.
- Link: `NEXT_PUBLIC_WHATSAPP_NUMBER`, read from the environment.
- Never commit or publish Karan's real number.
- If the env var is missing, the form and CTA show a visible note; they never point to a stranger.

## B6. Visual direction

- Gumloop tokens on a white canvas: `#FFFFFF` canvas, `#F7F7F7` surface, `#EEEEEE` raised, `#111111` ink, `#646464` muted, `#E2E2E2` border. Primary blue `#1E8CFF`; decorative purple `#8922EE`, mid blue `#147BD1`, green `#95BF47`, yellow `#F5C542`, brown `#522A10`.
- Multi-colour accents are used in rules, numbers and dots, never as a second call-to-action colour. Primary buttons are always blue.
- **Typography:** Fraunces (`--font-fraunces`) and Golos Text (`--font-golos`) via `next/font/google`. No italics anywhere. Display 40–48px, section headings 28–36px, body 16px, small 14px.
- Flat white surfaces with 1px borders; radii 8/10/12; no gradients, glass, glow or nested boxes.
- The hero shows a phone chat with sample bubbles and a basket card, not a dashboard. No stock photography. The logo mark is blue with a purple handle.

## B7. OAuth bridge

- Routes: `/api/auth/swiggy/login` and `/api/auth/swiggy/callback`; the website start route is `/api/auth/whatsapp/start`.
- Exact redirect: `https://grocerr.vercel.app/`.
- The bridge stores the phone in PKCE state and links the Swiggy token to that `wa_id`.
- Current: login requires a signed link token (HMAC, 1-hour TTL). The website start route mints a signed token with a 10-minute TTL and a per-IP rate limit; the webhook `connect <code>` branch compares the sender's `wa_id` before sending the OAuth link. PKCE state lives in `grocer.oauth_states` with a 10-minute one-time TTL. The state-cookie and origin-check hardening remain parked in `.scratch/parked/oauth-state-cookie.patch`; the current routes do not set a browser state cookie.
- The landing page must not render customer data after the callback. It only shows a success or failure state.

## B8. Landing page done condition

- A stranger understands the product in under 30 seconds.
- One primary button style (blue): connect on the page or open WhatsApp.
- Every claim is live, in testing, or opening next.
- No fake number, fake uptime, or invented statistic. Sample data is labeled.
- Mobile layout works at 360px width.
- The page does not pretend to be the product UI.

**State 2026-11-04 (white rebuild):** rebuilt on a white canvas with Gumloop tokens and blue/purple/green/yellow/brown accents. Order: phone-chat hero, six feature cards, three steps, Connect form, safety band, four coloured facts, privacy, FAQ, blue CTA. No italics; display type tops out at 48px. `npm run build` passes 8 routes; 1440/1024/768/390/360 have zero horizontal overflow; `/privacy` and `/proof` render; no console errors. The connect form ran in a browser through the Next proxy to the local FastAPI backend and received a real signed code; the WhatsApp `wa.me` URL carried `connect <token>`. Handset run still pending. The demo section stays hidden until `public/demo.mp4` exists. The OAuth state-cookie hardening is parked in `.scratch/parked/oauth-state-cookie.patch`.
