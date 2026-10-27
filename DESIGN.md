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
- Replies are in English. Grocer understands Hindi and Hinglish grocery words but writes back in English.

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

Current gap: the receipt prints a coupon line but the savings message is never sent (`backend/agent/customer_advocate.py:251`). Long receipts are truncated at 1024 characters (`backend/channels/whatsapp_client.py:105`). The target is to split long receipts, never silently drop lines.

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

Current: the basket path sends two quick replies, `[Pay ₹X]` (`pay:<approval_id>`) and `[Clear Basket]` (`cart:clear`). After the pay tap, the bot sends a CTA URL button, `[Pay on Swiggy]`, using the HTTPS `bridgeUrl`.

Target: one CTA URL button `[Pay ₹X (UPI / Card)]`, plus up to two secondary actions:
1. `[Cash on Delivery]` when Swiggy offers it.
2. `[Change Address]` or `[Change Items]`.

A CTA URL button opens Swiggy's payment page. A quick reply only sends a button ID back to Grocer. Do not mix them up.

### A4.2 Clear basket

Current and target: preview first, then two buttons, `[Clear Cart]` (`cart:clear`) and `[Keep Cart]` (`cart:keep`). Never clear on a text guess.

### A4.3 Address switch and delete

- Switch: show the saved addresses as a list (max 10 rows), then confirm. Current code writes `sessions.active_address_id` only; it does not clear or rebuild the basket. The target is to warn, clear and rebuild.
- Delete: `[Confirm Delete: <Label>]` and `[Keep Address]`. The target guard refuses deletion when an active delivery uses that address. Current code only refuses the last/current address.

### A4.4 Token expiry

Target copy:

> Your Swiggy login needs a quick security refresh. Tap below to reconnect. Your grocery list is saved.

Button: `[Reconnect Swiggy]` (CTA URL to the allowlisted OAuth redirect).

Current gap: the webhook writes `status='parked'` but replay waits for `awaiting_link`, and the callback does not re-execute the saved message. Do not claim the list resumes automatically until that is fixed.

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
- UPI requires `intentApp` or `generateUPIQR` from `get_payment_options`. The current client sends neither; that is a P0 gap.
- COD is the second path. SwiggyPay is later, only when the live response offers it.
- The ₹1,000 cap is a safety limit, not a product upsell. The customer must explicitly raise it.

## A7. Post-order messages

Target: exactly three milestones.

1. Confirmed and packing.
2. Picked up and out for delivery, with ETA and live map link.
3. Delivered.

Current gaps: the "Confirmed" branch can repeat every 30 seconds, a 401 can kill the poller, and split orders 2..n are not notified. Do not promise reliable milestones until those are fixed.

## A8. Error truth

Every error must say what happened and what the customer can do:

- Item out of stock: name it and offer a real alternative or skip it.
- Store closed: say it is closed and when it opens if Swiggy returns that.
- Price changed: say the price changed, by how much, and ask them to review the new receipt.
- Cap exceeded: say the cap, show the total, offer the explicit raise button.
- Swiggy or network failure: say it failed, do not claim the order was placed, and do not retry a non-idempotent checkout blindly.
- WhatsApp send failure: log it and surface it. Never pretend the message was delivered.

## A9. Privacy

- `"delete my data"` must list what will be deleted, then delete it after confirmation.
- Target: delete the user row, onboarding context, display name, coordinates, address coordinates, approvals and checkouts, and revoke the Swiggy token.
- Current: the handler deletes the token and nulls some payloads, but leaves the user row, onboarding context, display name and coordinates. Do not claim a full purge until that is fixed.

---

# Part B — Website Landing Page

## B1. Purpose

The website is the advertisement. A stranger should understand three things in under 30 seconds:

1. What Grocer is: a WhatsApp concierge for Swiggy Instamart.
2. What it can do for them: shop, ask, reorder, manage addresses, track, save money.
3. How to try it: one tap to WhatsApp.

It is also the project showcase for reviewers: what is built, how the safety works, and what is proven.

