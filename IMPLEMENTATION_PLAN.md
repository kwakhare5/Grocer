# GROCER v2 — Implementation Plan

> **Status:** Implementation roadmap
> **Source of truth:** `GROCER_V2_MASTER_SPEC.md`
> **Updated:** 2026-09-05
>
> This document turns the master specification into bounded engineering tasks. It is an execution plan, not a second product specification.

---

## 0. Rules for implementation

1. `GROCER_V2_MASTER_SPEC.md` is the product and architecture source of truth.
2. Implement one bounded phase/slice at a time.
3. Do not rewrite the repository from scratch.
4. Reuse working infrastructure when it matches the target architecture.
5. Before changing a major boundary, inspect the existing implementation and explain the proposed diff.
6. Backend is the single source of truth for operational state.
7. Frontend is a presentation/control surface, not an authoritative simulator.
8. LLMs do not calculate inventory, forecast quantities, enforce constraints, or directly mutate domain state.
9. Human approval is mandatory before consequential inventory mutations.
10. Every mutation must be verifiable and auditable.
11. Every phase must end with tests passing or clearly documented failures.
12. Do not add realtime infrastructure, microservices, complex ML, or UI theatre unless a demonstrated requirement justifies it.

---

# 1. Target architecture

```text
                         GROCER
                           │
             ┌─────────────┴─────────────┐
             │                           │
        CUSTOMER SIDE              OPERATIONS SIDE
             │                           │
      Replenishment Agent          Ops Dashboard
             │                           │
      Commerce Adapter             Backend APIs
             │                           │
       Swiggy MCP              ┌─────────┴─────────┐
             │                 │                   │
             └────────────── Shared Backend ───────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
        Simulation        Forecasting        Decisions
             │                 │                 │
             │              Risk Engine         │
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                        Recommendations
                               │
                         Human Approval
                               │
                           LangGraph
                               │
                           Execution
                               │
                         Verification
                               │
                           Audit/Event Log
                               │
                           Database
```

Recommended logical backend boundaries:

```text
backend/
  api/
  customer/
  operations/
  simulation/
  forecasting/
  decisions/
  agents/
  integrations/
  audit/
  database/
  tests/
```

Exact folders may differ if existing structure can be cleanly reused.

---

# 2. Implementation order

| Phase | Area | Outcome | Priority |
|---|---|---|---|
| 0 | Audit / freeze | Repository understood and baseline recorded | P0 |
| 1 | Backend state | One authoritative state model | P0 |
| 2 | Simulator | Reliable 5-store operational world | P0 |
| 3 | Forecasting | Measured demand forecasts | P0 |
| 4 | Risk engine | Stockout/spoilage risk | P0 |
| 5 | Decision engine | Ranked transfer/reorder/discount/hold recommendations | P0 |
| 6 | Approval + LangGraph | Safe human-approved execution | P0 |
| 7 | Frontend | Conventional readable operations UI | P0 |
| 8 | Customer workflow | Replenishment + commerce adapter | P1 |
| 9 | Integration / hardening | End-to-end reliability and failure handling | P0 |
| 10 | Demo / documentation | Portfolio-quality final work sample | P1 |

Do not start Phase 7 or 8 by building UI/integrations on top of unstable backend semantics.

---

# 3. Phase 0 — Repository audit and baseline

## Goal

Understand the current repository before modifying architecture.

## Inspect

At minimum:

- `GROCER_V2_MASTER_SPEC.md`
- current `IMPLEMENTATION_PLAN.md` if present
- `README.md`
- `ARCHITECTURE.md`
- `CONTEXT.md`
- `JOURNAL.md`
- `backend/`
- `frontend/`
- `tests/`
- `docker-compose.yml`
- dependency/configuration files

## Audit questions

- Which existing services are reusable?
- Where is state duplicated?
- Which frontend code performs business logic?
- Which backend APIs are authoritative?
- Does simulation time actually advance backend state?
- Are reset semantics correct?
- Are inventory totals derived from batches?
- Are existing tests actually runnable?
- Which documentation is stale?
- Which endpoints/services conflict with the master spec?

## Deliverable

Create an audit report before coding:

```text
REUSE
REFACTOR
DELETE
MISSING
RISK
TEST BASELINE
```

## Acceptance criteria

- No product architecture changes.
- No speculative rewrite.
- Existing test/runtime baseline recorded.
- Concrete file-level implementation plan produced.

---

# 4. Phase 1 — Backend as the single source of truth

## Goal

Remove competing frontend authority over operational state.

## Implement

Backend owns:

