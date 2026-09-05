# GROCER v2 — Master Engineering Specification

> **Status:** Source of truth for product, architecture, implementation, testing, and demo decisions
> **Version:** 2.1
> **Updated:** 2026-09-05
> **Repository:** `kwakhare5/Grocer`
> **Primary use:** engineering portfolio, Swiggy Builders Club, internship/job work sample

---

## 0. How to use this document

This document is the **source of truth for GROCER v2**.

Antigravity, Gemini, Claude, and other coding agents must implement this specification rather than inventing a different product or architecture.

If implementation exposes a genuine technical problem:

1. stop at the affected boundary,
2. explain the problem and evidence,
3. propose the smallest viable change,
4. get approval before changing a locked product decision,
5. update this specification if the decision changes,
6. then implement.

Do not silently change scope, safety boundaries, domain rules, or the source-of-truth architecture.

### Status labels

- **LOCKED** — agreed decision; do not change casually.
- **IMPLEMENT** — required work.
- **SIMULATE** — intentionally simulated; never present it as a real integration.
- **TBD** — implementation detail can be selected by the engineer when reached; choose the simplest sound option and document it.
- **OPTIONAL** — useful only if the core system is complete.
- **OUT OF SCOPE** — do not build in v2.

---

# 1. Product definition

GROCER is an **AI-assisted quick-commerce inventory decision and execution system**.

It contains two distinct workflows under one product:

1. **Customer replenishment workflow** — predicts when a household is likely to run out of recurring groceries and provides a low-friction reorder experience.
2. **Dark-store operations workflow** — predicts store-level stockout and spoilage risk, evaluates possible interventions, recommends the best action, obtains human approval, executes the approved action through an agent, verifies the result, and records the outcome.

These workflows share backend infrastructure but **must not be merged into one confused workflow**.

The central product loop is:

```text
OBSERVE
  ↓
PREDICT
  ↓
DETECT RISK
  ↓
GENERATE OPTIONS
  ↓
CHECK CONSTRAINTS
  ↓
RANK OPTIONS
  ↓
RECOMMEND
  ↓
HUMAN APPROVAL
  ↓
AGENT EXECUTION
  ↓
VERIFY
  ↓
MEASURE OUTCOME
  ↓
OBSERVE AGAIN
```

The project is not an LLM wrapper. The intelligence is deliberately split across forecasting, deterministic domain logic, decisioning, and agent orchestration.

---

# 2. Product goals

GROCER should demonstrate:

- applied forecasting
- inventory and batch modeling
- stockout and spoilage risk detection
- transfer/reorder/discount/hold decisioning
- explainable recommendations
- human-in-the-loop AI execution
- LangGraph orchestration
- controlled simulation
- full-stack engineering
- robust testing and invariants
- measurable simulated outcomes
- safe integration boundaries for external commerce systems

The strongest demo should make it obvious that GROCER can answer:

> **What is likely to go wrong, what can we do about it, why is this the best option, and what happened after we acted?**

---

# 3. What GROCER is NOT

GROCER is not currently:

- a SaaS business
- a grocery marketplace
- a generic chatbot
- an autonomous inventory system with unrestricted mutation rights
- a deep ML research thesis
- a warehouse robotics system
- a production-grade replacement for a WMS/ERP

The project is an engineering prototype and work sample. Architecture should be credible and disciplined without adding enterprise theatre.

---

# 4. Locked product decisions

## 4.1 Stores

**LOCKED:** 5 simulated dark stores.

Stores are inspired by Singapore neighborhoods. Use recognizable neighborhood names such as:

- Orchard
- Tiong Bahru
- Bugis
- Tampines
- Jurong East

These are **simulation labels**, not representations of actual dark-store locations or operational data.

Each store needs only the location information required for distance/ETA simulation and operational display.

Do not create elaborate maps or real-world address data.

## 4.2 Products

**LOCKED:** keep the catalog intentionally minimal: approximately **12–15 products**, not 20–30.

Suggested set:

### Perishables
- Milk
- Yogurt
- Bread
- Eggs
- Bananas
- Tomatoes

### Staples
- Rice
- Atta
- Cooking Oil

### Packaged / fast-moving
- Biscuits
- Coffee
- Juice

The exact final count may be adjusted slightly if required by implementation, but do not expand the catalog just to make the demo look larger.

Products should differ in demand velocity, variability, perishability, and price.

## 4.3 Customers

Use a small simulated household/customer dataset sufficient to demonstrate recurring consumption and replenishment.

Do not build a detailed customer identity/profile system. Customer records are simulation inputs, not a product in themselves.

## 4.4 Historical data

Generate enough historical demand to support forecasting.

Target: approximately 60–90 simulated historical days.

The exact amount is **TBD** based on forecast quality and runtime.

## 4.5 Main operations actions

**LOCKED:** exactly four operator decisions:

1. `TRANSFER`
2. `REORDER`
3. `DISCOUNT`
4. `HOLD`

## 4.6 Transfer scope

**LOCKED:** one source store → one destination store per transfer recommendation.

Multi-source optimization is out of scope for v2.

## 4.7 Human autonomy level

**LOCKED:** Level 2 autonomy / human-in-the-loop.

GROCER may analyze state, generate recommendations, compare alternatives, and prepare an execution plan.

