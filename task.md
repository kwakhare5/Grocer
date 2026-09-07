# Active Tracer Bullets: Codex Deep Audit and Reliability Hardening

> Branch: `audit/codex-deep-review`
> Plan: `docs/audit/CODEX_DEEP_AUDIT_MISSION.md`
> Findings: `docs/audit/CODEX_AUDIT_REPORT.md`
> Tests: `docs/audit/ADVERSARIAL_TEST_MATRIX.md`

- [x] Recover branch, worktree, commit, artifact, and baseline test state. <!-- id: codex-1 -->
- [x] Inspect repository and official current Swiggy commerce documentation. <!-- id: codex-2 -->
- [x] Record initial mission, audit report, and adversarial matrix. <!-- id: codex-3 -->
- [ ] Implement shared physical quantity and product identity semantics test-first. <!-- id: codex-4 -->
- [ ] Bind approval to basket/address/payment/intent and serialize checkout. <!-- id: codex-5 -->
- [ ] Complete truthful payment, multi-order, order, and tracking models/flows. <!-- id: codex-6 -->
- [ ] Remove live Swiggy fabricated fallbacks and unsafe timeout reconciliation. <!-- id: codex-7 -->
- [ ] Unify provider authentication and prevent cross-user provider state. <!-- id: codex-8 -->
- [ ] Harden WhatsApp/API session ownership, signatures, stale actions, privacy, and failures. <!-- id: codex-9 -->
- [ ] Remove proven dead/duplicate dependencies, routes, code, assets, and legacy docs. <!-- id: codex-10 -->
- [ ] Expand and run high-value adversarial/evaluation coverage. <!-- id: codex-11 -->
- [ ] Synchronize active architecture/state/setup documentation. <!-- id: codex-12 -->
- [ ] Run full Python, lint, build, static/reference, and no-real-order gates. <!-- id: codex-13 -->
- [ ] Commit logical slices and run independent standards/spec self-review. <!-- id: codex-14 -->

---

# Historical Tracer Bullets: Cleanroom Intent-Preserving Commerce & Golden Flow

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
- [x] Remove obsolete operation ORM models/enums after dependency audit.
- [x] Remove remaining obsolete frontend operation clients/types.
- [x] Remove generated `graphify-out/` tracked artifacts.
- [x] Archive/remove stale walkthrough and audit documents.
- [x] Run repository-wide import/reference audit and repair any breakage.

## P1 — Intent correctness
- [x] Audit and harden `IntentContract` semantics.
- [x] Harden parser normalization and ambiguity handling.
- [x] Verify explicit-current-request > stored-preference precedence.
- [x] Strengthen product identity matching.
- [x] Add commerce snapshot/version semantics.
- [x] Make consequential actions require current-state verification.

## P2 — Golden vertical slice
- [x] User request → intent contract → cart.
- [x] Capture commerce snapshot.
- [x] Inject cart drift/failure.
- [x] Detect intent violation.
- [x] Recover safely.
- [x] Re-verify.
- [x] Ask only when ambiguity remains.
- [x] Explicit checkout confirmation.
- [x] Truthful success/failure reporting.

## P3 — Reliability + evaluation
- [x] Deterministic failure injection at the commerce seam.
- [x] Adversarial regression suite.
- [x] Reliability metrics.
- [x] Live Swiggy MCP hardening.

## P4 — Experience
- [x] Make the WhatsApp demo UI backend-driven rather than commerce-script-driven.
- [x] Preserve visual language; make failure/recovery/approval states truthful.
- [x] Polish flagship failure-and-recovery demo.

## P5 — Live WhatsApp Cloud API & Swiggy MCP Integration [COMPLETED]
- [x] Official Meta WhatsApp Cloud API adapter (`backend/channels/whatsapp.py`).
- [x] Webhook challenge verification (`hub.challenge`) and HMAC-SHA256 signature checking.
- [x] In-memory message deduplication and replay protection.
- [x] Telephone-number-to-customer identity and session continuity (`wa-{sender_id}`).
- [x] Live Swiggy MCP Instamart production integration (`https://mcp.swiggy.com/im`).
- [x] Live address resolution, catalog search, and cart mutation.
- [x] Multi-turn out-of-stock recovery rendering interactive WhatsApp lists (`[ ☰ Select Alternative ]`).
- [x] Consequential basket confirmation rendering interactive quick reply buttons (`[ Confirm Order ]`).
- [x] End-to-end verified real shopping order placement (`OD-68355847`).

## Non-negotiables
- No dark-store / warehouse / supplier / inventory-operations subsystem in GROCER.
- No second commerce abstraction competing with `CommercePort`.
- No frontend ownership of commerce truth.
- LLMs interpret and propose; deterministic backend logic enforces hard constraints and verifies state.
- Checkout always requires explicit user confirmation.
- Current explicit user instructions override stored preferences.
- Never silently substitute across incompatible constraints.
- Never claim success when the underlying action is failed or unknown.

---

## NEXT TASK — NOT STARTED

### Objective: Persistent Cloud Deployment & Production Webhook Stability
- [ ] Containerize FastAPI backend with production Docker configuration.
- [ ] Deploy backend to persistent public cloud infrastructure (e.g. Fly.io, Railway, or AWS) to eliminate local development tunnels.
- [ ] Exchange 24-hour Meta developer access token for a permanent System User Token in Meta Business Suite.
- [ ] Connect Redis/Postgres state storage for `OrchestratorSessionStore` and `SwiggyTokenVault` to ensure session continuity across service restarts.
- [ ] Live physical rider verification for `track_order` tool with real dispatch on the road.

