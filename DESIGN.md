# DESIGN.md — Visual System & UI Vibe

> **Source of Truth**: `taste-skill` and [globals.css](file:///d:/Grocer/app/globals.css)

---

## 1. Aesthetic Direction & Vibe
- **Design Theme:** Warm modern editorial grocery concierge. Clean, tactile, high legibility.
- **Background Feel:** Soft warm canvas (`#FBFBF9`), crisp card surfaces (`#FFFFFF`), subtle muted borders (`#E5E5DF`).
- **Density:** Compact, high-information receipt cards and WhatsApp interactive bubbles.

---

## 2. Color Palette (Tokens)

| Token | CSS Variable / Hex | Purpose |
|---|---|---|
| Background | `var(--background)` (`#FBFBF9`) | Main canvas background |
| Surface Card | `var(--surface-card)` (`#FFFFFF`) | Elevated shopping cards, simulator panels |
| Surface Muted | `var(--surface-muted)` (`#F4F4F0`) | Inactive areas, code blocks, message bubbles |
| Border | `var(--border)` (`#E5E5DF`) | Subtle 1px structural separators |
| Foreground | `var(--foreground)` (`#09090B`) | Primary headers, item names, prices |
| Foreground Muted | `var(--foreground-muted)` (`#52525B`) | Secondary captions, variant notes, taxes |
| Primary / Emerald | `var(--primary)` (`#16A34A`) | Checkout buttons, savings badges, confirmed states |
| Primary Hover | `var(--primary-hover)` (`#15803D`) | Button hover state |
| Accent Orange | `var(--accent-orange)` (`#EA580C`) | Swiggy brand accents, urgent alerts |
| Destructive | `#EF4444` | Clear cart, item drops, errors |

---

## 3. Typography & Hierarchy
- **Heading & Editorial Font:** `Lora` / Georgia / Serif (`var(--font-editorial)`) for hero headings and culinary flair.
- **Body Font:** `Geist Sans` / Inter / system-ui (`var(--font-sans)`).
- **Monospace Font:** `Geist Mono` (`var(--font-mono)`) for SKU numbers, UPI links, and prices.
- **Scale:**
  - `H1`: 32px / font-semibold / tracking-tight
  - `H2`: 24px / font-semibold
  - `H3`: 18px / font-medium
  - `Body`: 14px / font-normal / leading-relaxed
  - `Caption`: 12px / font-medium / text-muted

---

## 4. WhatsApp Conversational UI Standards
- **Receipts:**
  - Clean markdown layout with product name, quantity, and unit price in rupees (`₹`).
  - Itemized subtotal, delivery fee, taxes, packaging, and coupon discount badge.
  - Prominent `Total Saved: ₹...` badge whenever coupons or threshold staples are applied.
- **Interactive Action Buttons (Meta Cloud API):**
  - Order review: 2 buttons max (`Confirm Order`, `Change Items`).
  - Clear cart: Dual confirmation (`Confirm Clear Cart`, `Keep Cart`).
  - Payment: Clickable `upi://pay` dynamic deep link (1 tap to open Google Pay / PhonePe) + secondary COD button where supported.
- **Voice & Tone:**
  - Strict, friendly, natural English.
  - No robotic prefixes or internal debug logs exposed to customer.

---

## 5. Anti-Slop Checklist
- [ ] No generic AI purple-on-black gradient backgrounds.
- [ ] No fake metrics or decorative dummy counters.
- [ ] No raw JSON or internal error strings printed in chat.
- [ ] Never omit out-of-stock items silently; report them with radical honesty.
- [ ] All interactive buttons must have verified payload IDs handled by the fast dispatcher.
