# GROCER v2 — Master Engineering Specification

> **Status:** LOCKED PRODUCT SCOPE / ACTIVE ENGINEERING SOURCE OF TRUTH
> **Version:** 3.0
> **Updated:** 2026-09-06
> **Repository:** `kwakhare5/Grocer`
> **Product:** WhatsApp grocery replenishment assistant + intent-preserving conversational commerce
> **Commerce provider:** Swiggy Instamart through `CommercePort` / MCP
> **Companion operations product:** `kwakhare5/Dark-store-operator`

---

## 0. Purpose of this document

This file is the **single source of truth for the current GROCER product**.

Coding agents, designers, reviewers, and future contributors must implement this specification rather than inventing a new interpretation of GROCER.

A genuine technical problem does not authorize a silent product change. When implementation exposes a conflict:

1. stop at the affected boundary;
2. document the evidence and the smallest viable change;
3. preserve the locked product thesis unless explicitly changed;
4. update this file when a locked decision changes;
5. then implement.

### Status labels

- **LOCKED** — product decision; do not casually change.
- **IMPLEMENT** — required capability.
- **SIMULATE** — deliberately simulated; never present as a live capability.
- **TBD** — implementation detail; choose the simplest sound option when reached.
- **OPTIONAL** — only after the core loop works.
- **OUT OF SCOPE** — do not build for this version.

---

# 1. Product identity

## 1.1 One-sentence definition

> **GROCER is a WhatsApp grocery replenishment agent that preserves a user's shopping intent across changing commerce conditions, recovering automatically when safe and asking the human to decide when the system cannot safely infer the right action.**

## 1.2 What changed from the previous scope

The previous GROCER documentation described both consumer replenishment and a dark-store operations system inside one repository. That architecture is no longer the product boundary.

**LOCKED:** the dark-store operations platform is a separate companion repository:

`https://github.com/kwakhare5/Dark-store-operator`

GROCER must not reintroduce dark-store operations as a subsystem.

The current product is the **existing WhatsApp consumer assistant extended with an Intent layer, verification loop, policy/memory, and recovery behavior**.

This is an evolution of GROCER, not a replacement product and not a separate generic “AI shopping assistant.”

## 1.3 Core thesis

The core innovation is **intent preservation**, not chat, product search, or simple cart creation.

A user's request describes an intended outcome. The commerce state is only the current implementation of that outcome.

Example:

> “get my weekly groceries under ₹2,000, vegetarian, use my usual brands.”

The agent should maintain that goal even when:

- a preferred product becomes unavailable;
- a pack size changes;
- price changes cause a budget breach;
- a substitution becomes necessary;
- a cart operation partially succeeds;
- a commerce action returns an error;
- a previously valid cart becomes stale.

The system therefore runs a closed loop:

```text
USER INTENT
    ↓
INTERPRET
    ↓
CREATE INTENT CONTRACT
    ↓
PLAN / EXECUTE
    ↓
OBSERVE LIVE COMMERCE STATE
    ↓
VERIFY AGAINST INTENT
    ↓
PASS ────────────────┐
    │                │
    ▼                │
REQUEST APPROVAL     │
    │                │
    ▼                │
CHECKOUT             │
                     │
FAIL                 │
    ↓                │
RECOVER / REPLAN     │
    ↓                │
VERIFY AGAIN ────────┘
```

The project is successful when it can preserve the user's objective even when the underlying commerce transaction changes.

---

# 2. Product goals

GROCER v2 must demonstrate:

1. **Natural-language intent understanding** for grocery tasks.
2. **Explicit modeling of hard constraints and soft preferences.**
3. **Policy-aware action selection** rather than unrestricted LLM behavior.
4. **Cart construction through the existing `CommercePort`.**
5. **Continuous verification of commerce state against the intent contract.**
6. **Automatic recovery for safe, well-defined failures.**
7. **Human clarification when multiple valid choices exist or confidence is insufficient.**
8. **Explicit confirmation before consequential checkout.**
9. **Real Swiggy Instamart execution through the existing MCP adapter when approved access is available.**
10. **Deterministic failure simulation and measurable evaluation.**

