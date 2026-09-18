# AGENTS.md — GROCER Project Rules

> Read this file before coding. It is the operational instruction set for Antigravity/Gemini and other repository agents.
> Product authority: `GROCER_V2_MASTER_SPEC.md`
> Updated: 2026-09-10

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
Customer Commerce Service (GrocerOrchestrator)
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

*(Resolution A: The legacy v1 `CustomerService` was intentionally collapsed into `GrocerOrchestrator` (`backend/intent/orchestrator.py`) as the sole approved v2 application boundary communicating directly with `CommercePort`.)*

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

**Last completed:** Submission Safety, Reviewer Evidence, and Stale-Choice Guard (2026-09-16).

**Next verification gate:** Configure durable encrypted PostgreSQL storage, then re-verify the whitelisted OAuth redirect, Meta test number, Render, Vercel, and real Swiggy review-mode behavior. `ConversationInterpreter` may interpret English text only; `ConversationController` validates each command and delegates to `GrocerOrchestrator`. No direct LLM cart mutation or checkout authority is permitted.

**Status:** Completed exhaustive codebase audit, modular decoupling of oversized God Objects, and WhatsApp replenishment flow hardening:
1. **Orchestrator Decomposition (`backend/intent/orchestrator.py`):** Reduced from 2,078 lines to 899 lines (-1,179 lines, a 57% reduction) by extracting single-responsibility stage coordinators:
   - `orchestrator_confirm.py` (439 lines): Immutable basket snapshotting, fingerprint validation, and locked checkout execution.
   - `orchestrator_choice.py` (357 lines): Ambiguity clarification resolution, user choice gating, and change requests.
   - `orchestrator_tracking.py` (344 lines): Deferred UPI payment status polling, order details extraction, and rider/coordinate tracking.
   - `orchestrator_address.py` (193 lines): Address matching, durable customer caching, and post-cart progression.
   - `orchestrator_payment.py` (138 lines): Payment option grouping, selection matching, and preference caching.
2. **Recovery Engine Decomposition (`backend/intent/recovery.py`):** Reduced from 968 lines to 487 lines (-481 lines, a 50% reduction) by isolating concrete recovery strategies into `recovery_strategies.py` (605 lines) and candidate ranking into `recovery_candidates.py` (198 lines).
3. **Swiggy MCP Adapter Decomposition (`backend/integrations/commerce/swiggy_adapter.py`):** Reduced from 1,321 lines to 513 lines (-808 lines, a 61% reduction) by extracting response payloads and schemas into `swiggy_parsers.py` (485 lines), `swiggy_normalizers.py` (354 lines), and JSON-RPC 2.0 transport into `swiggy_client.py` (151 lines).
4. **Presentation Decoupling (`formatters.py`):** Pure presentation module housing WhatsApp message templates, receipts, address prompts, payment prompts, and order/delivery status strings.
5. **Parser & Taxonomy Separation (`taxonomies.py`, `validator.py`):** Extracted packaging slots, unit maps, keywords, and stop words into `taxonomies.py` (100 lines) and validator into `validator.py` (127 lines).
6. **Zero Breaking Changes & 100% Behavioral Invariant Preservation:** Preserved every public method contract across `GrocerOrchestrator`, `RecoveryEngine`, and `SwiggyMCPAdapter`.

**Quality Gates:**
- `pytest backend/tests`: 383/383 tests passed (100% green in 4.47s).
- `npm run lint`: 0 errors, 0 warnings.
- `npm run build`: Next.js Turbopack compiled successfully in 10.8s (TypeScript clean in 3.4s).
- `graphify update .`: Synchronized 2,282 nodes, 6,239 edges, 126 communities.
- Zero credential leakage; all safety invariants preserved.

**Branch state:**
- `ag/mainline` — canonical active development branch.
- `main` — stable reference branch.