A human must approve consequential inventory mutations before execution.

## 4.8 Simulation modes

**LOCKED:** two simulator modes:

1. **Development/live mode** — manually advance time using controls such as +1 hour, +6 hours, +1 day, pause, and reset.
2. **Scenario mode** — run controlled realistic scenarios for demonstrations.

Do not build dozens of scenarios. A small number of strong scenarios is preferred.

## 4.9 Demand model

**LOCKED:** controlled stochastic + scenario-driven demand.

Normal demand should contain bounded randomness. Scenarios can introduce controlled events such as:

- demand spike
- weekend/morning surge
- supplier delay
- expiry wave
- network imbalance

The simulator must remain deterministic/reproducible when a seed is supplied.

## 4.10 Transfer ETA

**LOCKED:** transfer ETA is based on simulated distance plus traffic/scenario effects.

Do not claim real logistics ETA accuracy.

## 4.11 Supplier simulation

**LOCKED:** suppliers are simulated.

Supplier lead time, order creation, shipment, arrival, and failure/delay behavior may be modeled simply.

## 4.12 Markdown simulation

**LOCKED:** markdown affects simulated demand.

Use a simple configurable demand-response/elasticity model. The numbers are simulation assumptions, not real market claims.

## 4.13 Batch-level expiry

**LOCKED:** perishable inventory is batch-aware.

Expiry decisions must operate on batches, not only aggregate SKU totals.

---

# 5. Two workflows

## 5.1 Customer replenishment workflow

Objective:

> Predict when a household is likely to run out of a recurring grocery and make replenishment frictionless.

Conceptual flow:

```text
Household order history
        ↓
Consumption / depletion estimate
        ↓
Predicted stockout/depletion time
        ↓
Customer alert
        ↓
Confirm / Remind / Skip
        ↓
Commerce integration
        ↓
Cart
        ↓
Explicit customer confirmation
        ↓
Checkout
        ↓
Tracking
```

This workflow should remain clearly separated from dark-store internal operations.

### External commerce integration

**LOCKED ARCHITECTURE:** the customer workflow must use an integration adapter so the commerce provider can be swapped.

Swiggy MCP is the preferred real integration when the user's approved access is available and safe to use.

The integration layer must not leak provider-specific tool calls throughout the domain code.

Conceptually:

```text
Customer Agent
     ↓
CommercePort
     ↓
Swiggy MCP Adapter
     ↓
Instamart tools
```

### Safety

Real checkout must never happen accidentally during development.

The application must require explicit user confirmation before a consequential checkout action. Production credentials/tokens must never be committed, logged, or exposed to the frontend.

If real production checkout cannot be safely exercised, use a stub/mock adapter for development and demonstrate the adapter boundary.

## 5.2 Operations workflow

Objective:

> Help dark-store operations decide when to transfer, reorder, discount, or hold inventory before stockouts and spoilage happen.

Conceptual flow:

```text
Inventory + demand
        ↓
Forecast
        ↓
Risk engine
        ↓
Decision engine
        ↓
Ranked recommendations
        ↓
Human approval
        ↓
LangGraph execution
        ↓
Verification
        ↓
Audit event
```

The customer workflow does not directly control internal store inventory.

---

# 6. Target architecture

```text
                              GROCER
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
             CUSTOMER                       OPERATIONS
                  │                             │
          Replenishment UI                Ops Dashboard
          / WhatsApp Demo                  / Control UI
                  │                             │
                  └──────────────┬──────────────┘
                                 │
                           SHARED BACKEND
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
    Customer Domain         Operations Domain         Simulation
        │                        │                        │
        │                 Forecasting                 Scenarios
        │                 Risk Engine                 Clock
        │                 Decision Engine             Demand
        │                        │                    Suppliers
        │                        │                    Transfers
        │                        │
        └──────────────┬─────────┴──────────────┐
                       │                        │
                 Integration Layer         Agent Layer
                       │                        │
                 Swiggy MCP adapter        LangGraph
                       │                        │
                       │                  Controlled tools
                       │                        │
                       └──────────────┬─────────┘
                                      ↓
                                Domain services
                                      ↓
                                  Database
                                      ↓
                               Audit / events
```

### Critical architectural rule

The backend is the **single source of truth** for simulation time, inventory, forecasts, risks, recommendations, approvals, actions, and resulting state.

The frontend must never maintain a competing authoritative inventory/simulation state.

Bad:

```text
Frontend simulator ──┐
                     ├── competing truth
Backend simulator ───┘
```

Correct:

```text
Frontend
   ↓
API
   ↓
Backend domain services
   ↓
Database / simulation state
```

---

# 7. Architecture style

**LOCKED:** modular monolith.

Do not split GROCER into microservices.

The project is small enough that microservices would add operational complexity without improving the core demonstration.

Recommended backend boundaries:

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

The exact directory structure may reuse the current repository where practical. Refactor incrementally rather than rewriting working code without reason.

---

# 8. Technology stack

## Frontend

- Next.js
- React
- TypeScript
- Tailwind/current working styling stack
- Recharts or existing charting infrastructure where useful

## Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic where appropriate

## Database

