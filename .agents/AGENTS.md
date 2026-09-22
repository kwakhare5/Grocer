# AGENTS.md — GROCER Project Rules

> Read this file before coding. It is the operational instruction set for Antigravity/Gemini and other repository agents.
> Product authority: `GROCER_V2_MASTER_SPEC.md`
> Updated: 2026-09-16

## 1. PROJECT IDENTITY — LOCKED

**Name:** GROCER

**What it is:** the existing WhatsApp consumer grocery replenishment assistant extended with intent-preserving commerce behavior.

**Core thesis:** preserve the user's intended shopping outcome even when live commerce state changes.

**Commerce foundation:** `CommercePort` with `MockCommerceAdapter` and `SwiggyMCPAdapter`.

### Critical anti-drift rule

> **GROCER is not a new dark-store project, generic shopping chatbot, or separate Intent product. Intent is an extension of the existing GROCER WhatsApp agent.**

## 2. TARGET FLOW

```text
Meta WhatsApp webhook
  ↓
Durable inbox
  ↓
ShoppingTask application service
  ├── English message proposal
  ├── deterministic reducer
  ├── catalogue resolution
  ├── provider-cart ownership policy
  └── verifier / bounded recovery
  ↓
CommercePort
  ↓
Swiggy MCP / Mock
  ↓
Durable outbox → WhatsApp
```

The legacy conversation/orchestrator runtime remains only until the durable ShoppingTask route is wired and replay-tested. Do not delete it first; do not extend it as the future architecture.

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

1. use one durable ShoppingTask state owner;
2. ensure all natural language becomes a proposal, not a mutation;
3. require full-basket approval and explicit provider-cart ownership;
4. retain `CommercePort` and the checkout guard;
5. persist inbox, outbox, preferences, OAuth tokens, and idempotency safely;
6. replay human conversation transcripts before removing legacy code.

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

**Last completed:** (1) Developed and executed the exhaustive 3-Tier Human Chaos & Stress Matrix (`scripts/human_stress_matrix.py` and `backend/tests/test_human_stress_matrix.py`): Tier 1 (25 stateful multi-turn human personas covering pasta address switching, indecisive cooks, Hinglish, rapid deltas, sick care, budget enforcers, address ping-ponging, and 6-turn marathon sessions — 100% verified green across 100+ stateful turns); Tier 2 (500+ combinatorial permutations covering Indian typos, dietary restrictions, and catalog variance); Tier 3 (1,000 property-based fuzz iterations verifying fee math conservation, turn-boundary invariants, and anti-amnesia filters — 1,000/1,000 passing in 0.74s); (2) Implemented deterministic server-side checkout confirmation gate in `engine.py` preventing LLMs from autonomously confirming orders without explicit human intent; (3) Added 0.6s inter-turn pacing and 6-tier exponential backoff (`max_retries=6`, backoff up to 25s) with `Retry-After` extraction to survive Gemini rolling 15 RPM limits; (4) Enriched `MockCommerceAdapter` with authentic dark store staples and Sangvi Pune address resolution; (5) Purged obsolete `scripts/eval_stress_test.py` and configured `pytest.ini` with `live_llm` marker; (6) 280/280 backend tests passing green in 4.24s; (7) Clean ESLint (0 errors, 0 warnings) and clean Next.js 16 Turbopack production build (1.9s); (8) Codebase knowledge graph updated with `graphify update .`.

**Next implementation gate:** 2-minute video demo recording following the reviewer walkthrough script and official submission to `builders@swiggy.in`.

**Current status:** 280 backend tests passing green (100%), 25/25 human personas passing, 1,000/1,000 property fuzz runs passing, 0 ESLint errors, Next.js build clean, knowledge graph synchronized.


