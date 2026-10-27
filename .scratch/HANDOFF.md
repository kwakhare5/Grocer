# Grocer v1 — Session Handoff

- **Goal:** Swiggy Instamart on WhatsApp. Scope is full tool coverage, not the PRD example journeys. No live order during the build; Karan places the first real order after handoff.
- **Current:** Phases 0-4 done. Live smoke on 2026-10-27 used the real token/MCP: reads, a verified cart add/restore, 10/10 Groq routes, and a checkout that stops before Swiggy. Tracking, store info, "milk" choices and the pollers are now real.
- **Passing Tests:** `verify.ps1 -Db` exit 0 on 2026-10-27: schema check, `ruff` clean, 100 offline, 34 DB on `grocer_test`, 156 collected, Next build. App database and `grocer_test` both at migration 004.
- **Blocked on Karan:** Nothing. Migration 004 applied and committed.
- **Next Action:** Phase 5 — default-address grounding, switch clears and rebuilds the basket, delete guard, typed-text address add, OAuth binding, park/replay wired (open P0 #6).
- **Source of Truth:** `STATUS.md`, plan in `TASKS.md`.