**TBD:** retain the simplest reliable database configuration for local development. PostgreSQL is preferred for the final architecture, but SQLite may remain useful for fast local tests if the repository's test architecture supports it cleanly.

Do not introduce database complexity merely for appearances.

## Agent

- LangGraph
- configurable LLM provider/model

Model selection is **not locked**. Choose based on reliability, tool use, latency, cost, and implementation results rather than brand preference.

## Forecasting

- Python statistical/time-series tooling
- lightweight models first
- scikit-learn where useful

Prophet is optional. The current repository uses exponential smoothing; retain it if it performs adequately. Do not force Prophet into the project simply because the original concept mentioned it.

## Realtime

**TBD:** use polling or lightweight server-sent updates unless true WebSocket behavior is actually needed. Do not build realtime infrastructure for theatre.

## Local environment

- Docker Compose where useful
- reproducible seed data
- environment variables for secrets

---

# 9. Responsibility boundaries

This separation is fundamental.

## Forecasting

Answers:

> What is likely to happen?

Examples:

- expected demand in next 6h
- expected demand before batch expiry
- expected stockout time

## Risk engine

Answers:

> What is dangerous right now?

Examples:

- high stockout risk
- high spoilage risk
- supplier-delay risk

## Decision engine

Answers:

> What feasible action has the best expected outcome?

It must compare transfer, reorder, discount, and hold where applicable.

## LLM / agent

Answers:

> How do I orchestrate tools, approval, execution, communication, and recovery?

The agent must not invent inventory facts or override hard domain constraints.

## Database

Answers:

> What is the current authoritative state?

---

# 10. Data model

The model should remain minimal but complete enough to support the decision loop.

## 10.1 Store

Important fields:

- id
- name
- neighborhood/location
- coordinates or distance model input
- operating status

Do not add unnecessary organizational metadata.

## 10.2 Product

Important fields:

- id
- name
- category
- unit
- brand
- perishable flag
- shelf life
- selling price
- supplier reference

Brand exists mainly to support future substitution/alternative reasoning. Do not build a full catalog marketplace.

## 10.3 Batch

Important fields:

- id
- product_id
- store_id
- quantity
- received_at
- expiry_at
- status

Batches are the source of truth for physical inventory.

## 10.4 Inventory

Do not maintain contradictory independent totals.

For a product/store pair:

```text
available inventory = sum(active batch quantities)
```

If a cached aggregate is introduced for performance, it must be derived/validated against batches and must not become a second independent truth.

## 10.5 Customer order / demand record

For the operations simulator, keep this minimal:

- timestamp
- store
- product
- quantity

No payment, rider, address, or customer-profile complexity is required.

## 10.6 Demand

Keep **actual demand** separate from **forecast demand**.

Actual demand is simulator ground truth.

Forecast demand is a model output.

Never overwrite actual data with predictions.

## 10.7 Forecast

Important fields:

- store/product scope
- forecast window
- predicted demand
- uncertainty/confidence information
- model/version identifier
- generated_at

## 10.8 Transfer

Important fields:

- id
- source_store
- destination_store
- product
- quantity
- requested_at
- ETA
- status
- transport cost
- source/destination batch information where required

Statuses:

```text
PROPOSED
APPROVED
IN_TRANSIT
DELIVERED
FAILED
CANCELLED
```

## 10.9 Reorder

Important fields:

- id
- store
- product
- quantity
- supplier
- created_at
- ETA
- cost
- status

Statuses:

```text
PROPOSED
APPROVED
ORDERED
IN_TRANSIT
DELIVERED
FAILED
CANCELLED
```

## 10.10 Markdown

Important fields:

- id
- store
- product
- batch
- discount percentage
- start_at
- end_at
- status

Applying a markdown affects simulated demand according to the configured demand-response model.

## 10.11 Recommendation

Recommendation is a first-class object.

It should answer:

1. What is wrong?
2. What should we do?
3. Why?
4. What is the expected impact?
5. What alternatives were considered?
6. Why were alternatives not preferred?

Important fields:

- id
- risk_id
- recommended action
- quantity
- source store if applicable
- destination store if applicable
- score
- confidence
- reason codes
- alternatives
- expected impact
- status
- created_at

## 10.12 Approval

Important fields:

- recommendation/action reference
- approver
- decision
- timestamp
- optional reason

The backend must enforce approval requirements.

## 10.13 Audit/event log

Record important state transitions, including:

```text
FORECAST_UPDATED
RISK_DETECTED
RECOMMENDATION_CREATED
RECOMMENDATION_APPROVED
RECOMMENDATION_REJECTED
TRANSFER_STARTED
TRANSFER_COMPLETED
TRANSFER_FAILED
REORDER_CREATED
REORDER_COMPLETED
MARKDOWN_APPLIED
BATCH_EXPIRED
SIMULATION_ADVANCED
```

Audit data should be append-oriented and useful for debugging and demos.

## 10.14 Simulation state

Important fields:

- simulation id
- current simulation timestamp
- random seed
- mode
- active scenario
- status

The frontend must retrieve this state from the backend.

---

# 11. Forecasting system

## 11.1 Goal

Forecast demand well enough to support decision-making inside the simulator.

The project does not need state-of-the-art forecasting.

## 11.2 Baseline first

Always compare against a simple baseline such as:

