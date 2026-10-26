# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — make the concierge answer the full Instamart surface, not just shopping.
- **Current:** Gate 1 + 1.1 committed and deployed (`c8d31c9`). Live refresh proven: forced exchange rotated the pair, new token loaded 3 addresses, expiry now 2026-11-25 17:40 UTC. Migration 003 applied. Live cart reads 11 items / ₹1,751 / one store.
- **Passing Tests:** 38 offline tests pass; Ruff clean. DB-backed and Gemini suites were not run (they write to live Supabase).
- **Next Action:** Gate 2 — price/stock/store, address list, order history, tracking, reorder intents with real live data. Unproven and blocked on an approved paid order: confirm_order, split orders, payment poller.
- **Source of Truth:** `STATUS.md`
