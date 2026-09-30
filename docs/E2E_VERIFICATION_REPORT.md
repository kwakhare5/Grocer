# GROCER End-to-End (E2E) Verification Report

- **Generated At (UTC):** `2026-09-30T14:04:35.468143+00:00`
- **Execution Mode:** `LIVE_GEMINI_API`
- **Primary Gemini Model:** `gemini-3.5-flash-lite`
- **Fallback Cascade:** `gemini-3.5-flash-lite -> gemini-flash-lite-latest -> gemini-3-flash-preview`
- **Total Multi-Turn E2E Latency:** `107902 ms`
- **Overall Verdict:** **`PASSED`** (`6/6` invariants verified)

---

## 1. Failure Mode Matrix & Verified Invariants

| ID | Subsystem Boundary | Failure Mode Prevented | Status |
| :--- | :--- | :--- | :---: |
| `INV-ADDR-01` | Upfront Multi-Address Disambiguation | Prompts customer with full street + area addresses before building a new cart when >1 addresses exist. | **PASS** |
| `INV-ADDR-02` | Full Street + Area Preservation | Preserves complete Flat/Building/Area/City/State in both prompt and receipt header/footer. | **PASS** |
| `INV-CART-01` | Parallel Recipe Decomposition & Receipt Math | Decomposes dish into multiple ingredients in parallel and reconciles Subtotal + Fees == Grand Total. | **PASS** |
| `INV-CART-02` | Delta Cart Merge (No Item Wipe) | Adding a follow-up item ('also add 1 amul milk 1L') merges onto existing cart items without dropping previous items. | **PASS** |
| `INV-GUARD-01` | Hesitation Guard ('wait') | Holds active basket intact when customer expresses hesitation instead of wiping cart or placing order. | **PASS** |
| `INV-CHECKOUT-01` | Server-Side Checkout Authorization Gate | Authorizes checkout only on explicit human confirmation ('Confirm') and generates order ID / QR state. | **PASS** |

---

## 2. Multi-Turn E2E Conversation Transcript & State Transitions

### Turn 1: `i wanna make pasta under 1500`
- **State Transition:** `NEEDS_DECISION`
- **Latency:** `0 ms`
- **Active Basket Items:** `0` (`Grand Total: ₹0`)

```text
📍 *Which address should I deliver this order to?*

*1.* Flat No 201, Everest Graciana, Opposite Yash Laxmi Heights, Sangvi, Pune, Maharashtra
*2.* D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra

👉 Reply *1*–*2* to select your delivery address!
```

### Turn 2: `2`
- **State Transition:** `AWAITING_CHECKOUT_CONFIRMATION`
- **Latency:** `58216 ms`
- **Active Basket Items:** `4` (`Grand Total: ₹281`)

```text
I've updated your delivery address to *D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra*! 📍

🛒 *Your Basket (D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra)*
• 1x Yu Zero Maida Penne Pasta 500g (500 g) — ₹49
• 1x Veeba Pasta & Pizza Sauce 280g (280 g) — ₹79
• 1x Amul Mozzarella Diced Cheese 200g (200 g) — ₹110
• 1x Fresh Garlic 100g (100 g) — ₹38

*Subtotal:* ₹276
*Delivery Fee:* FREE (₹0)
*Packaging & Handling:* ₹5
*Grand Total:* ₹281

📍 *Delivering to:* D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra
👉 Reply *Confirm* to place order, or tell me what to change!
```

### Turn 3: `also add 1 amul milk 1L`
- **State Transition:** `AWAITING_CHECKOUT_CONFIRMATION`
- **Latency:** `44705 ms`
- **Active Basket Items:** `5` (`Grand Total: ₹347`)

```text
🛒 *Your Basket (D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra)*
• 1x Yu Zero Maida Penne Pasta 500g (500 g) — ₹49
• 1x Veeba Pasta & Pizza Sauce 280g (280 g) — ₹79
• 1x Amul Mozzarella Diced Cheese 200g (200 g) — ₹110
• 1x Fresh Garlic 100g (100 g) — ₹38
• 1x Amul Taaza Milk 1L Pouch (1 L) — ₹66

*Subtotal:* ₹342
*Delivery Fee:* FREE (₹0)
*Packaging & Handling:* ₹5
*Grand Total:* ₹347

📍 *Delivering to:* D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra
👉 Reply *Confirm* to place order, or tell me what to change!
```

### Turn 4: `wait`
- **State Transition:** `AWAITING_CHECKOUT_CONFIRMATION`
- **Latency:** `0 ms`
- **Active Basket Items:** `5` (`Grand Total: ₹347`)

```text
No problem, I've kept your basket on hold! 🛒

Your groceries are still saved. Whenever you're ready, let me know if you want to add/remove items, switch delivery address, or clear your basket.

🛒 *Your Basket (D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra)*
• 1x Yu Zero Maida Penne Pasta 500g (500 g) — ₹49
• 1x Veeba Pasta & Pizza Sauce 280g (280 g) — ₹79
• 1x Amul Mozzarella Diced Cheese 200g (200 g) — ₹110
• 1x Fresh Garlic 100g (100 g) — ₹38
• 1x Amul Taaza Milk 1L Pouch (1 L) — ₹66

*Subtotal:* ₹342
*Delivery Fee:* FREE (₹0)
*Packaging & Handling:* ₹5
*Grand Total:* ₹347

📍 *Delivering to:* D block 704, Tanish Orchid, Charholi Budruk, Pune, Maharashtra
👉 Reply *Confirm* to place order, or tell me what to change!
```

### Turn 5: `Confirm`
- **State Transition:** `AWAITING_PAYMENT`
- **Latency:** `4981 ms`
- **Active Basket Items:** `0` (`Grand Total: ₹0`)

```text
Your order is ready! Please complete payment to place your order: https://instamart.swiggy.com/pay/bridge/paas_mock_03a37382
```

### Turn 6: `clear cart`
- **State Transition:** `READY`
- **Latency:** `0 ms`
- **Active Basket Items:** `0` (`Grand Total: ₹0`)

```text
🗑️ *Basket Cleared!*

Your basket is now completely empty. What groceries can I get for you today?
```

