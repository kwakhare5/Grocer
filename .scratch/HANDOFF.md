# Grocer v1 — Session Handoff

- **Goal:** Swiggy Instamart on WhatsApp. Scope is full tool coverage, not the PRD example journeys. No live order during the build; Karan places the first real order after handoff.
- **Current:** Phases 0-5 done. Account lifecycle works: default-address grounding, switch that clears and rebuilds, delete guard on the real path, typed-text address add, signed OAuth links, park/replay after login. The production WhatsApp mock branch is gone; scripted tests carry a `scripted` marker.
- **Passing Tests:** `verify.ps1 -Db` exit 0 on 2026-10-27: schema check, `ruff` clean, 99 offline, 45 DB on `grocer_test`, 166 collected, Next build. Both databases at migration 004.
- **Blocked on Karan:** Nothing. Live address add/delete on the one throwaway address is optional proof.
- **Next Action:** Phase 6 — DPDP scrub and delete cascade, RLS or service-only access, log redaction, CHECK constraints and `updated_at` triggers.
- **Source of Truth:** `STATUS.md`, plan in `TASKS.md`.
