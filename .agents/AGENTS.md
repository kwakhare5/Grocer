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
pytest backend/tests
```

Never claim green verification without actually running the relevant command.

### Testing Rules
- **Never write unit tests after you write code.** Unit tests written post-hoc suffer from confirmation bias and merely echo implementation logic.
- **Highly prefer E2E tests as the sole testing mechanism.** Use them to verify complex features work across the entire lifecycle. At the end of E2E tests, produce a verifiable and repeatable artifact (`artifacts/e2e_verification_report.json` and `docs/E2E_VERIFICATION_REPORT.md`).
- **If you must test a system in isolation, first write down all the ways it could fail, then write the code.** Enumerate adversarial failure modes upfront (boundaries, corrupt payloads, network drops, session amnesia, financial leaks), assert those failure modes, and only then implement the code.

## 14. DECISION RULE FOR NEW IDEAS

Before implementing a proposed feature, ask:

> Does this directly improve the user's ability to complete a grocery task while preserving the stated intent across changing commerce state?

If the answer is no, it does not belong in GROCER v2 unless the architectural contract is deliberately changed first.

## 15. SESSION RESUME

**Last completed:** Live Render backend deployment (`dep-davro67avr4c73d675d0`) is LIVE and fully operational. Resolved exit code 3 root cause by routing Supabase database connection through the Singapore IPv4 Supavisor pooler (`aws-0-ap-southeast-1.pooler.supabase.com:5432`). Live `/api/ready` confirmed HTTP 200 with `status: "ready"` and `missing: []`. Live `/api/health` confirmed HTTP 200 `alive`. Live `/api/whatsapp/webhook` verified challenge response 200. Test suite 145/145 pytest green, ESLint clean, Next.js build clean.

**Next implementation gate:** Conduct end-to-end 2-customer real-device WhatsApp test flow. Keep CHECKOUT_MODE=review and LIVE_CHECKOUT_ENABLED=false.

**Current status:** Production backend is live, connected to Supabase PostgreSQL, and ready for WhatsApp customer conversations.