- simulation clock
- stores
- products
- batches
- inventory
- actual demand
- forecasts
- risks
- recommendations
- approvals
- transfers
- reorders
- markdowns
- audit events

Frontend obtains these through APIs.

## Required fixes

Audit and eliminate/reduce frontend-owned copies of:

- inventory
- batches
- simulation time
- demand
- transfer state
- reorder state
- markdown state
- scenario state
- authoritative risk/recommendation calculations

Fix simulation advancement so the backend actually advances time and persists resulting state.

Fix reset so the backend returns a new authoritative state and the frontend refreshes to the correct simulation/state identifier.

## Tests

- state persists across requests
- simulation time changes correctly
- reset produces a clean authoritative state
- frontend cannot create an alternate source of truth
- inventory reads agree with batch state

## Acceptance criteria

```text
Frontend → API → Backend → Database
```

There must be no competing authoritative simulator in the browser.

---

# 5. Phase 2 — Operational simulator

## Goal

Create a small, deterministic, credible simulated dark-store network.

## Locked simulation

### Stores

Five Singapore-inspired stores:

- Orchard
- Tiong Bahru
- Bugis
- Tampines
- Jurong East

These are simulation labels only.

### Products

Approximately 12–15 products.

Suggested catalog:

- Milk
- Yogurt
- Bread
- Eggs
- Bananas
- Tomatoes
- Rice
- Atta
- Cooking Oil
- Biscuits
- Coffee
- Juice

Give products different demand velocity, variability, price, and perishability.

### Batches

Perishable inventory is batch-level.

Inventory is derived from active batches:

```text
available_inventory(store, product)
= SUM(active batch quantities)
```

### Historical demand

Generate approximately 60–90 simulated historical days, adjusting if forecasting evaluation shows a better runtime/data balance.

### Demand

Controlled stochastic + scenario-driven demand.

Actual demand and forecast demand must remain separate.

### Supplier

Simulate:

- supplier lead time
- order creation
- shipment
- arrival
- optional delay/failure

### Transfer ETA

Use simulated distance plus traffic/scenario effects.

### Simulator modes

Development/live:

- pause
- +1 hour
- +6 hours
- +1 day
- reset

Scenario mode:

- normal
- demand spike
- supplier delay
- expiry wave
- network imbalance

Use a seed for deterministic reproduction.

## Invariants

Must never:

- create negative inventory
- sell expired stock
- transfer expired stock
- transfer more than source availability
- lose inventory silently
- mutate inventory without an audit/event path

## Tests

- seeded simulation reproducibility
- time advancement
- demand generation
- batch expiry
- inventory derivation
- sale consumption
- supplier arrivals
- transfer movement
- scenario behavior
- all inventory invariants

## Acceptance criteria

A clean simulator can reproduce a known scenario from seed + initial state.

---

# 6. Phase 3 — Forecasting

## Goal

Answer:

> What is likely to happen?

## Implement

Forecast at store/product level for useful horizons.

Start with the simplest credible baseline, such as the existing exponential smoothing implementation.

Evaluate before replacing it.

Forecast output should contain:

- predicted demand
- forecast horizon
- uncertainty/confidence
- model/version
- generated timestamp

Handle:

- insufficient history
- sparse demand
- anomalies
- high variability

Keep actual demand immutable as ground truth.

## Evaluation

Use simulator ground truth.

At minimum evaluate:

- MAE
- RMSE

Where useful, evaluate directional/stockout-relevant performance rather than optimizing only a generic error metric.

## Rule

Do not add Prophet or a heavier ML model unless measured results justify it.

## Tests

- forecast shape/schema
- insufficient data
- deterministic behavior where expected
- actual vs forecast separation
- confidence/uncertainty behavior
- model fallback

## Acceptance criteria

Forecasting is isolated, measurable, reproducible, and does not mutate inventory.

---

# 7. Phase 4 — Risk engine

## Goal

Answer:

> What is dangerous right now?

## Stockout risk

Use:

- current available inventory
- forecast demand
- demand rate
- time to expected stockout
- relevant lead times
- forecast uncertainty

Output severity such as:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

## Spoilage risk

For each relevant batch consider:

- quantity
- expiry time
- expected demand before expiry
- expected sell-through
- at-risk quantity

Risk must be batch-aware.

## Requirements

- deterministic
- testable
- configurable thresholds
- no state mutation
- no LLM dependency

## Tests

Cover:

- healthy inventory
- warning
- critical stockout
- near-expiry batch
- enough demand before expiry
- low/no demand before expiry
- multiple batches
- zero demand
- missing/low-confidence forecast

## Acceptance criteria

Given the same state and forecast, the risk engine produces the same result.

---

# 8. Phase 5 — Decision engine

