# Active Tracer Bullets: Developer Live-Debug View

> Purpose: Understand live WhatsApp tests without modifying core intent/commerce behavior

- [x] Create read-only sanitized debug endpoint (`GET /api/debug/latest`, `GET /api/debug/sessions`) <!-- id: live-debug-1 -->
- [x] Add unit test verifying telemetry structure, zero credential leaks, phone masking, and PII safety <!-- id: live-debug-2 -->
- [x] Build `LiveDebugInspector.tsx` displaying all 13 dimensions with developer-focused styling <!-- id: live-debug-3 -->
- [x] Integrate quick-toggle drawer in `AppGlobalHeader.tsx` on main page <!-- id: live-debug-4 -->
- [x] Add dedicated standalone route `app/debug/page.tsx` for side-by-side WhatsApp phone testing <!-- id: live-debug-5 -->
- [x] Run quality gates: pytest, npm run lint, npm run build <!-- id: live-debug-6 -->
- [x] Verify live debug telemetry across all dimensions and confirm goal completion <!-- id: live-debug-7 -->

---

# Active Tracer Bullets: Live Swiggy Integration Hardening

> Branch: `live/swiggy-integration-hardening`
> Plan: `docs/LIVE_SWIGGY_INTEGRATION_HARDENING_PLAN.md`

- [x] Add sanitized real-response replay fixtures and first failing regressions. <!-- id: live-swiggy-1 -->
- [x] Preserve bare quantity as catalog-dependent and introduce canonical resolved meaning. <!-- id: live-swiggy-2 -->
- [x] Use resolved meaning for selection, cart verification, recovery, and user communication. <!-- id: live-swiggy-3 -->
- [x] Enforce exact current MCP arguments and provider tri-state semantics. <!-- id: live-swiggy-4 -->
- [x] Canonically reconcile material mutations and classify accepted shortfalls. <!-- id: live-swiggy-5 -->
- [x] Recover provider limits using targeted bounded catalog search. <!-- id: live-swiggy-6 -->
- [x] Add safe interpretation tracing and generalized semantic test coverage. <!-- id: live-swiggy-7 -->
- [x] Run backend, evaluation, frontend, and diff quality gates. <!-- id: live-swiggy-8 -->
- [ ] Update session evidence and handoff documentation; do not merge main. <!-- id: live-swiggy-9 -->

---

# Active Tracer Bullets: Independent Merge-Blocker Remediation

> Branch: `audit/codex-deep-review`
> Approved plan: `docs/audit/TARGETED_REMEDIATION_PLAN.md`

- [x] Verify all nine reported findings against current code and official provider docs. <!-- id: remediation-1 -->
- [x] Add red regressions and fix general COUNT versus PACK_COUNT semantics. <!-- id: remediation-2 -->
- [x] Add red regressions and fail closed for unverifiable hard dietary constraints. <!-- id: remediation-3 -->
- [x] Classify the reported Instamart ₹1000 cap as current-provider-doc changed/not applicable. <!-- id: remediation-4 -->
- [x] Require explicit saved-address selection for one or many returned addresses. <!-- id: remediation-5 -->
- [x] Preserve auth, revoked-session, timeout/network, and genuinely empty provider outcomes. <!-- id: remediation-6 -->
- [x] Add deterministic live payment-option selection and confirmation invalidation. <!-- id: remediation-7 -->
- [x] Finalize headless UPI once at the polling cap and map the result truthfully. <!-- id: remediation-8 -->
- [x] Prefer conversational rich tracking with trustworthy coordinates and use an explicit ETA fallback otherwise. <!-- id: remediation-9 -->
- [x] Make required CommercePort lifecycle capabilities explicit and align tracking signatures. <!-- id: remediation-10 -->
- [x] Update only materially changed audit/state evidence. <!-- id: remediation-11 -->
- [x] Run focused regressions, full Python tests, adversarial evaluation, frontend lint/build, and `git diff --check`. <!-- id: remediation-12 -->
- [x] Review the cumulative remediation diff for regressions. <!-- id: remediation-13 -->
- [x] Commit logical slices and push `audit/codex-deep-review`; do not merge `main`. <!-- id: remediation-14 -->

---

# Active Tracer Bullets: Codex Deep Audit and Reliability Hardening

> Branch: `audit/codex-deep-review`
> Plan: `docs/audit/CODEX_DEEP_AUDIT_MISSION.md`
> Findings: `docs/audit/CODEX_AUDIT_REPORT.md`
> Tests: `docs/audit/ADVERSARIAL_TEST_MATRIX.md`

- [x] Recover branch, worktree, commit, artifact, and baseline test state. <!-- id: codex-1 -->
- [x] Inspect repository and official current Swiggy commerce documentation. <!-- id: codex-2 -->
- [x] Record initial mission, audit report, and adversarial matrix. <!-- id: codex-3 -->
- [x] Implement shared physical quantity and product identity semantics test-first. <!-- id: codex-4 -->
- [x] Bind approval to basket/address/payment/intent and serialize checkout. <!-- id: codex-5 -->
- [x] Complete truthful payment, multi-order, order, and tracking models/flows. <!-- id: codex-6 -->
- [x] Remove live Swiggy fabricated fallbacks and unsafe timeout reconciliation. <!-- id: codex-7 -->
- [x] Unify provider authentication and prevent cross-user provider state. <!-- id: codex-8 -->
- [x] Harden WhatsApp/API session ownership, signatures, stale actions, privacy, and failures. <!-- id: codex-9 -->
- [x] Remove proven dead/duplicate dependencies, routes, code, assets, and legacy docs. <!-- id: codex-10 -->
- [x] Expand and run high-value adversarial/evaluation coverage. <!-- id: codex-11 -->
- [x] Synchronize active architecture/state/setup documentation. <!-- id: codex-12 -->
- [x] Run full Python, lint, build, static/reference, and no-real-order gates. <!-- id: codex-13 -->
- [x] Commit final verification slices and complete post-fix standards/spec review. <!-- id: codex-14 -->

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
- [x] 9. Documentation: Document golden recovery flow (now archived at `docs/archive/GOLDEN_FLOW.md`) and update `AGENTS.md` / `JOURNAL.md` <!-- id: 9 -->

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

## P5 — Historical live WhatsApp/Swiggy milestone
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

## DEFERRED MILESTONE — NOT STARTED ON AUDIT BRANCH

### Objective: Persistent Cloud Deployment & Production Webhook Stability
- [ ] Containerize FastAPI backend with production Docker configuration.
- [ ] Deploy backend to persistent public cloud infrastructure (e.g. Fly.io, Railway, or AWS) to eliminate local development tunnels.
- [ ] Exchange 24-hour Meta developer access token for a permanent System User Token in Meta Business Suite.
- [ ] Connect Redis/Postgres state storage for `OrchestratorSessionStore` and `SwiggyTokenVault` to ensure session continuity across service restarts.
- [ ] Live physical rider verification for `track_order` tool with real dispatch on the road.