- moving average
- exponential smoothing

Do not assume a more complex model is better.

## 11.3 Model selection

Select the model using simulator validation data.

Useful metrics:

- MAE
- RMSE
- MAPE when appropriate

Model performance should be documented by product/store/scenario where useful.

Do not present simulator metrics as real-world quick-commerce accuracy.

## 11.4 Confidence

Confidence should reflect:

- forecast uncertainty
- historical data volume
- demand consistency
- anomaly rate

The old fixed `0.85` confidence gate is **not locked**.

Thresholds must be configurable and justified as prototype policies.

## 11.5 Anomalies

The pipeline should reduce the impact of abnormal observations when appropriate.

Potential simulated anomalies:

- unusually large purchase
- abnormal surge
- gaps in demand
- scenario-generated events

Start with the simplest robust method. Do not build a complicated anomaly-detection research system.

---

# 12. Risk engine

The risk engine converts state + forecasts into operational risk.

## 12.1 Stockout risk

Inputs may include:

- current available inventory
- demand rate
- forecast demand
- forecast uncertainty
- supplier lead time
- transfer ETA
- safety stock

Conceptually:

```text
stockout_time ≈ inventory / expected_demand_rate
```

The actual implementation should account for forecast windows and safety buffers rather than relying on one simplistic ratio.

## 12.2 Spoilage risk

Inputs include:

- batch quantity
- hours until expiry
- expected demand before expiry
- sell-through rate
- possible markdown effect
- possible transfer destination demand

Conceptually:

```text
at_risk_quantity = max(
    0,
    batch_quantity - expected_sell_through_before_expiry
)
```

## 12.3 Severity

Risk severity should be configurable and based on measurable factors.

Avoid arbitrary thresholds that exist only to create dramatic demos.

---

# 13. Decision engine

The Decision Engine is the core deterministic intelligence layer.

Pipeline:

```text
CURRENT STATE
     ↓
FORECAST / RISK
     ↓
GENERATE CANDIDATE ACTIONS
     ↓
APPLY HARD CONSTRAINTS
     ↓
CALCULATE EXPECTED OUTCOMES
     ↓
SCORE / RANK
     ↓
RECOMMEND BEST ACTION + ALTERNATIVES
```

## 13.1 Candidate actions

For each relevant risk, consider applicable actions from:

- TRANSFER
- REORDER
- DISCOUNT
- HOLD

Not every action is valid for every situation.

## 13.2 Hard constraints

Hard constraints must be checked before scoring.

Examples:

- source cannot transfer more than available quantity
- source cannot fall below configured safety threshold
- expired product cannot be transferred
- destination must have a genuine need
- transfer must arrive before the critical stockout window when transfer is being proposed as the solution
- supplier cannot deliver before its simulated minimum lead time
- quantity cannot be negative
- action cannot mutate state without required approval

A candidate violating a hard constraint is infeasible, not merely lower-scoring.

## 13.3 Transfer reasoning

Transfer is attractive when:

- destination has meaningful stockout risk
- source has safe excess
- ETA beats the destination critical window
- transfer cost is acceptable
- the transferred quantity is useful
- applicable expiry/cold-chain constraints are satisfied

Quantity should be optimized/configured, not hardcoded as a fixed arbitrary amount.

Example:

```text
Destination:
stockout in 3.4h

Source:
safe excess = 32 units
transfer ETA = 2.1h

→ transfer candidate is feasible
```

## 13.4 Reorder reasoning

Reorder is attractive when:

- supplier ETA is timely enough
- no safe transfer source exists
- several stores need replenishment
- transfer is infeasible or too costly

The system must model supplier lead time rather than magically adding inventory.

## 13.5 Discount reasoning

Discount is attractive when:

- inventory is perishable
- expiry is approaching
- expected sell-through is insufficient
- accelerated demand could reduce waste

Discount effects are simulator assumptions.

## 13.6 Hold reasoning

Hold is a valid decision when no intervention creates sufficient benefit.

Example:

```text
stock healthy
expiry distant
supplier normal
transfer unnecessary

→ HOLD
```

---

# 14. Decision scoring

Use a transparent hybrid approach.

### v2 approach

Start with configurable weighted scoring.

Potential components:

```text
score =
    stockout_risk_reduction
  + spoilage_reduction
  + availability_improvement
  - transfer_cost
  - supplier_delay_penalty
  - distance_penalty
  - source_risk
  - intervention_cost
```

Weights must be centralized configuration, not scattered magic numbers.

The exact weights are **TBD** and must be calibrated against scenarios.

The scoring system must not be tuned simply to make one predetermined action win every demo.

### Future extension

The decision-engine interface should be replaceable so a formal optimization solver can be introduced later if evidence justifies it.

Do not add an optimizer merely for resume buzzwords.

---

# 15. Explainability

Every recommendation must expose structured evidence.

The UI should communicate three levels:

### Why did this happen?

Example:

> Demand increased 38% above the recent baseline and the destination has only 3.4 hours of projected inventory remaining.

### Why this action?

> Tiong Bahru has 32 units of safe excess and can reach Orchard in 2.1 hours.

### Why not the alternatives?

> Supplier reorder ETA is 9 hours, which is later than the predicted stockout window.