## Goal

Answer:

> What feasible action has the best expected outcome?

## Candidate actions

Exactly four:

1. `TRANSFER`
2. `REORDER`
3. `DISCOUNT`
4. `HOLD`

## Pipeline

```text
state + forecast + risks
        ↓
generate candidates
        ↓
hard constraints
        ↓
calculate expected outcome
        ↓
score
        ↓
rank
        ↓
recommendation + alternatives
```

## Hard constraints

Examples:

- no negative inventory
- no expired batch transfer
- no transfer above source availability
- source remains above safety stock where required
- destination actually needs stock
- transfer ETA must satisfy the risk window
- supplier lead time must be respected
- valid product/store/batch
- cold-chain constraints where modeled

## Objective factors

Score candidates using a transparent combination of:

- stockout risk reduction
- spoilage reduction
- availability impact
- transfer/reorder cost
- delay/ETA
- safety-stock impact
- quantity efficiency
- expected demand response for discount

Avoid a giant opaque ML model for this layer.

## Example

```text
Orchard milk
inventory: 20
forecast: 8/hour
expected stockout: ~2.5h

Tiong Bahru milk
inventory: 100
safe excess: 40
transfer ETA: 1.5h

Supplier lead time: 8h
```

Transfer should normally rank above reorder because it can arrive before stockout while supplier replenishment cannot.

The engine must also explain why the alternatives ranked lower.

## Recommendation object

Minimum useful fields:

- recommendation_id
- risk_id
- action
- quantity
- source_store
- destination_store
- confidence
- score
- reason_codes
- rationale
- expected_impact
- alternatives
- created_at
- status

Recommendation statuses should support at least:

```text
PENDING
APPROVED
REJECTED
EXECUTED
FAILED
```

## Explainability

Every recommendation should answer:

1. What happened?
2. Why is it risky?
3. Why is this action recommended?
4. Why not the strongest alternatives?
5. What impact is expected?

## Tests

Create scenario-driven tests for:

- transfer preferred over reorder
- reorder preferred when no feasible transfer exists
- discount preferred for near-expiry excess
- hold when intervention is not justified
- source safety-stock violation
- transfer ETA too late
- insufficient stock
- expired batch
- multiple feasible candidates
- alternative ranking
- deterministic ranking/tie behavior

## Acceptance criteria

Decision engine can be tested without an LLM and produces a ranked, explainable recommendation.

---

# 9. Phase 6 — Human approval + LangGraph execution

## Goal

Safely execute approved recommendations.

## LangGraph flow

```text
load recommendation
        ↓
validate approval
        ↓
validate current state
        ↓
execute approved action
        ↓
verify resulting state
        ↓
record audit event
        ↓
finalize
```

## Critical rules

- No consequential action without backend-enforced approval.
- Agent cannot invent quantity.
- Agent cannot invent source/destination.
- Agent cannot bypass decision-engine constraints.
- Agent cannot directly become inventory truth.
- Failed execution must never be shown as success.
- Prefer idempotent execution where practical.

## Verification

After execution verify:

- source quantity decremented correctly
- destination quantity incremented correctly
- correct product
- correct batch where applicable
- correct quantity
- correct transfer/reorder/markdown status
- no negative inventory
- no invalid batch movement
- audit event created

## Failure cases

Test:

- rejected recommendation
- missing approval
- unauthorized execution
- stale recommendation
- insufficient inventory
- expired batch
- invalid target
- execution failure
- verification failure
- retry/idempotency

## Acceptance criteria

The agent is an orchestrator/executor, not the decision-maker or database authority.

---

# 10. Phase 7 — Operations frontend

## Goal

Make the system easy to understand and demo.

## UI principle

Use a conventional dashboard with low cognitive load.

**Do not build a command-center/cockpit/spatial UI.**

Recommended navigation:

```text
Dashboard
Inventory
Perishables
Transfers
Reorders
Simulation
Activity / Audit
Customer
```

## Dashboard

The dashboard answers:

> What needs attention right now?

Show:

- active high-priority risks
- recommended actions
- stockout risk
- spoilage risk
- pending approvals
- recent outcomes
- a small number of useful KPIs

## Recommendation card

Show:

- problem
- risk timing
- recommended action
- quantity
- source/destination when relevant
- why this action
- expected impact
- alternatives
- approve/reject

## Other pages

### Inventory

Readable store/product/batch views.

### Perishables

Expiry risk, batch, remaining quantity, predicted sell-through, markdown/transfer suggestions.

### Transfers

Proposed/approved/in-transit/delivered/failed transfers.

### Reorders

Supplier order state and ETA.

