# AGENTS.md — GROCER Coding Agent Contract

## 1. Read this first

Before changing code, read:

1. `GROCER_V2_MASTER_SPEC.md` — product and architecture source of truth.
2. `CONTEXT.md` — session context, domain language, invariants, anti-drift rules.
3. `ARCHITECTURE.md` — current system boundaries.
4. `IMPLEMENTATION_PLAN.md` — current execution order.

**GROCER is the existing WhatsApp consumer grocery replenishment assistant being extended with an Intent layer.**

Do not reinterpret it as a new project.

## 2. Non-negotiable product boundary

GROCER v2 is:

- WhatsApp consumer grocery replenishment;
- intent-aware shopping task execution;
- intent verification and preservation;
- bounded recovery/replanning;
- user clarification when needed;
- Swiggy Instamart commerce through `CommercePort` / MCP;
- explicit human confirmation before checkout;
- measurable reliability evaluation.

The dark-store operations platform is a separate repository:

`kwakhare5/Dark-store-operator`

### NEVER bring it back

Do not add the following to GROCER:

- dark-store inventory optimization;
- store transfer/reorder/discount/hold decisioning;
- supplier operations;
- warehouse management;
- batch-expiry operations dashboards;
- operations cockpit/map;
- internal fleet command center.

## 3. Extend, do not replace

Preserve and extend the existing customer architecture:

```text
WhatsApp / customer UX
        ↓
Customer service
        ↓
CommercePort
   ↙          ↘
Mock       Swiggy MCP
```

New work should add:

```text
Intent Contract
Intent Verifier
Policy / Memory
Recovery Engine
Evaluation
```

above this foundation.

Do not create a second parallel commerce architecture.

## 4. LLM responsibility

LLM/model code may:

- interpret natural language;
- extract candidate intent;
- propose actions/substitutions;
- summarize options;
- decide when clarification is useful.

LLM/model code must NOT be the only enforcement mechanism for:

- hard constraints;
- budget arithmetic;
- checkout authorization;
- state transitions;
- retry safety;
- cart verification;
- recovery validity.

**LLM interprets and proposes. Deterministic code enforces and verifies.**

## 5. Intent rules

Represent user intent explicitly.

Precedence:

```text
current explicit request
    > current session choice
    > stored soft preference
    > default
```

Never allow memory to silently override the current request.

A hard constraint cannot be relaxed without an explicit user decision or a policy that clearly authorizes the relaxation.

## 6. Recovery rules

When commerce state drifts from intent:

```text
observe
→ classify
→ check policy
→ generate candidates
→ filter hard constraints
→ rank
→ auto-act OR ask
→ verify again
```

Recovery must be bounded. Never create infinite retry loops.

Never report a failed/unknown action as successful.

## 7. Checkout safety

Checkout is always consequential.

The backend must require explicit user confirmation before executing it.

Frontend confirmation UX is not a sufficient security boundary.

Never weaken or remove the existing checkout guard to make demos easier.

## 8. Swiggy MCP

Before changing Swiggy integration, read the current authoritative Builders Club documentation:

- `https://mcp.swiggy.com/builders/llms.txt`
- `https://mcp.swiggy.com/builders/llms-full.txt`
- current Instamart reference/error documentation.

Do not invent tool names, parameters, or retry semantics.

Keep all provider-specific details inside `SwiggyMCPAdapter`.

## 9. Simulation/evaluation

Failure simulation is an internal reliability tool for GROCER.

Use the same `CommercePort` contracts as the real integration.

Initial scenarios should focus on:

- unavailable product;
- preferred brand unavailable;
- pack-size change;
- budget drift;
- stale cart;
- safe transient retry;
- partial cart success;
- minimum-order/basket validity when repairable.

Do not create a separate evaluation product.

## 10. Frontend rules

The frontend is not authoritative for commerce/domain state.

Do not implement a second inventory/state machine in React.

The existing WhatsApp/iPhone customer experience is the primary UI foundation. Improve its intelligence without turning it into an operations dashboard.

## 11. Engineering behavior

- Inspect actual code before making claims about implementation status.
- Prefer minimal, reversible changes.
- Reuse working boundaries.
- Avoid microservices and speculative infrastructure.
- Add deterministic tests around hard rules.
- Keep provider calls behind the adapter.
- Run relevant tests after changes.
- Do not rewrite functioning code solely for aesthetic architectural preference.

## 12. Quality commands

```bash
npm run lint
npm run build
pytest backend/tests
```

Run the commands relevant to the changed area and report failures honestly.

## 13. What to do when requirements appear ambiguous

Do not invent a new product direction.

First ask:

1. Does this directly help preserve user intent?
2. Does it extend the existing WhatsApp + CommercePort flow?
3. Is it compatible with the master spec?
4. Is it actually needed for the current milestone?

If not, do not build it.