The underlying facts must come from deterministic services.

The LLM may turn structured facts into natural language, but it must not invent them.

---

# 16. Recommendation ranking

Generate multiple feasible candidates where useful, then rank them.

The UI should normally show the top few rather than a giant decision table.

Example:

```text
1. TRANSFER 20 units       score 0.91
2. REORDER 30 units        score 0.68
3. HOLD                    score 0.14
```

The recommendation detail should expose the important alternative reasoning without overwhelming the operator.

---

# 17. Human approval and safety

**LOCKED:** human approval is mandatory for consequential inventory mutations.

Approval required for:

- TRANSFER
- REORDER
- DISCOUNT

Read-only operations do not require approval:

- inventory inspection
- batch inspection
- forecast calculation
- risk inspection
- recommendation generation
- alternative comparison

The backend must enforce this policy.

Never rely solely on an LLM prompt to prevent unauthorized mutation.

---

# 18. LangGraph agent

The LangGraph agent is an **execution/orchestration layer**, not the decision engine.

Recommended flow:

```text
LOAD APPROVED RECOMMENDATION
            ↓
VALIDATE APPROVAL + STATE
            ↓
EXECUTE CONTROLLED TOOL
            ↓
VERIFY RESULT
            ↓
FINALIZE
            ↓
WRITE AUDIT EVENT
```

The current repository already has a similar 5-node execution graph. Reuse/refactor it rather than replacing it unnecessarily.

### Agent responsibilities

The agent may:

- load an approved action
- inspect current state
- call controlled tools
- handle expected tool errors
- retry safe transient operations where appropriate
- verify execution
- produce an execution summary
- write/trigger audit events

The agent must not:

- invent quantities
- bypass approval
- violate hard constraints
- directly manipulate raw database state without domain tools
- decide inventory policy independently of the Decision Engine

---

# 19. Execution tools

Tools should represent controlled domain operations.

Examples:

```text
get_inventory
get_batches
get_forecast
get_risks
create_transfer
approve_transfer
execute_transfer
create_reorder
execute_reorder
apply_markdown
get_simulation_state
advance_simulation
verify_transfer
verify_reorder
```

The exact tool list may be simplified if a cleaner service/tool boundary is found.

Tools must enforce domain validation.

---

# 20. Verification

Verification is not optional.

For a transfer, verification should confirm at minimum:

```text
source quantity decreased correctly
 destination quantity increased correctly
correct product
correct quantity
correct batch handling
transfer status updated
inventory invariants preserved
```

For reorder:

```text
order exists
supplier/quantity correct
ETA respected
arrival changes inventory correctly
status updated
```

For markdown:

```text
correct batch targeted
discount active in intended window
demand model reflects markdown
```

A successful tool call is not automatically a successful business operation.

---

# 21. Inventory invariants

These invariants are core tests and should be enforced wherever practical.

### Invariant 1

Inventory cannot become negative.

### Invariant 2

Transfer quantity cannot exceed source available inventory.

### Invariant 3

Expired inventory cannot be transferred.

### Invariant 4

A transfer cannot leave the source below the configured safety requirement.

### Invariant 5

Supplier arrival cannot occur before its modeled lead time.

### Invariant 6

Simulation time advances only through the backend simulation service.

### Invariant 7

Frontend actions cannot directly mutate authoritative inventory state.

### Invariant 8

Consequential mutations require valid approval.

### Invariant 9

Actual demand and forecast demand remain distinct.

### Invariant 10

Every consequential action has an auditable state transition.

---

# 22. Simulator

The simulator is a major part of the project, not disposable fake data.

It must create a believable but controllable operating environment.

## 22.1 Initial state

Seed:

- 5 stores
- minimal product catalog
- product/store inventory
- multiple batches
- historical demand
- supplier configuration
- customer consumption history
- simulation clock

## 22.2 Time control

Support:

- pause
- +1h
- +6h
- +1d
- reset

The backend owns the clock.

## 22.3 Demand generation

Normal demand:

```text
base demand
+ bounded stochastic variation
+ time/weekday pattern where useful
```

Scenario demand may override or modify normal behavior.

## 22.4 Expiry

As simulation time advances, batches approach expiry and eventually expire.

Expiry must affect available inventory correctly.

## 22.5 Supplier flow

```text
order proposed
   ↓
approved
   ↓
ordered
   ↓
in transit
   ↓
ETA reached
   ↓
delivered
   ↓
inventory updated
```

## 22.6 Transfer flow

```text
proposed
   ↓
approved
   ↓
in transit
   ↓
ETA reached
   ↓
delivered
   ↓
source/destination state reconciled
```

## 22.7 Markdown flow

Markdown changes the simulated demand response while active.

Keep the model simple and configurable.

---

# 23. Scenario mode

Use a small number of high-quality scenarios.

Recommended scenarios:

## Scenario A — cross-store stockout

```text
Demand spike at Orchard
        ↓
stockout risk increases
        ↓
Tiong Bahru has safe excess
        ↓
transfer is feasible
        ↓
GROCER recommends transfer
        ↓
human approves
        ↓
agent executes
        ↓
verification
        ↓
stockout risk falls
```

## Scenario B — perishable expiry

