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

**Last completed:** 4-Turn Flow Overhaul, Session Durability & Non-Blocking Cache I/O (2026-09-11)

**Status:** Enforced strict 4-turn shopping flow, optimized backend latency, and hardened session durability:
1. **Strict 4-Turn Sequence Enforced:** Turn 1 (Items added + address prompt) → Turn 2 (Address choice + payment prompt) → Turn 3 (Payment choice + itemized receipt) → Turn 4 (Final confirmation + live Swiggy checkout).
2. **Session Disk Durability:** Backed `OrchestratorSessionStore` with atomic JSON file persistence (`/tmp/grocer_orchestrator_sessions.json`), ensuring active carts, confirmation nonces, and session states survive server reloads mid-conversation.
3. **Non-Blocking Cache I/O:** Migrated `AddressStageManager` synchronous file I/O to atomic background thread writes with temporary file replacement, preventing event loop blocking on active WhatsApp webhook requests. Encapsulated address resolution in `AddressStageManager.resolve_session_address`.
4. **Dead Code Purge:** Removed orphaned wrapper `GrocerOrchestrator._resolve_items` and purged duplicate in-memory state `_customer_saved_addresses` in `base.py`.
5. **WhatsApp Aesthetics & Spacing:** Formatted full address badges (`Label: Street, Landmark, City`), divider lines (`────────────────────`), bullet points (`•`), and contextual emojis (`🛒`, `🧾`, `📍`, `💳`, `🎉`).
6. **Concurrent Catalog Searches (`asyncio.gather`):** Parallelized catalog product searches in `backend/intent/stages/items_stage.py`, slashing multi-item search latency from ~4s to ~1s.

**Quality Gates:**
- `pytest backend/tests`: 372 tests passed (100% green in 16.17s).
- `npm run lint`: 0 errors, 0 warnings.
- `npm run build`: Next.js Turbopack compiled successfully in 2.3s.
- `graphify update .`: Synchronized 2,177 nodes, 5,755 edges, 139 communities.
- Zero credential leakage; all safety invariants preserved.

**Branch state:**
- `ag/mainline` — canonical active development branch.
- `main` — stable reference branch.



