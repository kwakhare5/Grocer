# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — keep the router honest and the tests off production.
- **Current:** Reorder is built (preview, tap, rebuild, verify, revert). Live Groq eval: 39/40 on two runs, 0 unsafe writes, misses vary between runs and pass individually after prompt rules. Tests can no longer touch production: `get_db_pool()` refuses `DATABASE_URL` under pytest, DB tests are marked `db` and skip without `TEST_DATABASE_URL`.
- **Passing Tests:** 113 passed, 23 skipped, 0 failed; `ruff` clean. Skips are the 23 DB tests waiting for a separate test database.
- **Next Action:** Karan creates a free Supabase test project, adds `TEST_DATABASE_URL` to `.env`, and decides whether to delete the ~350 junk users from production. Then typed-text address add. No checkout, no order.
- **Source of Truth:** `STATUS.md`