The strongest demonstration should make the following obvious:

> **The system does not merely make a cart. It understands what the user meant, detects when the live cart no longer satisfies that intent, repairs it when it can, and asks for help only when the user's decision is genuinely required.**

---

# 3. Product boundary

## 3.1 IN SCOPE

### Consumer experience

- WhatsApp-style conversational interface.
- Existing GROCER proactive replenishment experience.
- Natural-language grocery requests.
- Intent extraction and normalization.
- Session state.
- Soft preference memory.
- Hard constraints.
- Budget handling.
- Quantity and pack-size requirements.
- Brand preferences.
- Dietary/category constraints when explicitly stated.
- Substitution policy.
- Cart creation and modification.
- Cart/state verification.
- Failure detection.
- Recovery and replanning.
- Clarification messages.
- Explicit checkout confirmation.
- Basic order/tracking state through the commerce provider.

### Engineering

- `IntentContract` domain model.
- Deterministic intent verification.
- Policy/constraint engine.
- Recovery engine.
- Commerce failure taxonomy.
- State snapshots/events where required for recovery and evaluation.
- Mock/deterministic commerce adapter.
- Swiggy Instamart MCP adapter.
- Scenario/failure injection at the commerce boundary.
- Deterministic regression tests and evaluation harness.

## 3.2 OUT OF SCOPE

Do not build these into GROCER v2:

- Dark-store operations.
- Inventory optimization for internal stores.
- Warehouse management.
- Supplier management for dark stores.
- Transfer/reorder/discount/hold operations tooling.
- Robotics.
- Generic marketplace aggregation.
- Competitor price intelligence.
- Autonomous refunds or autonomous customer-service remediation that the available MCP contract does not support.
- Unrestricted autonomous purchasing.
- A standalone AI infrastructure/evaluation platform detached from GROCER.
- A second product architecture alongside the existing GROCER system.

The dark-store platform remains in `Dark-store-operator`.

---

# 4. Product job-to-be-done

## Primary job

> **Help me complete my grocery task on quick commerce without making me repeatedly manage product changes, cart failures, substitutions, and small commerce decisions.**

## Secondary jobs

- Warn before recurring household staples run out.
- Translate informal requests into an actionable basket.
- Preserve stated preferences.
- Keep the basket inside declared hard constraints.
- Explain only the decisions that need human input.
- Avoid accidental or unauthorized checkout.

---

# 5. Intent Contract

The `IntentContract` is the canonical representation of what the user is trying to accomplish during a commerce session.

The cart is **not** the source of truth for intent.

## 5.1 Required conceptual fields

```text
IntentContract
├── intent_id
├── session_id
├── goal
├── items[]
├── hard_constraints[]
├── soft_preferences[]
├── budget
├── quantity_rules
├── pack_size_rules
├── brand_preferences[]
├── substitution_policy
├── dietary_constraints[]
├── delivery_preferences
├── authorization_scope
├── confidence
├── ambiguities[]
├── source_context
├── created_at
├── updated_at
└── version
```

The exact database representation may evolve, but the domain semantics must remain equivalent.

## 5.2 Example

```yaml
goal: weekly grocery restock
items:
  - product: milk
    quantity: 2L
  - product: bread
    quantity: 1
  - product: eggs
    quantity: 12
hard_constraints:
  - vegetarian
  - total <= 2000
soft_preferences:
  - usual_brands
brand_preferences:
  - milk: usual_brand
substitution_policy:
  category: same_category
  pack_size_tolerance: reasonable
  max_budget_deviation: 0 unless explicitly allowed
authorization_scope:
  checkout: explicit_confirmation_required
```

## 5.3 Precedence rules

