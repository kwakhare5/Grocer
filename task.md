# Task Tracker: Architectural Overhaul & Radical Codebase Prune

## Full WhatsApp Journey Recovery (Approved 2026-10-03)

Verification policy (confirmed 2026-10-03): only full-path E2E tests count as release proof. The old unit suite is being retired after its customer and security behaviors are carried into E2E coverage. Docker PostgreSQL is local test isolation; production Supabase is not the test database.

Current local proof (2026-10-03): signed WhatsApp webhook → PostgreSQL inbox → agent → outbox → recorded Meta delivery: **27 passed**, JUnit `artifacts/whatsapp_e2e.xml`, exit 0. A CLI-only real-model/mock-commerce replay now reports missing pizza base and other unavailable extras as a partial basket, and keeps ingredient-only ₹1,000 separate from extras and fees. ESLint, TypeScript, and Next.js build pass. Meta accepted an approved `hello_world` test template to the authorized recipient; a customer reply and deployed-path verification are still pending. Live Swiggy MCP remains unauthenticated locally. None of this proves the complete release gate.

- [ ] Capture a red, repeatable signed-webhook → PostgreSQL inbox → worker → agent → outbox → synthetic Meta-delivery replay of the reported failures, with a test report and exit code.
- [ ] Make customer shopping intent durable across address selection, model/provider failures, retry, and worker restart; account for every requested item, including budget-blocked items.
- [ ] Verify provider cart, complete payable total, selected address, and payment choice at customer approval; reconcile unknown commerce outcomes and preserve truthful order results.
- [ ] Secure the simulator and make it exercise the full WhatsApp path; verify real customer-scoped Swiggy MCP non-order calls without chargeable checkout.
- [ ] Implement consent-based one-customer household replenishment with chosen reminder time/frequency, estimated timing, corrections, opt-out/delete, and durable WhatsApp delivery.
- [ ] Verify grocery-only symptom suggestions, customer support escalation, all failure and restart paths, and current Swiggy/Meta policy gates.
- [ ] Resolve the existing test/build baseline, review proven dead-code candidates, prune surgically, and rerun full journey checks.
- [ ] Inventory exposed credentials and prepare controlled rotation, including a data-key re-encryption migration; obtain separate go-ahead for production changes.

The detailed evidence and acceptance gates are in `docs/SYSTEM_AUDIT_AND_RECOVERY_PLAN.md`. The older tracker below is historical work and its checked boxes are not release proof.

## Active Overhaul Plan (Approved 2026-10-02)

- [x] **Phase 1: Radical Codebase Pruning & Engine Streamlining (Ponytail / YAGNI)** <!-- id: 101 -->
  - [x] Delete obsolete root planning files (`Grocer-BuilderClub-Plan.md`, `Grocer-Complete-Plan.md`) <!-- id: 102 -->
  - [x] Add atomic 1-turn `quick_add_items` tool in `backend/agent/tools.py` & `engine.py` (66% roundtrip reduction) <!-- id: 103 -->
  - [x] Replace brittle hesitation set matching with regex `is_hesitation()` in `guards.py` <!-- id: 104 -->
  - [x] Streamline `backend/agent/prompts.py` to Ultra-Crisp Transactional Persona (down to ~350 tokens) <!-- id: 105 -->
  - [x] Fix receipt duplication and guarantee out-of-stock item explanation preservation in `engine.py` <!-- id: 106 -->

- [x] **Phase 2: Simulator Transparency & Swiggy OAuth Connect** <!-- id: 107 -->
  - [x] Add dynamic visual status badge in `app/simulator/page.tsx` (🟢 LIVE SWIGGY MCP vs 🟡 LOCAL MOCK SIMULATOR) <!-- id: 108 -->
  - [x] Add 1-click "Connect Real Swiggy (OTP)" action button linking to `/api/auth/swiggy/login` <!-- id: 109 -->

- [ ] **Phase 3: Adversarial Verification Loop to 100% Pass Rate** <!-- id: 110 -->
  - [x] Isolate test state with per-test `clear_cart()` in `scripts/eval_adversarial_matrix.py` <!-- id: 111 -->
  - [x] Expand matrix from 10 to 15 real-world human scenarios (pack sizes, chai kits, mid-order edits, item removal) <!-- id: 112 -->
  - [ ] Execute 15-scenario adversarial run with isolated pacing to verify 100% pass rate <!-- id: 113 -->

- [ ] **Phase 4: Full System Verification & Live Auth** <!-- id: 114 -->
  - [x] Verified single-turn grocery add (2x Milk + 1x Bread in 1.2s with single clean receipt) <!-- id: 115 -->
  - [x] Verified out-of-stock preservation (Vicks added + Pencils unavailable note preserved with exit code 0) <!-- id: 116 -->
  - [ ] Connect real Swiggy account with phone number OTP to replace expired JWT <!-- id: 117 -->
