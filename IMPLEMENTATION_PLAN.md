# GROCER v2 — Implementation Plan

> **Source of truth:** `GROCER_V2_MASTER_SPEC.md`
> **Status:** ACTIVE IMPLEMENTATION ROADMAP
> **Updated:** 2026-09-06

This is an execution plan, not a second product specification.

## 0. Implementation rules

1. GROCER is the existing WhatsApp consumer replenishment assistant being extended with Intent.
2. `GROCER_V2_MASTER_SPEC.md` controls product scope and architecture.
3. Do not reintroduce the separate dark-store operations platform.
4. Extend the existing `CustomerService` + `CommercePort` foundation.
5. LLMs interpret/propose; deterministic services enforce/verify.
6. Backend is authoritative for commerce/session/intent/recovery/authorization state.
7. Checkout requires explicit human confirmation.
8. Do not create a second provider boundary or generic marketplace architecture.
9. Prefer small, testable slices over broad rewrites.
10. Every phase ends with relevant tests and honest verification.

---

# 1. Execution order

| Phase | Focus | Deliverable | Priority |
|---|---|---|---|
| 0 | Boundary cleanup | Consumer-only GROCER baseline | P0 |
| 1 | Intent Contract | Canonical goal/constraints/preferences model | P0 |
| 2 | Intent extraction | Natural language → validated intent | P0 |
| 3 | Policy + memory | Hard/soft precedence + durable preferences | P0 |
| 4 | Cart verification | Deterministic intent-vs-cart verifier | P0 |
| 5 | Recovery engine | Safe repair/replan loop | P0 |
| 6 | Agent orchestration | End-to-end conversational commerce loop | P0 |
| 7 | Failure simulation | Deterministic commerce failure injection | P0 |
| 8 | Evaluation | Reliability metrics + regression scenarios | P0 |
| 9 | Live MCP hardening | Verified Swiggy adapter behavior | P1 |
| 10 | Demo hardening | Flagship end-to-end experience | P1 |

Do not jump to later polish while the core intent → verify → recover loop is unstable.

---

# 2. Phase 0 — Consumer boundary cleanup

## Goal

Make the actual codebase match the already-frozen product boundary.

## Inspect first

- `backend/api/`
- `backend/services/customer/`
- `backend/integrations/commerce/`
- `backend/models/`
- frontend customer components
- `app/page.tsx`
- tests

## Required work

### Remove/isolate old operations residue

Identify and safely remove or isolate:

- operations-only routes;
- dark-store decisioning dependencies;
- old store/supplier/inventory mutation paths unrelated to the consumer flow;
- outdated operations UI imports.

### Remove fake consumer → dark-store mutation

A customer order should not mutate a simulated dark-store inventory universe merely because the old project used to contain one.

### Preserve

- WhatsApp customer experience;
- `CustomerService` customer flow;
- `CommercePort`;
- `MockCommerceAdapter`;
- `SwiggyMCPAdapter`;
- checkout authorization guard;
- customer commerce tests.

## Acceptance

```text
Consumer request
→ CustomerService
→ CommercePort
→ adapter
```

works without dependence on the removed dark-store product.

---

# 3. Phase 1 — Intent Contract

## Goal

Create a canonical structured representation of user intent.

## Required fields

```text
intent_id
session_id
goal
items
hard_constraints
soft_preferences
budget
quantity_rules
pack_size_rules
brand_preferences
substitution_policy
dietary_constraints
delivery_preferences
authorization_scope
confidence
ambiguities
version
timestamps
```

## Acceptance

- intent can be serialized/deserialized;
- hard vs soft semantics are explicit;
- authorization is represented separately from preference;
- no critical state exists only inside a prompt.

---

# 4. Phase 2 — Intent extraction

## Goal

Convert WhatsApp language into a validated `IntentContract`.

## Examples

```text
“get my weekly groceries under ₹2,000”
→ goal + budget + recurring task

“use my usual brands”
→ soft preference

“only vegetarian items”
→ hard constraint

“don't replace the milk with another brand”
→ substitution policy
```

## Rules

- Current explicit request wins.
- Missing critical information creates clarification, not hallucination.
- Confidence can trigger clarification, but confidence never overrides deterministic validation.

## Tests

- normal request;
- multiple items;
- quantities;
- budget;
- hard/soft distinction;
- contradictory request;
- ambiguous quantity;
- explicit substitution rule;
- current instruction overriding memory.

---

# 5. Phase 3 — Policy and memory

## Goal

Reduce repetitive user decisions without silently changing intent.

## Precedence

```text
current explicit request
    > session choice
    > stored soft preference
    > default
```

## Memory examples

- usual brand;
- common pack size;
- accepted substitutions;
- recurring grocery pattern.

## Do not store as permanent preference

- stale availability;
- old price;
- one-off choices without evidence.

## Acceptance

A remembered preference can affect ranking but cannot override an explicit current request.

---

# 6. Phase 4 — Intent Verifier

## Goal

Determine whether the live commerce state still represents the user's intended outcome.

## Inputs

- current `IntentContract`;
- live/mock cart;
- product/variant information;
- price/total;
- availability;
- substitution decisions;
- policy.