When information conflicts:

```text
CURRENT EXPLICIT USER REQUEST
        >
HARD CONSTRAINTS
        >
CURRENT SESSION CHOICES
        >
STORED SOFT PREFERENCES
        >
AGENT DEFAULTS
```

Stored memory can guide a choice but must never override an explicit current instruction.

## 5.4 Hard vs soft

### Hard constraint

A violation is normally a **failure** and cannot be silently accepted.

Examples:

- “under ₹2,000”
- “vegetarian only”
- “12 eggs” when exact quantity is required
- “do not use another brand” when explicitly stated.

### Soft preference

A preference influences ranking but can be relaxed only according to the user's stated policy or a clarification path.

Examples:

- usual brand
- preferred pack size
- preferred product variant.

The system must never convert a soft preference into a hard constraint without evidence.

---

# 6. Autonomy policy

GROCER uses a **three-level conversational autonomy model**.

| Situation | System behavior |
|---|---|
| Safe, deterministic, inside the intent | **Act automatically** |
| More than one reasonable choice / meaningful ambiguity | **Ask the user** |
| Consequential financial action | **Require explicit confirmation** |

Examples of safe automatic actions:

- add an explicitly requested item;
- replace an unavailable item using an already-approved substitution policy;
- recalculate the basket after a safe substitution;
- retry an operation that the provider contract marks as safely retryable.

Examples requiring user input:

- two substitutions are materially different;
- budget would need to change;
- a preferred brand must be abandoned without an authorized policy;
- item quantity needs interpretation;
- an action is not clearly covered by the user's authorization scope.

Checkout is always consequential.

**LOCKED:** checkout cannot execute unless the backend receives explicit user confirmation.

---

# 7. Memory and preferences

Memory exists to reduce repetitive conversation, not to override the user's current request.

## 7.1 What may be stored

Useful durable preference examples:

- commonly purchased brands;
- preferred pack sizes;
- recurring grocery patterns;
- substitution preferences when explicitly established.

## 7.2 What should not be treated as permanent policy

- old prices;
- stale availability;
- a one-off substitution;
- an inferred preference that has no meaningful evidence.

## 7.3 Precedence

```text
current request > explicit session choice > durable preference > default
```

Do not store the full chat transcript as the primary memory model. Store normalized preference/intent information only where it has product value.

---

# 8. Commerce architecture

The current commerce foundation is retained and extended.

```text
WhatsApp / Conversation Layer
          ↓
Intent Layer
          ↓
Customer Commerce Service
          ↓
CommercePort
       ↙      ↘
Mock Adapter   Swiggy MCP Adapter
```

`CommercePort` is the provider boundary. Provider-specific MCP tool calls must remain inside the Swiggy adapter.

## 8.1 Existing foundation to preserve

- `CustomerService` / customer domain service layer.
- `CommercePort`.
- `MockCommerceAdapter`.
- `SwiggyMCPAdapter`.
- Commerce models and exceptions.
- Existing checkout guard.
- Existing WhatsApp/customer UI language.

New intent/recovery behavior must be layered on top of this foundation rather than replacing it with a second architecture.

## 8.2 Swiggy MCP rules

Before modifying provider integration, use the authoritative Swiggy Builders Club documentation.

Do not invent tool names, parameters, response shapes, retry semantics, or checkout behavior.

Provider errors must be normalized at the adapter/domain boundary so higher layers can reason about failures without depending on raw MCP payloads.

## 8.3 Checkout guard

The backend must reject checkout without explicit authorization.

Conceptual invariant:

```python
if not explicit_confirmation:
    raise UnconfirmedCheckoutError
```

The frontend may present confirmation UX, but it is not the authority that guarantees safety.

---

# 9. Intent verification

Verification is the second half of the core product thesis.

After every meaningful commerce mutation, compare the observed state against the current `IntentContract`.

## 9.1 Verification inputs