### Simulation

Time controls and scenario controls.

### Activity/Audit

Chronological operational events.

### Customer

Separate customer replenishment experience.

## Acceptance criteria

The UI reflects backend state rather than maintaining a competing state machine.

---

# 11. Phase 8 — Customer replenishment workflow

## Goal

Demonstrate the second GROCER workflow without mixing it with internal inventory decisioning.

## Flow

```text
household order history
        ↓
consumption/depletion estimate
        ↓
predicted runout
        ↓
customer alert
        ↓
confirm / remind / skip
        ↓
commerce adapter
        ↓
cart
        ↓
explicit confirmation
        ↓
checkout
        ↓
tracking
```

## Integration boundary

```text
Customer Agent
      ↓
CommercePort
      ↓
Swiggy MCP Adapter
      ↓
Instamart
```

Provider-specific calls must remain inside the adapter.

## Swiggy MCP safety

- Use approved access only.
- Never commit credentials/tokens.
- Never log plaintext access tokens.
- Require explicit confirmation before real checkout.
- Prefer a stub/mock adapter for development when real checkout is unsafe/unnecessary.
- Do not represent internal dark-store operations as Swiggy MCP capabilities.

## Acceptance criteria

Customer replenishment can be demonstrated independently from the operations workflow.

---

# 12. Phase 9 — Integration, testing, and hardening

## Full system test

Test the complete loop:

```text
scenario
 → detect
 → forecast
 → risk
 → candidates
 → rank
 → recommendation
 → human approval
 → agent execution
 → verification
 → outcome
 → audit
```

## Required scenario tests

### Scenario A — Stockout

```text
normal operation
→ demand spike
→ stockout risk
→ transfer/reorder candidates
→ transfer ranked best
→ human approves
→ agent executes
→ verification
→ risk decreases
```

### Scenario B — Spoilage

```text
perishable batch
→ expiry risk
→ transfer/discount/hold candidates
→ best action selected
→ human approves
→ execution
→ spoilage risk decreases
```

### Scenario C — Network imbalance

```text
one store has excess
→ another store becomes low
→ transfer candidate
→ ETA/constraint check
→ approval
→ delivery
→ inventory rebalanced
```

### Scenario D — Supplier delay

```text
supplier delay
→ reorder becomes less useful
→ alternative transfer/discount/hold considered
→ recommendation changes
```

## Failure testing

Intentionally test:

- stale recommendation
- unavailable source inventory
- expired batch
- transfer ETA too late
- supplier failure
- duplicate execution
- rejected approval
- verification mismatch
- malformed API input
- database failure where practical

## Performance

Measure before optimizing.

Priorities:

1. correctness
2. predictable API behavior
3. simulation performance
4. decision latency
5. UI responsiveness

Do not add caching or infrastructure without evidence.

---

# 13. Phase 10 — Documentation and final demo

## README

README should explain:

1. What GROCER is.
2. Why the two workflows are separate.
3. Architecture.
4. Simulator.
5. Forecasting.
6. Risk engine.
7. Decision engine.
8. Human approval.
9. LangGraph execution.
10. Swiggy MCP adapter.
11. Testing.
12. How to run locally.

## Architecture documentation

Keep:

- product architecture
- backend architecture
- decision pipeline
- agent execution pipeline
- customer integration boundary

Do not maintain contradictory diagrams.

## Demo narrative

The strongest demonstration follows:

```text
SCENARIO
   ↓
DETECT
   ↓
RECOMMEND
   ↓
EXPLAIN
   ↓
HUMAN APPROVES
   ↓
AGENT EXECUTES
   ↓
VERIFY
   ↓
SHOW OUTCOME
```

The demo should prove the system changed the simulated operational outcome, not merely display a chatbot response.

---

# 14. Agent execution protocol for Antigravity

Antigravity must not receive a prompt like:

> Build the entire GROCER v2 from the master spec.

Instead use this loop:

```text
YOU
 ↓
bounded task
 ↓
ANTIGRAVITY
 ↓
inspect repository
 ↓
propose files/diff
 ↓
implement
 ↓
run tests
 ↓
report
 ↓
YOU REVIEW
 ↓
accept/reject
 ↓
next task
```

For every implementation task, require Antigravity to report:

```text
1. What I inspected
2. What I will change
3. What I will not change
4. Why the change matches the master spec
5. Tests added/updated
6. Tests executed
7. Failures and their causes
8. Remaining risks
```

Never allow one prompt to silently redesign multiple architecture boundaries.

---

# 15. Recommended Antigravity task sequence

Use these as individual implementation prompts, not one giant prompt.

### Task 01

