# GROCER — Active Task Board

> **Source of truth:** `GROCER_V2_MASTER_SPEC.md`
>
> GROCER is the existing WhatsApp-first consumer grocery replenishment assistant extended with intent-preserving commerce. The old dark-store operator system is a separate project and must not return to this repository.

## Current milestone: Cleanroom + Intent Hardening

### P0 — Consumer boundary cleanup
- [ ] Remove obsolete dark-store API routes and execution services.
- [ ] Remove obsolete dark-store SQLAlchemy models and enums.
- [ ] Remove customer-service paths that mutate simulated store inventory or fabricate local delivered orders.
- [ ] Remove frontend operation types, store metadata, and unused operation clients.
- [ ] Eliminate duplicate Swiggy commerce execution paths where backend `CommercePort` should be authoritative.
- [ ] Remove generated `graphify-out/` artifacts and ignore them going forward.
- [ ] Remove duplicate lowercase `implementation_plan.md`; keep `IMPLEMENTATION_PLAN.md` as canonical.
- [ ] Archive or clearly mark stale historical documents so coding agents cannot mistake them for current architecture.

### P1 — Intent correctness audit
- [ ] Review `IntentContract` schema and precedence semantics.
- [ ] Review parser normalization and ambiguity handling.
- [ ] Review preference-memory precedence: explicit current request > constraints > stored preference > default.
- [ ] Strengthen product identity matching and quantity/pack-size validation.
- [ ] Add commerce snapshot/version semantics so recovery actions cannot run against stale state.
- [ ] Ensure every consequential action is verified against the current commerce state before execution.

### P2 — Golden vertical slice
- [ ] User sends one constrained grocery request.
- [ ] Build an `IntentContract`.
- [ ] Construct the basket through `CommercePort`.
- [ ] Capture a commerce snapshot.
- [ ] Detect a deterministic cart drift/failure.
- [ ] Generate recovery candidates.
- [ ] Apply only policy-compliant recovery.
- [ ] Re-verify the recovered basket against the original intent.
- [ ] Ask the user only when ambiguity remains.
- [ ] Require explicit checkout confirmation.
- [ ] Never report an unsuccessful/unknown action as successful.

### P3 — Reliability + evaluation
- [ ] Add deterministic failure injection at the commerce seam.
- [ ] Add adversarial intent/recovery regression scenarios.
- [ ] Measure intent preservation, hard-constraint satisfaction, recovery success, unsafe action rate, unnecessary clarification, budget deviation, and tool efficiency.
- [ ] Harden live Swiggy MCP error/retry/state handling.

### P4 — Experience
- [ ] Convert the polished WhatsApp demo UI from scripted commerce state to backend-driven state.
- [ ] Preserve the existing visual language while making failures, recovery, ambiguity, approval, and checkout truthful.
- [ ] Build the flagship demo around one polished failure-and-recovery journey.

## Non-negotiables
- No dark-store / warehouse / supplier / inventory-operations subsystem in GROCER.
- No second commerce abstraction competing with `CommercePort`.
- No frontend ownership of commerce truth.
- LLMs interpret and propose; deterministic backend logic enforces hard constraints and verifies state.
- Checkout always requires explicit user confirmation.
- Current explicit user instructions override stored preferences.
- Never silently substitute across incompatible constraints.
- Never claim success when the underlying action is failed or unknown.