- active intent contract;
- current cart;
- prices/totals;
- product availability;
- quantity;
- pack size;
- brand/variant;
- substitution decisions;
- applicable policies;
- authorization scope.

## 9.2 Verification output

Conceptually:

```text
PASS
or
FAIL
├── hard_constraint_violations[]
├── soft_preference_deviations[]
├── unresolved_items[]
├── budget_delta
├── stale_state_flags[]
├── confidence
└── recovery_candidates[]
```

## 9.3 Verification principles

- Deterministic hard-constraint checks.
- No hidden LLM-only verification for critical rules.
- Explainable violation codes.
- Re-check after recovery.
- Re-check immediately before consequential checkout.

---

# 10. Recovery engine

The Recovery Engine is the first major feature wedge for v2.

Its job is:

> **When the live commerce state no longer satisfies the user's intent, find the safest valid path back to the intent or ask the human when no safe path is known.**

## 10.1 Recovery loop

```text
OBSERVE FAILURE
      ↓
CLASSIFY FAILURE
      ↓
CHECK POLICY
      ↓
GENERATE CANDIDATES
      ↓
FILTER HARD CONSTRAINTS
      ↓
RANK SAFE OPTIONS
      ↓
AUTO-APPLY or ASK USER
      ↓
VERIFY
      ↓
RETRY / COMPLETE / ESCALATE
```

## 10.2 Initial recovery classes

V1 should support a small, strong set:

1. Product unavailable.
2. Preferred brand unavailable.
3. Pack size changed.
4. Price change causes budget drift.
5. Cart becomes inconsistent/stale.
6. Safe provider retry after a transient error.
7. Partial cart operation success.
8. Minimum-order or basket-validity failure when the user intent allows repair.

Do not build dozens of exotic failure classes before these work reliably.

## 10.3 Candidate ranking

Candidate recovery options should consider:

- hard-constraint satisfaction;
- category equivalence;
- pack-size similarity;
- brand preference;
- price impact;
- budget compliance;
- user policy;
- availability confidence;
- number of additional changes required.

Do not use an opaque model when a deterministic ranking rule is adequate.

## 10.4 Recovery limits

The system must avoid endless loops.

Use bounded attempts and explicit terminal states such as:

```text
RECOVERED
NEEDS_USER_DECISION
BLOCKED
FAILED
```

A failed recovery must not be represented as success.

---

# 11. Conversation behavior

WhatsApp is the interface, not the innovation.

Messages should be short, actionable, and proportional to the user's decision burden.

## 11.1 Normal case

Example:

> Your weekly basket is ready — ₹1,842. I kept your usual brands and stayed under your ₹2,000 budget.

## 11.2 Automatic recovery

Example:

> 2 items changed because they went out of stock. I replaced them using your saved substitution policy and the basket is still within budget.

## 11.3 Ambiguity

Example:

> Your usual milk is unavailable. I found two reasonable options: Mother Dairy 1L at ₹62 or Amul 500ml ×2 at ₹70. Which should I use?

## 11.4 Checkout

Example:

> Your final basket is ₹1,934. Ready to place the order? Confirm checkout.

The checkout step must remain explicitly authorized.

---

# 12. Agent architecture

The LLM is not the system of record and not the final authority over hard constraints.

## 12.1 Responsibilities of the LLM

- interpret natural language;
- extract candidate intent fields;
- resolve conversational references;
- propose plans/actions;
- summarize recovery options;
- decide when a clarification question is useful;
- orchestrate tool calls within defined capabilities.

## 12.2 Responsibilities of deterministic code

- enforce hard constraints;
- calculate totals;
- verify cart state;
- enforce authorization;
- classify provider errors;
- enforce retry policy;
- maintain state transitions;
- validate candidate recovery actions;
- verify post-action results.

## 12.3 Core rule

> **LLM interprets and proposes. Deterministic backend code enforces and verifies.**

---

# 13. State model

