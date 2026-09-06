# AGENTS.md — GROCER Project Rules

> Read this file before coding. It is the operational instruction set for Antigravity/Gemini and other repository agents.
> Product authority: `GROCER_V2_MASTER_SPEC.md`
> Updated: 2026-09-06

## 1. PROJECT IDENTITY — LOCKED

**Name:** GROCER

**What it is:** the existing WhatsApp consumer grocery replenishment assistant extended with intent-preserving commerce behavior.

**Core thesis:** preserve the user's intended shopping outcome even when live commerce state changes.

**Commerce foundation:** `CommercePort` with `MockCommerceAdapter` and `SwiggyMCPAdapter`.

**Companion repository:** `https://github.com/kwakhare5/Dark-store-operator`

### Critical anti-drift rule

> **GROCER is not a new dark-store project, generic shopping chatbot, or separate Intent product. Intent is an extension of the existing GROCER WhatsApp agent.**

## 2. TARGET FLOW

```text
WhatsApp
  ↓
Conversation Agent
  ↓
Intent Parser
  ↓
Intent Contract
  ↓
Policy / Memory
  ↓
Customer Commerce Service
  ↓
CommercePort
  ↓
Swiggy MCP / Mock
  ↓
Live Commerce State
  ↓
Intent Verifier
  ├── PASS → approval → checkout
  └── FAIL → Recovery Engine → verify again / ask user
```

## 3. NEVER BUILD THESE INSIDE GROCER

- dark-store operator dashboards;
- store inventory optimization;
- transfer/reorder/discount/hold workflows;
- warehouse management;
- supplier operations;
- internal fleet/logistics optimization;
- operations cockpit/maps;
- a generic cross-marketplace shopping assistant;
- competitor price intelligence;
- autonomous refunds that are not supported by the current provider contract;
- autonomous checkout without explicit user confirmation;
- a standalone evaluation platform;
- a second commerce abstraction beside `CommercePort`.

When a task sounds like one of these, stop and compare it with `GROCER_V2_MASTER_SPEC.md` before writing code.

## 4. INTENT RULES

Intent is represented explicitly. Do not leave critical intent only inside an LLM prompt.

Precedence:

```text
current explicit request
    > current session choice
    > stored soft preference
    > agent default
```

Hard constraints are non-negotiable unless the user explicitly changes them.

Soft preferences influence ranking and may yield when permitted.

## 5. AUTONOMY RULES

```text
safe + deterministic + policy-authorized → auto-act
meaningful ambiguity → ask user
financially consequential action → explicit confirmation
```

Checkout must be server-side gated.

## 6. LLM RULE

### LLM/model may

- interpret language;
- extract intent candidates;
- resolve conversational references;
- propose recovery/substitution candidates;
- decide when clarification is useful;
- generate user-facing explanations.

### Deterministic code must

- enforce hard constraints;
- calculate prices/totals;
- verify cart state;
- enforce checkout authorization;
- classify/normalize errors;
- enforce retry policy;
- validate recovery actions;
- maintain authoritative state;
- verify outcomes.

**LLM interprets and proposes. Deterministic code enforces and verifies.**

## 7. RECOVERY LOOP

```text
observe failure
→ classify
→ check policy
→ generate candidates
→ filter hard constraints
→ rank
→ auto-apply OR ask
→ verify again
→ recover / block / complete
```

Recovery must be bounded. Never create infinite loops.

## 8. FIRST MILESTONE

Before broad feature work:

1. clean/remove old dark-store residue from the consumer repository;
2. remove frontend fake operational inventory mutation from consumer checkout;
3. verify the customer commerce path remains intact;
4. retain `CommercePort` and checkout guard;
5. implement `IntentContract`;
6. implement deterministic `IntentVerifier`;
7. implement one polished recovery scenario;
8. then expand recovery and evaluation.

## 9. FLAGSHIP SCENARIO

User:

> “get my weekly groceries under ₹2,000, vegetarian, use my usual brands.”

System should:

1. parse intent;
2. apply soft memory;
3. build basket;
4. verify basket;
5. inject a controlled commerce problem;
6. detect intent drift;
7. recover if safe;
8. ask only when necessary;
9. verify again;
10. request explicit checkout confirmation;
11. checkout through the commerce boundary;
12. report the verified result.

## 10. SWIGGY MCP RULES

Before changing Swiggy integration, read the current Builders Club documentation:

- `https://mcp.swiggy.com/builders/llms.txt`
- `https://mcp.swiggy.com/builders/llms-full.txt`

Use current Instamart reference and error documentation. Do not invent tool schemas or retry behavior.

Keep Swiggy-specific code inside `backend/integrations/commerce/swiggy_adapter.py` or an equally isolated adapter boundary.

## 11. UI RULES

The existing WhatsApp/iPhone customer experience remains the interface foundation.

Improve behavior, not product identity.

Use compact states:

```text
READY
RECOVERING
NEEDS DECISION
AWAITING CONFIRMATION
ORDERED
FAILED
```

No operations dashboard should be reintroduced into GROCER.

## 12. SAFETY INVARIANTS

