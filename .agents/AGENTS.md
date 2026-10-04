# AGENTS.md — GROCER Project Rules

> Read this file before coding. It is the operational instruction set for Antigravity/Gemini and other repository agents.
> Product authority: `ARCHITECTURE.md` and `docs/SWIGGY_MCP_API.md`
> Updated: 2026-09-30

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
Next.js forwarding route → FastAPI signature verification → PostgreSQL inbox
  ↓
Ordered message worker → GroceryAgentEngine (customer-scoped task snapshot)
  ├── Fresh multi-address choice each order
  ├── Parallel reads; serialized cart, address, and checkout writes
  ├── Provider-observed cart and complete payable-total approval
  └── Review-only checkout by default; live checkout remains release-gated
  ↓
CommercePort → SwiggyMCPAdapter with customer-scoped PostgreSQL token lookup
  ↓
Swiggy Instamart Live MCP (https://mcp.swiggy.com/im)
  ↓
PostgreSQL outbox → Meta WhatsApp delivery
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

When a task sounds like one of these, stop and compare it with `ARCHITECTURE.md` before writing code.

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

## 13. QUALITY GATE, ARCHITECTURE GRAPH & TESTING RULES

- **Graphify First & Auto-Install:** If `graphify-out/graph.json` or `GRAPH_REPORT.md` is missing, automatically run `npx graphify .` to generate the knowledge graph. Always inspect `GRAPH_REPORT.md` / `graphify-out/graph.json` before broad codebase exploration.

Run relevant checks after changes:

```bash
npm run lint
npm run build
pytest backend/tests/test_whatsapp_postgres_e2e.py
```

Never claim green verification without actually running the relevant command.

### Testing Rules
- **Never write unit tests after you write code.** Unit tests written post-hoc suffer from confirmation bias and merely echo implementation logic.
- **Use E2E tests as the sole release test mechanism.** Run the signed WhatsApp webhook through PostgreSQL, agent, and recorded Meta delivery. Record exit code and a repeatable JUnit report under `artifacts/`.
- **If you must test a system in isolation, first write down all the ways it could fail, then write the code.** Enumerate adversarial failure modes upfront (boundaries, corrupt payloads, network drops, session amnesia, financial leaks), assert those failure modes, and only then implement the code.

## 14. DECISION RULE FOR NEW IDEAS

Before implementing a proposed feature, ask:

> Does this directly improve the user's ability to complete a grocery task while preserving the stated intent across changing commerce state?

If the answer is no, it does not belong in GROCER v2 unless the architectural contract is deliberately changed first.

## 15. SESSION RESUME

**Last completed:** The new Mumbai Supabase project has all nine private GROCER tables and one reconnected Swiggy OAuth token. GitHub main and Render remain at `2eb23aa` in review-only checkout mode. The branch `codex/full-whatsapp-recovery` contains an E2E-verified exact-SKU customer-choice flow, one cart write with read-back, failure reconciliation, and human mid-choice correction. A bounded real Swiggy search at the selected Charholi address returned six exact milk choices after a broad-query defect was corrected. No real cart write or order was made.

**Next implementation gate:** Keep Render as the backend. Focus on verified budget language, a deterministic requested-item ledger, lists beyond thirty items, human-style conversations, and real MCP checks with few requests. The pizza step-limit, parallel-choice protocol failure, and mixed-error 429 recovery are fixed on the recovery branch but not deployed. Before production checkout, resolve the Swiggy data-processing release boundary: Render is in Singapore, and Swiggy's published rule requires a signed DPA and transfer safeguards when MCP responses are processed outside India. Follow `docs/GROCER_RECOVERY_PLAN_2026-10-04.md`.

**Current status:** The deployed Render backend is healthy at `2eb23aa`. The recovery branch passes 47 signed-webhook/PostgreSQL E2E cases including 3 opt-in real-Gemini journeys against synthetic commerce; lint, build, and Python compilation passed. No new Swiggy calls, live cart mutation, or order were attempted in this slice. The old database has no backup. An exploratory Mumbai Vercel backend project was removed without deployments; Render remains. Render Singapore and external model location are documented production data-processing gates without the required agreement.