The implementation should maintain enough state to reconstruct why the agent acted.

A minimal conceptual state set is:

```text
ConversationSession
IntentContract
CommerceSnapshot
ActionAttempt
RecoveryAttempt
ApprovalState
OutcomeEvent
```

Do not build a giant event-sourcing framework prematurely.

## 13.1 Session state

Should support:

- active intent;
- current cart reference;
- pending clarification;
- pending approval;
- current recovery attempt;
- terminal state.

## 13.2 Commerce snapshot

Capture the minimum relevant state needed for verification and recovery debugging.

## 13.3 Event/outcome record

Useful event types include:

```text
INTENT_CREATED
INTENT_UPDATED
CART_FETCHED
CART_MUTATED
VERIFICATION_PASSED
VERIFICATION_FAILED
RECOVERY_STARTED
RECOVERY_APPLIED
USER_CLARIFICATION_REQUESTED
USER_DECISION_RECEIVED
CHECKOUT_AUTHORIZED
CHECKOUT_ATTEMPTED
CHECKOUT_SUCCEEDED
CHECKOUT_FAILED
```

---

# 14. Error and retry semantics

The system must distinguish at least:

- deterministic business failure;
- stale state;
- transient transport failure;
- provider rejection;
- authentication/authorization failure;
- partial success;
- unknown outcome;
- user ambiguity.

Retry behavior must respect the real provider contract.

Never blindly retry a consequential operation just because a request failed.

When the provider returns an unknown outcome, first recover/observe state where supported before attempting another consequential action.

---

# 15. Deterministic failure simulation

The project needs a controlled simulation layer for evaluation and demos.

This is **not** a fake second product.

The simulator sits at the commerce boundary and injects known failures around the same contracts used by the real provider adapter.

Example:

```text
CustomerService
     ↓
CommercePort
     ↓
Failure Injection / Scenario Adapter
     ↓
Mock Commerce
```

or equivalent implementation that leaves the production architecture clean.

## Initial scenario set

### Scenario A — happy path

User request is satisfied without recovery.

### Scenario B — preferred item unavailable

Original item fails availability check; policy allows substitution; agent recovers automatically.

### Scenario C — budget drift

A price change causes the basket to exceed budget; agent finds a compliant repair or asks the user.

### Scenario D — ambiguous substitution

Two materially different alternatives exist; agent asks the user rather than choosing arbitrarily.

### Scenario E — stale cart

A previously valid basket is no longer valid; verifier detects drift before checkout.

### Scenario F — transient provider failure

Safe retry is permitted according to the adapter's documented semantics.

These are enough for V1. Expand only after the main loop is reliable.

---

# 16. Evaluation framework

Evaluation is an internal engineering capability of GROCER, not a separate SaaS/product.

## 16.1 Core metrics

### Intent preservation rate

Percentage of completed tasks where the final verified basket satisfies all applicable hard constraints and intended objective conditions.

### Hard constraint satisfaction

Percentage of action states with zero hard-constraint violations.

### Recovery success rate

Percentage of injected failures recovered without unnecessary human intervention.

### Human intervention rate

Percentage of tasks requiring clarification or user decisions.

### Unsafe autonomous action rate

Any action that violates authorization or hard policy. Target: **0**.

### Budget deviation

Difference between final basket total and declared budget where relevant.

### Unnecessary clarification rate

How often the system asks the user despite a safe deterministic decision being available.

### Recovery attempts

Number of recovery cycles before success, clarification, or terminal failure.

### Provider/tool efficiency

Useful counts such as MCP calls per completed task.

## 16.2 Regression testing

Every new recovery rule should have deterministic tests covering:

- successful recovery;
- blocked recovery;
- ambiguity;
- stale state;
- hard constraint violation;
- authorization failure;
- provider error;
- incorrect/partial outcome.

Do not optimize metrics by weakening constraints.

---

# 17. Security and safety invariants