- No checkout without explicit confirmation.
- No credentials in source, logs, or frontend.
- No LLM-only enforcement for critical rules.
- No unverified success claims.
- No blind retry of consequential operations.
- No silent hard-constraint violation.
- Current explicit request always overrides stored memory.

## 13. QUALITY GATE

Run relevant checks after changes:

```bash
npm run lint
npm run build
pytest backend/tests
```

Never claim green verification without actually running the relevant command.

## 14. DECISION RULE FOR NEW IDEAS

Before implementing a proposed feature, ask:

> Does this directly improve the user's ability to complete a grocery task while preserving the stated intent across changing commerce state?

If the answer is no, it does not belong in GROCER v2 unless the master spec is deliberately changed first.

## 15. SESSION RESUME

**Last completed:** Flagship Golden Flow & Cleanroom Intent Refactor (2026-09-06)

**Status:** ✅ Complete. End-to-end verified proof of the flagship shopping task:
`"get my weekly groceries under ₹2,000, vegetarian, use my usual brands."`
Full loop: Parse → IntentContract → PolicyEngine → CommercePort Cart Build → Deterministic OOS Fault Injection → Drift Detection (`ITEM_UNAVAILABLE`) → LoopingRecoveryEngine Auto-Recovery (2x Amul 500ml, Delta ₹0) → Re-verification → AWAITING_CONFIRMATION → Explicit Human Confirmation Gate → Consequential Checkout → ORDERED.
Build 100% green: 132/132 backend tests passing, `npm run lint` 0 errors, `npm run build` 100% clean.

**What was done:**
- **Task 1 — Choice Integrity & Session Hardening (`backend/intent/orchestrator.py`, `session.py`):**
  - Added `removes_spin_id` and `intended_quantity` to `PendingClarification`.
  - Hardened `handle_choice` to validate candidate against pending options, preserve all unrelated basket items, calculate pack size multiples, re-verify with `IntentVerifier`, and safely block violations.
  - Hardened `IntentParser` with negative lookaheads in `_extract_items` to prevent conjunction/preposition greediness, and added `_is_incremental_add` for multi-turn cart additions.
  - 24/24 tests passing in `backend/tests/test_orchestrator.py`.
- **Task 2 — Deterministic Failure Simulation (`backend/integrations/commerce/mock_adapter.py`, `models.py`):**
  - Added `is_available: bool = True` to `CartItem`.
  - Added deterministic failure hooks to `MockCommerceAdapter`: `inject_out_of_stock`, `inject_price_change`, `inject_stale_cart`, `inject_transient_error`, and `reset_injections`.
  - Instance-isolated catalog deepcopy to prevent cross-test pollution.
- **Tasks 4 & 5 — Looping Recovery Engine (`backend/intent/recovery.py`, `recovery_loop.py`):**
  - Created `LoopingRecoveryEngine` implementing the exact 10-step bounded recovery sequence (Spec §12).
  - Infinite retry loop signature detection and bounded step counter (`max_attempts`).
  - Separated mutating actions from non-mutating (`retry`, `refresh_cart`) to perform controlled live re-fetch from `CommercePort`.
  - Created `backend/tests/test_recovery_loop.py` (4/4 passing tests).
- **Task 6 — Intent Verifier Hardening (`backend/intent/verifier.py`):**
  - Added `_check_item_availability` checking `getattr(item, "is_available", True) is False` to trigger `ViolationCode.ITEM_UNAVAILABLE` (is_hard=True).
  - Sanitized dietary token matching with regex word boundaries to prevent punctuation trapping non-veg words.
- **Task 3 — Flagship Golden OOS Recovery Scenario (`backend/tests/test_golden_oos_recovery.py`):**
  - Proves the complete flagship scenario end-to-end: parse → contract → basket build → OOS fault injection on Amul 1L milk → drift detection → `LoopingRecoveryEngine` auto-recovers to 2x Amul 500ml → preserves bread & tomatoes → verification passes → explicit confirmation required → confirmed checkout to `ORDERED`. Both tests passing.
- **Tasks 7 & 9 — Intent Commerce Workbench UI (`components/customer/IntentCommerceWorkbench.tsx`, `app/page.tsx`, `lib/apiClient.ts`):**
  - Added canonical Intent API methods to `grocerApi`: `sendIntentChat`, `sendIntentChoice`, `confirmIntentOrder`, `getIntentSession`, and `resetIntentSession`.
  - Built `IntentCommerceWorkbench` component with WhatsApp phone simulation, live verified basket card, budget tracking progress bar, interactive substitution cards for `NEEDS_DECISION`, and consequential checkout gate (`explicit_confirmation` required).
  - Rendered `IntentCommerceWorkbench` as the primary view in `app/page.tsx`.
- **Task 11 — Documentation:**
  - Created `docs/GOLDEN_FLOW.md` detailing the product thesis, 10-step sequence, architecture diagram, and automated verification matrix.

**Quality Gates:**
- `pytest backend/tests -q`: 132/132 tests passed (100% green).
- `npm run lint`: 0 errors, 0 warnings.
- `npm run build`: Compiled successfully in Next.js 16 (Turbopack).
- Branch: `refactor/intent-cleanroom` (preserved, zero modifications to `main`).



