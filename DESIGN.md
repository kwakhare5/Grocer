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
2. Picked up and out for delivery, with ETA and live map link.
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

1. The landing page has one primary CTA: **Chat on WhatsApp**.
2. The link is `https://wa.me/<NEXT_PUBLIC_WHATSAPP_NUMBER>`.
3. Swiggy OAuth is a hidden bridge. The bot sends the reconnect link only when a customer needs to link or refresh Swiggy. The normal landing page does not ask for a phone number.

Done 2026-10-27: the phone form is gone. The page accepts a signed `?t=` link from the bot, and it never asks for a phone number. Rebuilt 2026-10-28: the WhatsApp button is the hero CTA; the OAuth card appears only for `?t=` or a callback; a missing `NEXT_PUBLIC_WHATSAPP_NUMBER` disables the button with a visible note instead of linking to a placeholder. Final rebuild 2026-11-01: printed sample receipt and a 9:16 demo slot in the hero, no PC window and no fake order.

## B3. Page sections

1. **Hero.** "Text the list. We’ll handle the rest." One sentence, the WhatsApp CTA, an early-access line, and a printed sample receipt beside a 9:16 demo slot. The receipt shows six sample products, a sample coupon and ₹312 to pay, stamped **Sample**. The demo slot appears only when `public/demo.mp4` exists in production; development shows a labelled placeholder. A missing WhatsApp env var disables the CTA with a visible note.
2. **What it does.** Six plain rows: Build the basket, Ask about prices, Plan dinner, Keep your addresses, Follow the rider, Pay once. Each row carries a small status: Live, In testing or Opening next. No internal tool names.
3. **Before you pay.** One dark band. Left: a three-step vertical timeline (you tap, we re-read the basket, it runs once) and the ₹1,000 cap note. Right: a sample checkout card with the bill, sample coupon, cap meter, a disabled Pay button and "Sample checkout · no payment taken".
4. **Built.** Six backend facts, led by "20 tools", plus a small "229 automated tests pass" line and a link to `/proof`. No test statistics as a headline section.
5. **Questions.** Six short FAQs: official Swiggy, connecting an account, paying, Grocer’s fee, out of stock, data.
6. **Footer.** Compact: brand, "Instamart, in your chats.", WhatsApp button, Privacy, Run log, Questions, trademark line and copyright.

Privacy lives at `/privacy`; the run log lives at `/proof`. There is no founder section, no separate privacy section, no proof-stat band and no phone form.

## B4. Claims policy

- Every claim is either **live today**, labeled **in testing**, or labeled **opening next**.
- Sample baskets, coupons and checkout cards are stamped **Sample** and say no order or payment happened.
- No invented numbers, no "100%", no "best coupon" unless it is true. Current code tries up to two applicable coupons and only keeps one that lowers the total.
- No "Systems Operational" badge unless it is wired to a real health check and can show degraded.
- No real customer data, order IDs, addresses or phone numbers.
- No fake screenshots. The hero receipt is sample data, not a past order.
- Payment is never described as available. "Payments open soon. The chat is live today." is the current status line.

## B5. Number policy

- The page shows no phone number.
- Link: `NEXT_PUBLIC_WHATSAPP_NUMBER`, read from the environment.
- Never commit or publish Karan's real number.
- If the env var is missing, the CTA becomes a disabled button with a visible note; it never points to a stranger.

## B6. Visual direction

- Light paper (`#f4f2ed`) with a darker paper section, ink green, and Swiggy orange (`#FC8019`) as the only accent. One dark safety band and a dark footer.
- Clean, warm, mobile-first. Generous spacing. Large Fraunces headings, Golos Text body, one idea per section.
- **Typography:** Fraunces (`--font-fraunces`) and Golos Text (`--font-golos`) via `next/font/google`.
- Interface surfaces: 12px buttons, 16px cards, 24px panels. The printed receipt is a paper prop with an 8px edge and a perforated bottom; the demo frame is 30px. No glass, no gradient glows, no nested cards.
- Show the product as a printed receipt and a phone-shaped demo slot, not a fake dashboard. No stock photography. No video-editor aesthetic.

## B7. OAuth bridge

- Routes: `/api/auth/swiggy/login` and `/api/auth/swiggy/callback`.
- Exact redirect: `https://grocerr.vercel.app/`.
- The bridge stores the phone in PKCE state and links the Swiggy token to that `wa_id`.
- Current: login requires a signed bot link (HMAC, 1-hour TTL). PKCE state lives in `grocer.oauth_states` with a 10-minute one-time TTL. The login route sets a 10-minute `grocer_oauth_state` cookie; the callback refuses a state that does not match this browser, so a copied callback link cannot link the wrong session.
- The landing page must not render customer data after the callback. It only shows a success or failure state.

## B8. Landing page done condition

- A stranger understands the product in under 30 seconds.
- One primary CTA to WhatsApp.
- Every claim is live, in testing, or opening next.
- No fake number, fake uptime, or invented statistic. Sample data is labeled.
- Mobile layout works at 360px width.
- The page does not pretend to be the product UI.

**State 2026-11-03:** live at `https://grocerr.vercel.app` on the `1468b16` code; `/`, `/privacy` and `/proof` return 200 and the page says 229 tests. `verify.ps1 -Db` passes (153 offline + 76 database tests, ruff, Next 16.4.3 build). Checked at 1440/1024/768/390/360 with zero horizontal overflow; the skip link is removed; the first Tab lands on the brand; both subpages render. Production output contains no demo placeholder and no phone number; the demo slot stays hidden until `public/demo.mp4` exists. Security headers are live. The OAuth state-cookie hardening is parked in `.scratch/parked/oauth-state-cookie.patch`; the proven routes are live. `npm audit --omit=dev` reports 0 vulnerabilities. A phone tap on the CTA is still unproven.