```text
Milk batch approaching expiry
        ↓
expected sell-through is insufficient
        ↓
GROCER compares markdown / transfer / hold
        ↓
best action recommended
        ↓
human approves
        ↓
execution
        ↓
waste risk changes
```

## Scenario C — supplier delay

```text
store needs replenishment
        ↓
supplier ETA becomes too slow
        ↓
transfer becomes preferable or no action is feasible
        ↓
GROCER explains the trade-off
```

Additional scenarios are optional only after these work reliably.

---

# 24. Frontend / UX

The UI must be a **conventional, readable operational application**.

Do not build a futuristic “command center”, giant cockpit, or spatial map as the primary interface.

The operator should not spend mental effort learning the interface.

## 24.1 Primary navigation

Recommended structure:

```text
Overview
Inventory
Perishables
Transfers
Reorders
Recommendations
Simulation
Activity / Audit
Customer Replenishment
```

Exact labels may be simplified.

## 24.2 Overview page

The overview should answer:

> What needs attention right now?

Useful sections:

- stockout risks
- spoilage risks
- pending recommendations
- active transfers/reorders
- key inventory KPIs
- recent activity

## 24.3 Inventory page

A conventional filterable inventory table is appropriate here.

Show:

- store
- product
- available quantity
- risk status
- expiry information for perishables

Batch details can be opened as a secondary detail view.

## 24.4 Recommendation UI

Recommendations should be visually prominent but not overwhelming.

Each should show:

```text
Problem
Recommended action
Quantity
Why
Expected impact
Alternatives
Approval controls
```

## 24.5 Detail pages

Use tables, filters, cards, detail panels, and activity timelines where appropriate.

## 24.6 Map

A map is optional.

It is not a core requirement and should only be added if it materially improves transfer/network comprehension without increasing cognitive load.

## 24.7 Visual references

Figma and real operational software may be used as references for patterns such as:

- sidebar navigation
- KPI cards
- exception lists
- filterable tables
- detail drawers
- activity logs

References must inform usability, not become blind copies.

---

# 25. Backend API principles

APIs should be domain-oriented and predictable.

Potential groups:

```text
/api/health
/api/simulation
/api/inventory
/api/products
/api/stores
/api/forecasts
/api/risks
/api/recommendations
/api/approvals
/api/transfers
/api/reorders
/api/markdowns
/api/audit
/api/customer
```

Do not create an endpoint for every internal function.

The API should expose business capabilities rather than implementation details.

---

# 26. Current repository refactor strategy

**LOCKED:** do not throw away the existing codebase blindly.

The repository already contains useful infrastructure including:

- FastAPI
- SQLAlchemy
- forecasting service
- risk engine
- decision engine
- LangGraph agent
- simulator
- scenario engine
- transfer/reorder/markdown services
- approval flow
- audit flow
- frontend dashboard
- tests

The codebase is currently closer to a working prototype than a blank project, but some areas reflect older assumptions.

Therefore the strategy is:

```text
AUDIT
  ↓
REMOVE DUPLICATION
  ↓
FIX SOURCE-OF-TRUTH PROBLEMS
  ↓
STRENGTHEN DOMAIN RULES
  ↓
TEST INVARIANTS
  ↓
INTEGRATE CUSTOMER COMMERCE ADAPTER
  ↓
REFINE UI
  ↓
DEMO
```

Do not perform a rewrite unless a measured technical reason requires it.

---

# 27. Known repository issues to address

These were identified during the repository review and are implementation priorities.

## 27.1 Frontend simulation state duplication

The frontend currently contains simulation/business logic that overlaps with backend state.

**Required:** backend becomes authoritative. Frontend should call simulation APIs and render returned state.

Reduce `frontend/lib/scenarioEngine.ts` to presentation/helper logic or remove it when no longer needed.

## 27.2 Simulation advance bug

The current frontend advance-time flow appears to call risk evaluation rather than the authoritative simulation-advance operation.

**Required:** time controls must call the backend simulation advance endpoint/service.

## 27.3 Reset/stale simulation IDs

Resetting simulation can invalidate client-held simulation identifiers.

**Required:** reset must return the authoritative new state/id and frontend must replace stale state immediately.

## 27.4 Decision engine simplicity

Current decision scoring is too simplistic for the intended v2 demonstration.

**Required:** implement explicit candidate generation, hard constraints, expected impact, configurable scoring, ranked alternatives, and reason codes.

## 27.5 Transfer verification

Current verification appears too weak if it only checks destination inventory increase.

**Required:** validate source decrement, destination increment, product/quantity correctness, batch handling, status, and invariants.

## 27.6 Stale implementation plan

Older implementation plans may conflict with the current architecture.

**Required:** this master spec is the authoritative plan. Update/remove stale documentation that contradicts it.

## 27.7 Swiggy integration boundary

The current architecture needs a clean commerce integration adapter.

**Required:** provider-specific MCP details must remain behind the integration boundary.

---

# 28. Swiggy MCP integration

Swiggy MCP is relevant primarily to the **customer-side commerce workflow**.

It does not replace the simulated internal dark-store operations system.

The internal operations data — batch expiry, supplier inventory, inter-store transfer, internal markdown decisions, etc. — remains simulated.

## 28.1 Adapter architecture

