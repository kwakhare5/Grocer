# DESIGN.md — Grocer v5.0 WhatsApp Interaction & UX Specification

> **Platform:** WhatsApp Business Cloud API  
> **Target Form Factors:** Android & iOS Mobile WhatsApp Clients  
> **Core Constraint:** Meta Interactive Message Limits (Max 3 Quick-Reply Buttons, Max 10 List Rows, Max 1024 chars in Interactive Body)  

---

## 1. Visual Hierarchy & Receipt Card Typography

WhatsApp does not support rich HTML or markdown tables. All structured receipts are formatted using WhatsApp-native monospaced and bold markdown tokens.

### Canonical Receipt Card Template:

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

### Out-of-Stock / Unserviceable Items Section:
When an item is unavailable, it is never dropped silently. It appears under a dedicated warning section directly beneath the basket lines:

```
⚠️ *Not added (Out of stock at Bandra store):*
• Amul Salted Butter (100g)
(Available alternative: Mother Dairy Table Butter 100g)
```

---

## 2. Interactive Action Layouts (The 3-Button Limit)

Meta allows up to 3 buttons per interactive message. Grocer uses discrete combinations based on conversation state:

### State A: Active Basket (Review & Checkout)
1. **Button 1 (Primary - CTA URL):** `[Pay ₹555 (UPI / Card)]`  
   - Payload: Opens Swiggy HTTPS `bridgeUrl`.
2. **Button 2 (Secondary - Quick Reply):** `[Cash on Delivery]` (if enabled) OR `[Change Address]`
3. **Button 3 (Tertiary - Quick Reply):** `[Change Items]`  
   - Payload: Returns to conversational item editing.

### State B: Two-Step Clear Cart Confirmation
1. **Button 1:** `[Clear Cart]` (ID: `clear_cart_confirm:<token>`)
2. **Button 2:** `[Keep Cart]` (ID: `modify_cart`)

### State C: 5-Day Token Expiration
1. **Button 1 (CTA URL):** `[Connect Swiggy]` (Opens OAuth callback)

---

## 3. Conversational Tone & Persona

- **Concierge, Not Robot:** Friendly, direct, minimalist Indian neighborhood grocer.
- **Strict English Voice:** Understands Hindi and Hinglish grocery terms (*doodh, dahi, atta, tamatar, pyaz*), but always writes back in crisp, natural, polite English.
- **Zero Academic or Internal Jargon:** Never quote internal variable names, status codes (`400`, `500`), or technical constraints. Explain things from the customer's point of view:
  - ❌ *"ProviderAuthError: token expired at 1729837200"*
  - ✅ *"Your Swiggy login needs a quick 5-day security refresh. Tap below to reconnect."*

---

## 4. Post-Order Milestone Push Notifications

Delivery notifications are restricted to 3 discrete milestones to avoid notification fatigue:

### Milestone 1: Confirmed & Packing
> 🛵 *Your Swiggy Instamart order #IM-982314 is confirmed! The Bandra dark store is packing your items now.*

### Milestone 2: Picked Up & Out for Delivery
> 🛵 *Your delivery partner Ramesh has picked up your bag and is on the way!*  
> ⏱️ *ETA: 8–12 mins*  
> 📍 *Live Map:* `https://swiggy.com/track/IM-982314`

### Milestone 3: Delivered
> 📦 *Your order has been delivered! Enjoy your groceries.*
