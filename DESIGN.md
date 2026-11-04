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
2. What it can do for them: shop, ask, plan, manage addresses and orders, and control their data.
3. How to try it: connect Swiggy once, then chat.

It is also the project showcase for reviewers: what is built, how the safety works, and what is proven.

It is **not** a dashboard. It does not show a customer's basket, addresses, orders or payments. It is not a second product UI.

## B2. CTA flow

1. The landing page has one primary action: **Connect your Swiggy account**. The header, hero, final CTA and the connect form's submit all use the same black primary button. There is no filled accent button.
2. A direct chat is a small secondary link, **Already connected? Open the chat**, not a competing button. Footer contact uses **Open chat**.
3. The WhatsApp link is `https://wa.me/<NEXT_PUBLIC_WHATSAPP_NUMBER>`.
4. Website connect is number-first, ownership-proven. The visitor types a +91 mobile number; `POST /api/auth/whatsapp/start` validates it, rate-limits per IP and returns a signed 10-minute code. The page opens `wa.me` with `connect <code>`. The bot sends the Swiggy login link only when the sender's `wa_id` matches the code. No typed number is stored.
5. Swiggy OAuth remains a bot-sent bridge. The `?t=` link still works for reconnect.

The Connect band sits directly below the hero. The signed `?t=` card still appears only for a bot link or a callback. A missing `NEXT_PUBLIC_WHATSAPP_NUMBER` disables the form with a visible note instead of linking to a placeholder. A visible fallback and a `<noscript>` link open WhatsApp directly if the form cannot run.

## B3. Page sections

1. **Hero.** Pill with the pink mascot, "Your Swiggy Instamart, on WhatsApp.", one support line, black **Connect your Swiggy account** and ghost **See how it works**, a small already-connected chat link, three micro-facts, and a phone-style WhatsApp sample. The phone has a status bar, a Grocer header with the blue bag avatar, three real item lines and To Pay ₹187; the caption says **Sample**. On phones the three micro-facts stack with no dangling separators. At 1280px and wider, a small ink-and-paper grocery cluster sits beside the phone's lower-left edge: bag, receipt, milk, bread, eggs and coriander.
2. **Connect band.** Surface gray, not a color field. Left: "Connect Swiggy once. Then it's just chat.", the service-area line and three steps with blue markers. Right: the number-first form with a black submit and an Indian-numbers-only note. Success shows a black **Open WhatsApp** button carrying `connect <code>`.
3. **Facts strip.** A white ruled strip below the connect band with four plain numbers: 20 Instamart tools, ₹1,000 default cap, 3 checkout locks, 24h data deletion. These are facts, not live metrics.
4. **What you can do.** Eight features in a two-column ruled list, no cards: plain-words basket, live prices and stock, saved addresses, orders and bills, coupons, meal plans, support reports and data deletion. Each has a small hand-drawn mark in its accent colour and a bright underline: chat, price tag, house, receipt, ticket, pot, lifebuoy, bin. Below it, **Try a message**: five prompt chips that update a WhatsApp-style reply panel with real copy and a short typing indicator.
5. **How it works.** A wide ink route above the three steps: message → Swiggy store → basket → bill, with four small illustrations and labels. On phones the route stacks vertically with a vertical rule. Below it, three steps with green number markers: text your list, read the basket, check the bill. Checkout is not a step yet.
6. **Demo.** A black video stage with a small red-dot **Recording** chip in the corner; no card chrome and no play icon. With no file it says the demo is being recorded; when `public/demo.mp4` exists the stage renders the real player. The lead says the walkthrough is on the way.
7. **Safety (dark band).** "One gate before money." Left: a red lock beside the Safety label, three checks, the ₹1,000 cap and a sample cap meter (₹187 of the sample ₹1,000, an 18.7% orange fill, labelled **Sample**). Right: a white paper bill with dashed rules, real item lines, a red **Sample** stamp, To Pay ₹187 and a disabled Pay.
8. **FAQ.** Eight short answers: official app, Swiggy app needed, connecting, paying, fee, service area, out of stock and data.
9. **Final CTA.** Surface gray panel, five bag mascots, "Your next grocery run is a message away.", black **Connect your Swiggy account**, and the already-connected chat link.
10. **Footer.** White, five columns (brand, Product, Project, Built on, Contact), legal line and copyright. The logo is the original smiling bag in brand blue.

Privacy lives at `/privacy`. `/proof` is an internal evidence page and is not linked from the landing.

## B4. Claims policy

