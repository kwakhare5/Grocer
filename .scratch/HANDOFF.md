# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — complete the read capabilities, then account and basket writes.
- **Current:** Router wired into the webhook (`e519cdd`). Read capabilities answer from live Swiggy: price/stock, addresses, order history, active-order status, cancel help, payment options. Price question left the cart unchanged (11 items, ₹1,763 before and after).
- **Passing Tests:** 49 offline tests pass; `ruff` clean. DB-backed and Gemini suites not run.
- **Next Action:** Add store info and coupons, then address add/switch/delete, then basket change/clear/reorder. Text checkout stays blocked; money moves only by physical button.
- **Source of Truth:** `STATUS.md`
