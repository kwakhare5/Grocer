# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — finish reorder, then prove the router with real AI calls.
- **Current:** Reorder previews a past order or usual items with live products and prices, rebuilds the cart only on a tap, verifies read-after-write, and reverts on mismatch. Router prompt now separates reorder, ETA, bare lists, vague deletes and checkout. Live Groq eval: 39/40 on two full runs, 0 unsafe writes, different miss each time; both misses pass on rerun after a prompt rule.
- **Passing Tests:** 47 targeted offline tests (router, basket, reorder, catalog) and `ruff` clean on changed files. Full suite not green: live-loop tests write junk users to the live Supabase DB and fail with `auth_required`.
- **Next Action:** Build an isolated test DB (P1 #15, now confirmed with ~350 junk users), then typed-text address add. Run the eval 3 times for per-case consistency. No checkout, no order.
- **Source of Truth:** `STATUS.md`
