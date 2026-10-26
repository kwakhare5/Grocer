# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — make the concierge answer the whole Instamart surface with live data, not just shopping searches.
- **Current:** `grocer-v1` at c8d31c9 deployed. Live refresh proven (expires 2026-11-25). Live reads work: 3 addresses, search, 11-item cart (₹1,751), 10 payment methods, 0 orders.
- **Docs:** `STATUS.md` is the only current status. `TASKS.md` deleted. Cardboard web style moved to `docs/design-reference.md`; `DESIGN.md` is now the WhatsApp UX spec.
- **Passing Tests:** 38 offline tests pass; Ruff clean. DB-backed and Gemini suites not run.
- **Next Action:** Gate 2 in a new chat. Add real intents for price, stock, store, saved addresses, order history, tracking, reorder and disambiguation, grounded in live Swiggy calls. No checkout, no order, no push without typed approval.
