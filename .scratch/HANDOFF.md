# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — finish reorder, then the 40-case router evaluation.
- **Current:** Reads proven live (price/stock, addresses, history, tracking, cancel, payments, delivery quote, coupons). Address switch proven live; delete guarded. Basket clear/remove/quantity preview, confirm and verify, proven against fixtures only. A Python guard asks "set total or add more" when an add names an item already in the basket.
- **Passing Tests:** 57 offline tests pass; `ruff` clean. DB-backed and Gemini suites not run.
- **Next Action:** Reorder from past orders (read-only proof if the account has none), then write the 40-case router evaluation and run it on Groq. No checkout, no order.
- **Source of Truth:** `STATUS.md`
