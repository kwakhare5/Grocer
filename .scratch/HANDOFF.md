# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — finish basket capabilities, then money stays button-only.
- **Current:** Router wired. Reads proven live: price/stock, addresses, history, active order, cancel help, payment options, delivery quote, coupons. Address switch proven live with a basket warning; delete is guarded and previewed but never executed on a real address.
- **Passing Tests:** 49 offline tests pass; `ruff` clean. DB-backed and Gemini suites not run.
- **Next Action:** Basket change and clear (with confirmation), then reorder. Then the 40-case router evaluation. No checkout, no order.
- **Source of Truth:** `STATUS.md`