```text
Customer replenishment logic
          ↓
CommercePort interface
          ↓
SwiggyMCPAdapter
          ↓
Swiggy Instamart MCP
```

The rest of the codebase should not directly call provider-specific MCP tools.

## 28.2 Customer flow

Conceptually:

```text
get addresses
      ↓
search products / recurring items
      ↓
update cart
      ↓
get cart
      ↓
show checkout summary
      ↓
explicit user confirmation
      ↓
checkout
      ↓
track order
```

The exact provider tool names and parameters must be read from the current official Swiggy Builders Club documentation before implementation. Do not guess MCP schemas.

## 28.3 Credential safety

- OAuth/token secrets stay server-side.
- Never commit credentials.
- Never log plaintext access tokens.
- Never expose provider credentials to the browser.
- Real checkout requires explicit confirmation.
- Development should prefer stubs/safe environments until real production calls are intentionally tested.

---

# 29. Testing strategy

Testing is a first-class deliverable.

## 29.1 Unit tests

Test independently:

- forecasting
- confidence calculation
- anomaly handling
- stockout risk
- expiry risk
- transfer candidate generation
- reorder candidate generation
- markdown calculation
- scoring
- constraint validation
- quantity calculation
- reason-code generation

## 29.2 Domain invariant tests

Explicitly test all inventory invariants in Section 21.

## 29.3 Integration tests

Test:

```text
simulation → forecast → risk → recommendation
recommendation → approval → agent → execution → verification
simulation advance → inventory/expiry/demand changes
```

## 29.4 API tests

Test success and failure paths.

Do not only test HTTP 200 responses.

## 29.5 Frontend tests

Prioritize:

- rendering real backend state
- filters
- recommendation approval/rejection
- simulation controls
- stale-state handling
- loading/error states

## 29.6 Scenario tests

Every major scenario should have a deterministic seed and expected outcome assertions.

Example:

```text
scenario: cross-store stockout
expected:
- risk becomes HIGH
- transfer candidate exists
- source constraint passes
- transfer outranks reorder
- approval required
- execution changes source/destination inventory
- verification passes
- audit events exist
```

## 29.7 Regression suite

Every bug fixed should receive a regression test where practical.

---

# 30. Debugging and diagnosis protocol

When something breaks, agents must not immediately patch symptoms.

Use:

```text
REPRODUCE
   ↓
LOCATE LAYER
   ↓
INSPECT STATE
   ↓
IDENTIFY ROOT CAUSE
   ↓
PATCH SMALLEST CORRECT LAYER
   ↓
ADD REGRESSION TEST
   ↓
RUN AFFECTED TESTS
   ↓
RUN FULL SUITE
```

For simulation bugs, log/inspect:

- simulation time
- seed
- store/product/batch
- before state
- action
- after state
- event/audit trail

For decision bugs, capture:

- risk inputs
- candidate actions
- rejected constraints
- scores
- selected recommendation

Do not hide uncertainty with arbitrary fallback behavior.

---

# 31. Code review standards

Every significant implementation change should be reviewed for:

### Correctness

Does it produce the right domain state?

### Invariants

Can it create impossible inventory states?

### Architecture

Does it respect the backend source of truth?

### Agent boundary

Does the LLM remain an orchestrator rather than a hidden business-logic engine?

### Explainability

Can the recommendation be traced to structured facts?

### Testability

Can the behavior be tested deterministically?

### Scope

Did the change add unnecessary complexity?

### Security

Are credentials, tokens, and consequential actions protected?

---

# 32. AI coding-agent workflow

Agents should work in bounded phases.

## Phase A — audit

Read relevant code and tests before modifying them.

Produce:

- current behavior
- dependencies
- contradictions
- risk areas
- exact proposed changes

## Phase B — foundation

Fix:

- backend source of truth
- simulation clock
- data model consistency
- state transitions

## Phase C — intelligence

Implement/refine:

- forecasting
- risk engine
- candidate generation
- constraints
- scoring
- recommendation explanation

## Phase D — execution

Refine:

- approvals
- LangGraph
- domain tools
- verification
- audit

## Phase E — simulation

Implement deterministic scenarios and measurable outcomes.

## Phase F — customer integration

Add the commerce adapter and Swiggy MCP integration only after the core architecture is stable.

## Phase G — frontend

Refactor UI around backend state and the conventional operational UX.

## Phase H — hardening

Run full tests, fix regressions, review security, and validate the demo path.

Agents should avoid mixing all phases in one giant change.

---

# 33. Definition of done

GROCER v2 is considered technically ready when:

- backend is authoritative for simulation state
- five-store simulation is stable
- minimal product catalog is stable
- batch expiry works
- actual vs forecast demand is separated
- forecasting has a baseline comparison
- stockout risk works
- spoilage risk works
- transfer/reorder/discount/hold candidates work
- hard constraints are enforced
- recommendations contain explanations and alternatives
- human approval is enforced server-side
- LangGraph executes approved actions
- execution is verified against actual state
- audit events are recorded
- scenario mode works deterministically
- frontend has no competing inventory truth
- core API/integration tests pass
- invariant tests pass
- customer replenishment flow works with a safe commerce adapter
- Swiggy MCP integration is isolated and safe if enabled
- no credentials are committed or leaked
- demo can be reset and reproduced reliably