## Output

```text
PASS
FAIL
  hard_constraint_violations
  soft_preference_deviations
  unresolved_items
  budget_delta
  stale_state
  recovery_candidates
```

## Required properties

- deterministic hard checks;
- clear violation codes;
- no LLM dependency for critical validation;
- reusable before checkout and after recovery.

## First tests

- exact cart pass;
- missing item;
- wrong brand;
- wrong quantity;
- wrong pack size;
- budget exceeded;
- unavailable item;
- stale cart;
- allowed soft preference deviation.

---

# 7. Phase 5 — Recovery engine

## Goal

Return a failed commerce state to a valid intent state when a safe path exists.

## Core loop

```text
failure
→ classify
→ policy check
→ candidate generation
→ hard-constraint filtering
→ candidate ranking
→ auto-apply or ask
→ verify again
```

## First recovery wedge

### Preferred item becomes unavailable

Example:

```text
Intent:
  milk = usual brand, 1L

Live state:
  preferred product unavailable

Recovery:
  find allowed same-category alternatives
  rank by policy
  modify cart
  verify total + constraints
```

This is the first “killer” scenario because it demonstrates intent preservation without requiring a massive feature surface.

## Expand after first scenario is stable

- pack-size drift;
- budget drift;
- stale cart;
- partial success;
- safe transient retry;
- minimum-order/basket repair.

## Terminal states

```text
RECOVERED
NEEDS_USER_DECISION
BLOCKED
FAILED
```

Recovery must be bounded.

---

# 8. Phase 6 — Agent orchestration

## Goal

Connect conversation, intent, policy, commerce, verification, recovery, and approval.

## Desired flow

```text
WhatsApp
 ↓
intent extraction
 ↓
contract
 ↓
plan
 ↓
commerce tools
 ↓
verify
 ↓
recover/ask if needed
 ↓
verify
 ↓
explicit approval
 ↓
checkout
 ↓
outcome verification
```

## Rule

The agent orchestrates. It does not become the domain authority.

---

# 9. Phase 7 — Deterministic failure simulation

## Goal

Make the reliability story reproducible without pretending simulated failures are live Swiggy behavior.

Inject failures at the commerce boundary against the same `CommercePort` semantics used by the real system.

## Initial scenarios

1. Product unavailable.
2. Preferred brand unavailable.
3. Pack size changes.
4. Budget drift.
5. Stale cart.
6. Safe transient failure.
7. Partial cart success.
8. Repairable basket/minimum-order failure.

## Acceptance

Each scenario can be reproduced from a known seed/configuration and produces observable events.

---

# 10. Phase 8 — Evaluation

## Core metrics

### Intent preservation rate

Completed tasks whose final verified state satisfies applicable hard constraints and objective conditions.

### Recovery success rate

Injected failures recovered without unnecessary human intervention.

### Unsafe autonomous action rate

Target: **0**.

### Human intervention rate

Tasks requiring clarification/choice.

### Unnecessary clarification rate

Cases where the agent asks despite an available safe deterministic action.

### Budget deviation

Final total against declared budget.

### Recovery attempts

Number of cycles before terminal state.

### MCP/tool calls

Useful efficiency signal, not a sole optimization target.

## Regression gate

Every recovery rule must include deterministic success, failure, ambiguity, and authorization tests.

---

# 11. Phase 9 — Live Swiggy hardening

## Goal

Use the real Swiggy MCP path through the existing adapter when approved access and safe test conditions permit.

## Rules

- read current Builders Club documentation before changing integration;
- do not invent tool schemas;
- normalize provider errors behind the adapter;
- respect retry semantics;
- do not blindly retry consequential actions;
- never expose credentials;
- retain explicit checkout confirmation.

## Acceptance

Live-provider-specific details do not leak into the domain layer.

---

# 12. Phase 10 — Demo hardening

## Flagship narrative

User:

> “get my weekly groceries under ₹2,000, vegetarian, use my usual brands.”

Then:

1. Intent is extracted.
2. Existing preferences are applied.
3. Basket is built.
4. Basket is verified.
5. A controlled commerce failure occurs.
6. GROCER detects intent drift.
7. GROCER recovers automatically where safe.
8. GROCER asks the user only when ambiguity remains.
9. Basket is verified again.
10. User explicitly confirms checkout.
11. Checkout is executed through the commerce boundary.
12. Outcome is verified and reported.

The demo should prove one idea clearly:

> **The commerce state can change without silently changing what the user asked for.**

---

# 13. Definition of done for implementation

The core V2 loop is done when all of the following work:

```text
NATURAL LANGUAGE
→ INTENT CONTRACT
→ CART
→ VERIFICATION
→ DRIFT DETECTION
→ SAFE RECOVERY / CLARIFICATION
→ RE-VERIFICATION
→ EXPLICIT APPROVAL
→ CHECKOUT
→ OUTCOME VERIFICATION
```

with:

- deterministic hard-constraint enforcement;
- bounded recovery;
- provider isolation;
- zero unauthorized checkout;
- reproducible failure scenarios;
- measurable reliability;
- no dark-store architecture in GROCER.