These are mandatory.

1. **No checkout without explicit confirmation.**
2. **No secrets in frontend code, logs, committed files, or client-visible state.**
3. **LLM cannot directly mutate commerce state outside defined tools/services.**
4. **Hard constraints are enforced server-side.**
5. **The backend verifies consequential state immediately before checkout.**
6. **Failed or uncertain operations are never reported as successful.**
7. **Provider-specific credentials remain inside the integration boundary.**
8. **Current explicit user instructions override durable preferences.**
9. **The system does not invent cart/product/order facts.**
10. **Retries must respect provider semantics, especially for consequential actions.**

---

# 18. Existing GROCER UX foundation

Preserve the existing visual language unless a justified redesign is required.

The current customer experience is an interactive WhatsApp/iPhone-style replenishment surface. The Intent work should make the behavior behind this surface more real; it should not turn the UI into a different product.

Continue to enforce the project's established quality rules:

- restrained, polished consumer UX;
- Lucide SVG icons;
- no emoji-only buttons;
- readable conversational hierarchy;
- minimal decision burden;
- clear confirmation state;
- no fake operational dashboard brought back from the former dark-store subsystem.

---

# 19. Repository boundary and cleanup

The current codebase contains leftovers from the historical dark-store implementation. Before expanding Intent, clean or isolate those residues so the architecture matches the product claim.

### Keep and extend

- customer UI;
- WhatsApp demo/interaction engine where still useful;
- `CustomerService` / customer domain;
- `CommercePort`;
- `MockCommerceAdapter`;
- `SwiggyMCPAdapter`;
- commerce exceptions/models;
- explicit checkout guard;
- customer-facing FastAPI endpoints.

### Refactor or remove from GROCER

- operations-only API routes;
- dark-store inventory/simulation authority;
- Store/Supplier/Batch/Transfer/Reorder/Discount/Hold systems that only exist for the old operations product;
- frontend code that mutates simulated internal inventory merely because a consumer order was placed;
- local commerce-to-dark-store state coupling;
- stale documentation claiming two products live in one repository.

Removal should be evidence-driven and incremental. Do not delete shared code merely because its name sounds operational.

---

# 20. Recommended implementation sequence

## Phase 0 — Boundary cleanup

Align code with the consumer-only product boundary.

Acceptance:

- no frontend-owned fake operational truth;
- no operational API surface presented as part of GROCER;
- customer commerce path remains green;
- `CommercePort` remains intact.

## Phase 1 — Intent Contract

Implement the canonical domain model and persistence/session shape.

Acceptance:

- explicit goal/items/constraints/preferences can be represented;
- current request overrides memory;
- no LLM-only critical state.

## Phase 2 — Intent extraction

Translate WhatsApp language into a validated contract.

Acceptance:

- deterministic schema validation;
- confidence and ambiguity surfaced;
- missing critical information can trigger clarification.

## Phase 3 — Policy and preference layer

Separate hard constraints from soft preferences and durable memory.

Acceptance:

- policy precedence is deterministic;
- explicit current request wins.

## Phase 4 — Cart verifier

Compare actual commerce state to the contract.

Acceptance:

- hard violations are detectable without an LLM;
- verifier works against mock commerce.

## Phase 5 — Recovery engine

Start with one polished failure loop, then expand.

First recommended loop:

```text
preferred item unavailable
→ policy-approved candidate
→ cart repair
→ verify
→ continue
```

Acceptance:

- automatic recovery works for deterministic cases;
- ambiguous cases stop and ask;
- recovery is bounded.

## Phase 6 — Agent orchestration

Connect conversation + intent + policy + commerce + verifier + recovery.

Acceptance:

- end-to-end WhatsApp task can complete;
- LLM does not bypass deterministic gates.

## Phase 7 — Memory

Persist useful soft preferences.

Acceptance:

- memory improves convenience;
- explicit request overrides memory.

