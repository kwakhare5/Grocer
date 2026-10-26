# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — run every test on the one pre-launch Supabase project without leaving junk.
- **Current:** Tests use the existing database through `TEST_DATABASE_URL` (in `.env`, not committed). Each run snapshots current user IDs and deletes any user created during the run, so the count is stable (364 before and after a full run). Vague multi-product requests now ask instead of silently picking the first item. Reorder is built; live Groq routing eval is 39/40, 0 unsafe writes.
- **Passing Tests:** 136 passed, 0 skipped, 0 failed; `ruff` clean.
- **Next Action:** Karan gives typed approval to delete ~363 junk users from earlier test runs, then typed-text address add. No checkout, no order.
- **Source of Truth:** `STATUS.md`
