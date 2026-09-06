# Tracer Bullets: Cleanroom Intent-Preserving Commerce & Golden Flow

- [x] 1. Choice Integrity: Harden `handle_choice` in `backend/intent/orchestrator.py` and `backend/intent/session.py` <!-- id: 1 -->
- [x] 2. Failure Injection: Add deterministic fault injection to `backend/integrations/commerce/mock_adapter.py` and `models.py` <!-- id: 2 -->
- [x] 3. Recovery Hardening: Fix transient retry bug in `recovery.py` and create `backend/intent/recovery_loop.py` (`LoopingRecoveryEngine`) <!-- id: 3 -->
- [x] 4. Verifier Hardening: Audit `backend/intent/verifier.py` for item availability and dietary token sanitization <!-- id: 4 -->
- [x] 5. Golden Scenario: Implement flagship end-to-end OOS recovery test in `backend/tests/test_golden_oos_recovery.py` <!-- id: 5 -->
- [x] 6. Checkout Safety: Add regression tests in `backend/tests/test_orchestrator.py` enforcing checkout confirmation invariants <!-- id: 6 -->
- [x] 7. Frontend Workbench: Implement `components/customer/IntentCommerceWorkbench.tsx`, update `lib/apiClient.ts` and `app/page.tsx`, fix lint errors <!-- id: 7 -->
- [x] 8. Full Validation: Run `pytest -q`, `npm run lint`, and `npm run build` <!-- id: 8 -->
- [x] 9. Documentation: Document golden recovery flow in `docs/GOLDEN_FLOW.md` and update `AGENTS.md` / `JOURNAL.md` <!-- id: 9 -->

---

# GROCER — Active Task Board

> **Source of truth:** `GROCER_V2_MASTER_SPEC.md`
>
> GROCER is the existing WhatsApp-first consumer grocery replenishment assistant extended with intent-preserving commerce. The old dark-store operator system is a separate project and must not return to this repository.

## P0 — Cleanroom boundary
- [x] Create isolated cleanroom branch.
- [x] Remove legacy operations API registration from the application entrypoint.
- [x] Remove legacy operations agent API.
- [x] Remove legacy forecasting, risk, decision, and simulation service code identified as consumer-irrelevant.
- [x] Replace `CustomerService` with a commerce-only application boundary; remove simulated inventory/order mutation.
- [x] Remove duplicate implementation-plan file.
- [x] Ignore generated Graphify output.
- [x] Add cleanroom completion criteria and quarantine legacy architecture context.
- [ ] Remove obsolete operation ORM models/enums after dependency audit.
- [ ] Remove remaining obsolete frontend operation clients/types.
- [ ] Remove generated `graphify-out/` tracked artifacts.
- [ ] Archive/remove stale walkthrough and audit documents.
- [ ] Run repository-wide import/reference audit and repair any breakage.

## P1 — Intent correctness
- [ ] Audit and harden `IntentContract` semantics.
- [ ] Harden parser normalization and ambiguity handling.
- [ ] Verify explicit-current-request > stored-preference precedence.
- [ ] Strengthen product identity matching.
- [ ] Add commerce snapshot/version semantics.
- [ ] Make consequential actions require current-state verification.

## P2 — Golden vertical slice
- [ ] User request → intent contract → cart.
- [ ] Capture commerce snapshot.
- [ ] Inject cart drift/failure.
- [ ] Detect intent violation.
- [ ] Recover safely.
- [ ] Re-verify.
- [ ] Ask only when ambiguity remains.
- [ ] Explicit checkout confirmation.
- [ ] Truthful success/failure reporting.

## P3 — Reliability + evaluation
- [ ] Deterministic failure injection at the commerce seam.
- [ ] Adversarial regression suite.
- [ ] Reliability metrics.
- [ ] Live Swiggy MCP hardening.

## P4 — Experience
- [ ] Make the WhatsApp demo UI backend-driven rather than commerce-script-driven.
- [ ] Preserve visual language; make failure/recovery/approval states truthful.
- [ ] Polish flagship failure-and-recovery demo.

## Non-negotiables
- No dark-store / warehouse / supplier / inventory-operations subsystem in GROCER.
- No second commerce abstraction competing with `CommercePort`.
- No frontend ownership of commerce truth.
- LLMs interpret and propose; deterministic backend logic enforces hard constraints and verifies state.
- Checkout always requires explicit user confirmation.
- Current explicit user instructions override stored preferences.
- Never silently substitute across incompatible constraints.
- Never claim success when the underlying action is failed or unknown.