## Phase 8 — Evaluation and adversarial scenarios

Build the deterministic failure-injection suite and metrics.

Acceptance:

- every core scenario is reproducible;
- metrics are generated from observable state.

## Phase 9 — Live Swiggy hardening

Exercise the real `SwiggyMCPAdapter` only where approved access and safe test conditions permit.

Acceptance:

- provider-specific behavior is isolated;
- documented error semantics are respected;
- checkout remains explicitly authorized.

## Phase 10 — Demo hardening

Polish the end-to-end narrative.

Acceptance:

- one normal task;
- one automatic recovery;
- one human clarification;
- one explicit checkout;
- one deterministic failure injection;
- visible verification/recovery evidence.

---

# 21. Flagship demo

The flagship demo should be one coherent story, not a collection of disconnected features.

### User

> “get my weekly groceries under ₹2,000, vegetarian, use my usual brands.”

### System

1. Extract intent.
2. Resolve stored soft preferences.
3. Search/construct the basket.
4. Add items through `CommercePort`.
5. Verify basket against the intent contract.
6. Inject one or more controlled commerce changes.
7. Detect intent drift.
8. Recover automatically where the policy allows.
9. Re-verify.
10. Ask the user only when an actual decision remains.
11. Present the final basket.
12. Require explicit confirmation.
13. Execute checkout.
14. Report the verified result.

### What the demo must prove

> **Commerce state can change without silently changing what the user meant.**

---

# 22. Engineering standards

- Prefer small, testable domain modules.
- Avoid speculative abstractions.
- Do not introduce microservices.
- Do not build infrastructure for theatre.
- Keep provider logic behind `CommercePort`.
- Keep critical policy deterministic.
- Add tests before broad refactors where practical.
- Preserve working behavior unless the target architecture requires change.
- Use actual repository code as evidence; do not trust stale README claims over implementation.
- When a feature is simulated, label it as simulated in code/docs/demo.

---

# 23. Anti-drift rules for coding agents

These rules apply to Gemini, Antigravity, Claude, Codex, and any other coding agent.

### NEVER

- turn GROCER back into a dark-store operations project;
- add inventory optimization, store transfer, reorder, supplier, warehouse, or operations-cockpit features;
- create a second parallel commerce architecture;
- replace `CommercePort` with provider-specific calls spread through the codebase;
- move commerce authority into the frontend;
- let the LLM silently override hard constraints;
- allow autonomous checkout without explicit confirmation;
- invent Swiggy MCP tools or parameters;
- build a generic marketplace assistant as the main product;
- create an independent “agent evaluation platform” instead of integrating evaluation into GROCER;
- expand scope because a demo looks visually small;
- rewrite functioning infrastructure without a measured reason.

### ALWAYS

- treat GROCER as the existing **WhatsApp consumer replenishment assistant** being extended;
- add new intelligence **above the existing commerce foundation**;
- preserve `CommercePort` and `SwiggyMCPAdapter` boundaries;
- model intent explicitly;
- verify live commerce state against intent;
- recover when safe, clarify when uncertain;
- enforce consequential actions server-side;
- use deterministic tests for hard rules;
- inspect the actual repository before deciding what is already implemented;
- keep the dark-store companion project separate.

---

# 24. Definition of done

GROCER v2 is complete when a user can express a realistic grocery goal through WhatsApp and the system can:

```text
UNDERSTAND
   ↓
FORMALIZE INTENT
   ↓
BUILD CART
   ↓
VERIFY
   ↓
DETECT DRIFT
   ↓
RECOVER OR ASK
   ↓
VERIFY AGAIN
   ↓
GET EXPLICIT APPROVAL
   ↓
CHECKOUT
   ↓
VERIFY OUTCOME
```

with deterministic enforcement of hard constraints, bounded recovery, measurable evaluation, safe checkout behavior, and no reintroduction of the dark-store operations product.

**This is the product. Do not drift from it.**