- No status badges on the landing. A capability is either described without a live claim, or the FAQ states its real status. Payment stays "not yet" until checkout opens.
- Honesty anchors are limited to four places: the footer legal line, the FAQ payment answer, the Safety sentence "It cannot place an order", and one **Sample** label per mock (phone caption, Try caption, bill stamp). The cap meter labels its number **Sample**. Repeated disclaimers are not used.
- No invented numbers, no "100%", no "best coupon" unless it is true. The fact strip repeats only fixed product facts, and the cap meter reuses the sample bill's ₹187.
- No "trusted by" logos, customer quotes or case studies. There are no customers to quote.
- No test counts, run dates or test-status labels on the landing. The internal `/proof` page carries the evidence.
- No real customer data, order IDs, addresses or phone numbers.
- No fake screenshots. The hero chat is sample data, not a past order.
- Payment is never described as available. The FAQ says the chat, live prices and basket work today and payments open next.

## B5. Number policy

- The page renders no real phone number. The connect form's placeholder is the documented dummy.
- Link: `NEXT_PUBLIC_WHATSAPP_NUMBER`, read from the environment.
- Never commit or publish Karan's real number.
- If the env var is missing, the form shows a visible note; it never points to a stranger.

## B6. Visual direction

- Gumloop is an inspiration, not a skin: white canvas `#FFFFFF`, surface `#F7F7F7`, ink `#0B0B0C`, body `#3D3D3D`, muted `#6B6B6B`, border `#E5E5E5`, border strong `#D4D4D4`.
- **Black is the primary action color.** Header, hero, final CTA and the connect submit are black with white labels. Secondary buttons are white with a 1px border. There is no filled accent button; the selected prompt chip uses soft blue with a blue border.
- **One section, one color role.** Connect blue; What pink; How green; Demo orange; Safety red; FAQ blue. Feature marks cycle through blue, green, orange, pink and red with a small bright underline. Green is also the online/success status; red is also the error color.
- **Exact Gumloop category colors, measured from the home screenshot:** blue `#03A2FE`, pink `#FB3C98`, green `#00A63E`, orange `#FE9A00`, red `#F54900`. Violet `#9810FA` is on Gumloop but is not used on Grocer at all. Darker ink variants (`--blue-strong`, `--pink-strong`, etc.) keep small text readable; the bright values fill dots, underlines, mascots and marks.
- **No large color fields.** Section backgrounds stay white, surface gray or the single dark safety band. Blue, orange, pink, green and red are small marks, stamps, plus signs, mascots or state cues. There is no cream or yellow page band and no yellow bill.
- Blue `#1E8CFF` is the logo and focus ring only. The logo is the original smiling bag in one blue with a white face.
- **Illustration:** one ink-line language, `#0B0B0C` strokes with flat accent fills. Fourteen small drawings: one grocery cluster, eight feature marks, four route marks and a lock. They are drawn in SVG in code; no stock photos, no generated 3D food, no gradients, no decorative blobs.
- **Motion:** one signature move — the How route draws from 0 to 1 and its nodes land in sequence. The bill's lines print, then the Sample stamp presses down. Hero media enters with a small scale; the phone's two bubbles, receipt and input stagger in; sections rise 14px and fade once; the cap meter fills to 18.7%; feature underlines grow on hover; nav links underline from the left; buttons press to 0.97; Try replies crossfade; FAQ plus rotates; CTA mascots lift on hover. Controls use 120–180ms, reveals 220–550ms, the route 800ms, all with a strong ease-out. Transform and opacity only; no animation library; reduced motion removes travel and drawing, and no-JS shows all content.
- **Header:** a three-column grid — logo left, nav centered, one black **Connect Swiggy** action right. Desktop nav labels are Features, How it works, Demo, Safety, FAQ. Hover shows a short underline. Below 980px the nav collapses to the Menu disclosure.
- **Page frame:** `--wrap-max` is 1180px and `--pad-x` is `clamp(24px, 6vw, 80px)`, giving 130px side gutters at 1440px. The header actions align to the same right edge as the content.
- **Typography:** Fraunces and Golos Text via `next/font/google`. No italics. H1 48px, H2 36px, H3 18–24px, body 16px, nav 14px, captions 12–13px.
- Flat surfaces with 1px borders; radii 8/12. No gradients, glass, glow, heavy shadows or nested boxes.
- The product frames look like working UI, not stock photography. The demo stage is a black recording slate with a REC chip, not a decorative video card.
- The Try panel and the illustrations are the playful layer; motion stays quiet and one-time.