It is **not** a dashboard. It does not show a customer's basket, addresses, orders or payments. It is not a second product UI.

## B2. CTA flow

Target:

1. The landing page has one primary CTA: **Chat on WhatsApp**.
2. The link is `https://wa.me/<NEXT_PUBLIC_WHATSAPP_NUMBER>`.
3. Swiggy OAuth is a hidden bridge. The bot sends the reconnect link only when a customer needs to link or refresh Swiggy. The normal landing page does not ask for a phone number.

Current: the page shows a phone-entry form and runs the OAuth flow. **Decision 2026-10-27: remove it.** The landing page never asks for a phone number. OAuth is only reached from a button the bot sends.

## B3. Page sections

1. **Hero.** "Groceries on WhatsApp. Real Swiggy Instamart." One sentence: chat naturally, see live prices, tap once to pay. Primary CTA.
2. **Problem.** Grocery apps are heavy. People already live in WhatsApp. Grocer removes the app hop.
3. **What Grocer does.** Shopping lists, price/stock questions, saved addresses, order history, tracking, coupons, reorders. Cover only tool-backed abilities. Mark which are live today and which are coming next. Recipes are not a Swiggy tool, so they are not a product claim.
4. **The 3-lock safety story.** Physical tap only; live cart re-check; exactly-once lock. Explain in plain words, not internal names.
5. **What is live today.** Pull from `STATUS.md`. Do not list a feature as live if it is partial or fixture-only. Current live: read answers, basket add, address list/switch preview, coupon discovery. Checkout is not live.
6. **How it works.** Three steps: open WhatsApp, connect Swiggy, chat and tap to pay.
7. **Privacy.** 24-hour data minimization, encrypted Swiggy tokens, "delete my data". Only claim what the code does.
8. **Proof.** Real tests, real Swiggy reads, Groq router eval. No invented percentages, no fake uptime.
9. **FAQ.** Is this official Swiggy? What happens if an item is out of stock? Can I cancel? How do I delete my data?
10. **Footer CTA.** One WhatsApp button. No fake status badge.

## B4. Claims policy

- Every claim is either **live today** or labeled **coming next**.
- No invented numbers, no "100%", no "best coupon" unless it is true. Current code tries the first two applicable coupons and only keeps one that lowers the total.
- No "Systems Operational" badge unless it is wired to a real health check and can show degraded.
- No real customer data, order IDs, addresses or phone numbers.
- No fake screenshots. If a WhatsApp mockup is shown, it must match the current copy or be labeled as a concept.

## B5. Number policy

- Display: placeholder `+91 98765 43210`.
- Link: `NEXT_PUBLIC_WHATSAPP_NUMBER`, which is read from the environment.
- Never commit or publish Karan's real number.
- If the env var is missing, the CTA must fail loudly in development, not silently point to a stranger.

## B6. Visual direction

- Keep the current dark charcoal background with Swiggy orange (`#FC8019`) as the accent. It fits the product and already exists.
- Clean, warm, mobile-first. Generous spacing. Large type. One idea per section.
- No video-editor aesthetic, no dense creative-tool chrome. `docs/archive/design-reference.md` was a Cardboard.ai video-editor system and is archived; do not use it as the landing-page spec.
- Show the product with real WhatsApp-style receipts and buttons, not a fake dashboard.

## B7. OAuth bridge

- Routes: `/api/auth/swiggy/login` and `/api/auth/swiggy/callback`.
- Exact redirect: `https://grocerr.vercel.app/`.
- The bridge stores the phone in PKCE state and links the Swiggy token to that `wa_id`.
- Target: DB-backed state with a TTL and a signed WhatsApp ticket. Current state is in process memory and the login accepts any phone; this is a security gap.
- The landing page must not render customer data after the callback. It only shows a success or failure state.

## B8. Landing page done condition

- A stranger understands the product in under 30 seconds.
- One primary CTA to WhatsApp.
- Every claim is live or labeled coming next.
- No fake number, fake uptime, or invented statistic.
- Mobile layout works at 360px width.
- The page does not pretend to be the product UI.