---

# 34. Demo narrative

The demo should not be a tour of every feature.

It should tell one clear operational story.

## Primary demo

```text
NORMAL STATE
     ↓
DEMAND SPIKE
     ↓
FORECAST CHANGES
     ↓
STOCKOUT RISK DETECTED
     ↓
GROCER GENERATES OPTIONS
     ↓
TRANSFER vs REORDER
     ↓
BEST OPTION EXPLAINED
     ↓
HUMAN APPROVES
     ↓
LANGGRAPH EXECUTES
     ↓
VERIFICATION
     ↓
INVENTORY RECONCILES
     ↓
RISK DISAPPEARS
```

## Secondary demo

```text
PERISHABLE BATCH
     ↓
EXPIRY APPROACHES
     ↓
EXPECTED SELL-THROUGH IS LOW
     ↓
TRANSFER / DISCOUNT / HOLD COMPARED
     ↓
BEST OPTION EXPLAINED
     ↓
HUMAN APPROVES
     ↓
EXECUTION
     ↓
SPOILAGE RISK CHANGES
```

The demo should show the before/after state and measurable impact where possible.

---

# 35. Metrics for the demo

Track simulation-level outcomes such as:

- stockout events prevented
- stockout-risk hours avoided
- spoilage/waste quantity
- estimated waste reduction
- transfer count
- reorder count
- markdown count
- intervention cost
- service/availability proxy
- forecast MAE/RMSE
- recommendation acceptance rate in the demo workflow

These are **simulated metrics**.

Never imply they represent actual Swiggy/Blinkit/quick-commerce operational performance.

---

# 36. Scope control

When deciding whether to add a feature, ask:

1. Does it strengthen the core observe → predict → decide → approve → execute → verify loop?
2. Does it improve technical credibility?
3. Can it be tested reliably?
4. Does it materially improve the demo?
5. Does it justify its complexity?

If not, do not add it to v2.

Avoid:

- unnecessary microservices
- unnecessary infrastructure
- unnecessary AI models
- generic chatbot features
- decorative dashboards
- giant datasets
- complex optimization without need
- speculative integrations

---

# 37. Final architecture summary

The final mental model for GROCER is:

```text
                    GROCER
                       │
          ┌────────────┴────────────┐
          │                         │
     CUSTOMER                    OPERATIONS
          │                         │
     Replenishment            Inventory network
          │                         │
     Commerce MCP             Forecasting
          │                         │
          │                     Risk engine
          │                         │
          │                  Decision engine
          │                         │
          │                  Recommendation
          │                         │
          │                   Human approval
          │                         │
          │                    LangGraph
          │                         │
          │                     Execute
          │                         │
          │                     Verify
          │                         │
          └────────────┬────────────┘
                       │
                  Shared backend
                       │
                  Simulation + DB
                       │
                    Audit log
```

And the core operations intelligence is:

```text
DATA
 ↓
FORECAST
 ↓
RISK
 ↓
CANDIDATES
 ↓
CONSTRAINTS
 ↓
OUTCOME / COST
 ↓
RANK
 ↓
RECOMMEND
 ↓
HUMAN
 ↓
AGENT
 ↓
EXECUTE
 ↓
VERIFY
 ↓
AUDIT
```

This is the architecture GROCER v2 should be built around.

---

# 38. Immediate implementation order

The next implementation sequence is:

### 1. Repository audit + cleanup

Map current code against this spec and identify stale/duplicate code.

### 2. Backend source-of-truth refactor

Make simulation time and inventory authoritative in the backend.

### 3. Data/model consistency

Ensure batches are the inventory source of truth and all state transitions are coherent.

### 4. Simulation engine

Make time advancement, demand, expiry, suppliers, transfers, and scenarios deterministic and testable.

### 5. Forecasting + risk

Stabilize baseline forecasting and risk calculations.

### 6. Decision engine

Implement candidate generation, hard constraints, scoring, ranking, alternatives, and reason codes.

### 7. Approval + execution

Harden LangGraph tools, approval enforcement, execution, verification, and audit.

### 8. Operations UI

Refactor dashboard/pages around backend state and readable operational workflows.

### 9. Customer workflow

Implement the customer replenishment flow behind a commerce adapter; integrate Swiggy MCP safely where appropriate.

### 10. Testing + demo hardening

Run full regression/invariant/scenario suites and polish the two core demo narratives.

---

# 39. Non-negotiable principles

1. **Backend is the source of truth.**
2. **Batches are the source of truth for physical inventory.**
3. **Forecasting predicts; it does not decide.**
4. **Deterministic domain logic enforces constraints.**
5. **Decision engine ranks feasible actions.**
6. **LLM/agent orchestrates; it does not invent inventory truth.**
7. **Consequential actions require human approval.**
8. **Every consequential action is verified.**
9. **Important actions are auditable.**
10. **Customer and operations workflows remain distinct.**
11. **Simulation must be controllable and reproducible.**
12. **The UI must optimize for operator comprehension, not visual theatrics.**
13. **Complexity must earn its place.**
14. **Tests must protect domain invariants.**
15. **Real integrations must be isolated behind adapters and must never compromise safety.**

---

## End of GROCER v2 Master Engineering Specification