## B7. OAuth bridge

- Routes: `/api/auth/swiggy/login` and `/api/auth/swiggy/callback`; the website start route is `/api/auth/whatsapp/start`.
- Exact redirect: `https://grocerr.vercel.app/`.
- The bridge stores the phone in PKCE state and links the Swiggy token to that `wa_id`.
- Current: login requires a signed link token (HMAC, 1-hour TTL). The website start route mints a signed token with a 10-minute TTL and a per-IP rate limit; the webhook `connect <code>` branch compares the sender's `wa_id` before sending the OAuth link. PKCE state lives in `grocer.oauth_states` with a 10-minute one-time TTL. The state-cookie and origin-check hardening remain parked in `.scratch/parked/oauth-state-cookie.patch`; the current routes do not set a browser state cookie.
- The landing page must not render customer data after the callback. It only shows a success or failure state.

## B8. Landing page done condition

- A stranger understands the product in under 30 seconds.
- One primary button style (black); no filled accent button.
- Every claim is live, in testing, or opening next.
- No fake number, fake uptime, or invented statistic. Sample data is labeled.
- Mobile layout works at 360px width.
- The page does not pretend to be the product UI; the sample chat and bill are illustrative.
- The demo section is a plain stage, and the interactive panel uses real replies.

**State 2026-11-04 (exact Gumloop palette):** connect band is surface gray with a black submit and blue step markers; the paper bill is white with a red Sample stamp; the video section is a plain stage with no card chrome; the feature list sits above a working **Try a message** panel with five real replies. Accents use the exact colors measured from the Gumloop home screenshot: blue `#03A2FE`, pink `#FB3C98`, green `#00A63E`, orange `#FE9A00`, red `#F54900`; violet and yellow are gone. Header is logo / centered nav / one black **Connect Swiggy** action, and the page frame is 1180px inside 130px gutters at 1440px. The hero chat avatar is the blue bag logo, and the Try panel uses the same logo; phone micro-facts stack cleanly. `npm run build` passes 9 routes, including the OG image; 1440/1024/768/390/360 show zero horizontal overflow and zero console errors. Browser tests: a bad number is blocked, a valid dummy number returns a real signed token through the proxy, the sixth attempt returns 429, and the Try reply, typing indicator, FAQ, menu and all anchors work. `verify.ps1 -Db` exits 0 (182 offline + 81 database tests). Pushed; Vercel serves the page, and production passes the same five-width check with zero overflow and zero console errors. Handset connect and Swiggy OAuth passed 2026-11-04. `public/demo.mp4` is still absent; the stage shows the recording state.

**Graphics + motion pass (local, not pushed):** the eight feature numbers are now ink marks; a grocery cluster sits beside the chat at 1280px and wider; the How route draws from 0 to 1 with staggered nodes; the bill prints its lines and the Sample stamp presses in. Measured with reduced motion off: route line at scale 0 before scroll, 0.34 at 120ms, 1 at 1s; nodes 0 then 1; bill item at 0.96 at 150ms; stamp 0 then 1 at its final -7° rotation. Reduced motion and no-JS keep everything visible. Gate v7 passes 9 routes, 182 offline + 81 DB, 0 overflow and 0 console errors at five widths. Vercel still serves the palette version without these graphics until the next push.

**Copy cleanup + phone pass (local, not pushed, 2026-11-04):** the hero right side is now a phone-style WhatsApp sample instead of a wide chat card; the phone aligns with the copy's left edge at 1040px and below. Removed the connect form's two meta paragraphs, the demo's "stop before payment" and "No order is placed" lines, and the Try caption's "No order is placed"; the caption is now "Sample reply." Added the four-fact strip and the sample cap meter. The demo stage is black with a REC chip. The only remaining payment/no-order statements are the four honesty anchors above. Dead CSS for the old chat buttons, receipt fees, form meta and bill captions is removed. Proof: 9 routes build, 0 overflow and 0 console errors at 1440/1024/768/390/360, all reveals triggered, no repeated disclaimer strings, reduced-motion and no-JS show all content; phone bubbles settle at opacity 1, the cap meter settles at scaleX 0.187; `verify.ps1 -Db` exit 0 (182 offline + 81 DB); five-width screenshots `final_*` in `.scratch`. Pushed as `c16b924`; Vercel serves this pass, and production repeats the five-width pass with 0 overflow, 0 console errors and 0 hidden reveals.