Audit the repository against `GROCER_V2_MASTER_SPEC.md`. Do not modify files. Produce a reuse/refactor/delete/missing report and test baseline.

### Task 02

Make backend the single source of truth. Audit and refactor frontend/backend simulation state. Fix simulation advancement/reset semantics. Do not change forecasting, decisioning, or UI design.

### Task 03

Refactor/complete the simulator: 5 stores, 12–15 products, batch inventory, historical demand, seeded stochastic demand, supplier simulation, transfer ETA, and two simulator modes.

### Task 04

Add simulator invariant tests and scenario tests. Fix all discovered state/expiry/negative-inventory defects.

### Task 05

Isolate and evaluate forecasting. Preserve the current baseline if it performs adequately. Add model evaluation, uncertainty/confidence, and tests.

### Task 06

Implement deterministic stockout and spoilage risk detection. Add threshold/edge-case tests.

### Task 07

Implement the decision engine with candidate generation, hard constraints, scoring, ranking, explanations, and alternatives for transfer/reorder/discount/hold.

### Task 08

Add recommendation persistence/schema/API and recommendation lifecycle.

### Task 09

Implement backend-enforced approval and the LangGraph execution/verification flow. Add failure/idempotency tests.

### Task 10

Implement the operations dashboard and dedicated pages against backend APIs. Remove remaining authoritative frontend business logic.

### Task 11

Implement the customer replenishment workflow and `CommercePort` abstraction. Keep it isolated from operations.

### Task 12

Implement the Swiggy MCP adapter/stub behind the commerce interface. Protect secrets and enforce explicit checkout confirmation.

### Task 13

Run full integration/failure/performance testing. Fix correctness issues before visual polish.

### Task 14

Clean stale documentation, update README/architecture diagrams, create demo seed/scenarios, and prepare final portfolio/demo material.

---

# 16. Definition of done

GROCER v2 is implementation-complete when all of the following are true:

### Architecture

- [ ] Two workflows remain logically separate.
- [ ] Modular monolith is maintained.
- [ ] Backend is the operational source of truth.
- [ ] No competing frontend simulator authority.

### Simulation

- [ ] 5 simulated dark stores.
- [ ] 12–15 products.
- [ ] Batch-level expiry.
- [ ] Actual vs forecast demand separated.
- [ ] Seeded reproducibility.
- [ ] Live/manual and scenario modes.
- [ ] Supplier and transfer simulation.

### Intelligence

- [ ] Forecasting evaluated against simulator ground truth.
- [ ] Stockout risk implemented.
- [ ] Spoilage risk implemented.
- [ ] Transfer/reorder/discount/hold candidates.
- [ ] Hard constraints enforced.
- [ ] Recommendations ranked and explainable.
- [ ] Alternatives shown.

### Agents

- [ ] Human approval required.
- [ ] Agent cannot bypass backend approval.
- [ ] Agent executes approved recommendation only.
- [ ] Verification is real and state-based.
- [ ] Failures cannot masquerade as success.
- [ ] Audit events recorded.

### Customer workflow

- [ ] Replenishment flow is separate.
- [ ] Commerce adapter exists.
- [ ] Swiggy MCP is isolated behind adapter.
- [ ] Explicit checkout confirmation exists.
- [ ] Secrets are protected.

### Frontend

- [ ] Dashboard answers what needs attention.
- [ ] Inventory/perishables/transfers/reorders/simulation/audit/customer views exist as appropriate.
- [ ] UI has low cognitive load.
- [ ] No command-center theatre.
- [ ] Backend state is reflected correctly.

### Quality

- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Failure scenarios are tested.
- [ ] Inventory invariants are tested.
- [ ] End-to-end demo scenarios work from a clean seed.
- [ ] Documentation matches the code.

---

# 17. What not to build

Do not add these unless the scope is explicitly changed:

- microservices
- complex WMS/ERP functionality
- warehouse robotics
- route optimization research
- deep ML research pipeline
- huge product catalog
- customer payment/profile systems
- unrestricted autonomous inventory mutation
- elaborate realtime/WebSocket infrastructure
- giant spatial command-center UI
- unnecessary maps
- dozens of scenarios
- generic chatbot features
- features added only to make the project look bigger

The goal is a **small but technically serious system** where the complete decision-to-execution loop is demonstrably correct.

---

# 18. Final engineering principle

The quality of GROCER is not measured by how many AI features it contains.

It is measured by whether the system can reliably demonstrate:

> **observe → predict → detect risk → generate options → enforce constraints → recommend → obtain approval → execute → verify → measure outcome.**

If a feature does not strengthen that loop, it should be questioned before implementation.
