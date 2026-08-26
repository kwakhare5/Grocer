# GROCER v2 — Master Engineering Specification

> **Status:** Architecture and product source of truth  
> **Version:** 2.0  
> **Purpose:** Engineering prototype / competition submission / resume work sample  
> **Repository:** `kwakhare5/Grocer`

---

## 0. How to use this document

This document is the source of truth for GROCER v2.

AI coding agents (Antigravity, Gemini, Claude, etc.) must **implement this specification rather than inventing a new product or architecture**.

If implementation reveals a genuine technical problem or a requirement needs to change:

1. stop at the relevant boundary,
2. explain the issue,
3. propose the smallest viable change,
4. update this specification only after approval,
5. then implement.

Do not silently change the product scope, architecture, safety boundaries, or core decision logic.

### Status labels

- **LOCKED** — agreed product/architecture decision; do not change casually.
- **IMPLEMENT** — should be built.
- **SIMULATE** — intentionally simulated; must not be represented as a real integration.
- **TBD** — implementation detail not yet worth locking; choose the simplest sound option when reached and document it.
- **OUT OF SCOPE** — do not build in v2.

---

# 1. Vision

GROCER is an **AI-assisted quick-commerce inventory decision and execution system**.

It connects two sides of the same simulated quick-commerce world:

1. **Customer experience:** a WhatsApp-style proactive replenishment flow that predicts household staple depletion and lets a customer reorder with minimal friction.
2. **Operations experience:** an internal control center that predicts store-level stockout and spoilage risk, evaluates interventions, recommends the best action, and executes an approved action through a controlled agent.

The central idea is not “use an LLM for groceries.”

The central idea is:

> **Observe → Predict → Detect risk → Evaluate options → Recommend → Human approval → Agent execution → Verify → Measure outcome → Observe again.**

The system must demonstrate that this loop works end-to-end inside a realistic, controllable simulation.

---

# 2. Why v2 exists

The original GROCER prototype focused primarily on proactive household replenishment:

```text
Order history
    ↓
Consumption velocity
    ↓
Predicted depletion
    ↓
WhatsApp alert
    ↓
Customer confirmation
    ↓
Simulated order
```

That remains an important part of v2, but it is no longer the whole product.

v2 expands the same underlying idea upstream into dark-store operations:

```text
Store demand + inventory
        ↓
Forecast
        ↓
Stockout / spoilage risk
        ↓
Transfer / reorder / discount / hold
        ↓
Human approval
        ↓
Agent execution
```

This is an evolution of the original project, not a completely different product.

---

# 3. Target outcome

GROCER is being built primarily for:

- Swiggy Builder Club / builder challenges
- engineering portfolio and resume
- internship/job conversations
- potential conversations with engineers at quick-commerce/e-commerce companies
- public build-in-public demonstration

It is **not currently a SaaS product** and should not be forced into a SaaS business model.

It is an engineering prototype demonstrating applied AI engineering, simulation, decision systems, agent orchestration, full-stack implementation, and measurable outcomes.

---

# 4. Problem

Quick-commerce systems have two related inventory problems:

### Problem A — stockouts / availability

A store can be heading toward a stockout while another nearby store has excess inventory.

A supplier reorder may also be too slow to prevent the stockout.

### Problem B — perishable waste

A store can simultaneously hold excess short-shelf-life inventory that is likely to expire before being sold.

The system therefore needs to answer:

> **Should we transfer, reorder, discount, or hold?**

The interesting part is that these are not independent problems. The same inventory can be a shortage at one store and excess at another.

GROCER treats them as one decision problem.

---

# 5. Core product concept

GROCER has two connected intelligence loops.

## 5.1 Availability loop

```text
Demand
  ↓
Forecast
  ↓
Stockout risk
  ↓
Find feasible interventions
  ↓
Transfer / Reorder / Hold
  ↓
Human approval
  ↓
Agent execution
```

## 5.2 Waste loop

```text
Inventory + expiry
       ↓
Expected sell-through before expiry
       ↓
Spoilage risk
       ↓
Transfer / Discount / Hold
       ↓
Human approval
       ↓
Agent execution
```

The two loops share the same inventory, simulation, forecasting, decision, and execution infrastructure.

---

# 6. Locked scope

## 6.1 Stores

**LOCKED:** 5 simulated dark stores.

Each store has a location/coordinate so distance between stores can be calculated.

No real store addresses are required.

## 6.2 Products

**LOCKED:** approximately 20–30 products.

Categories should include a mixture of:

- dairy
- bakery
- produce
- staples
- packaged goods

Products must have different demand patterns and shelf-life characteristics.

## 6.3 Customers

**LOCKED:** approximately 20–30 simulated customers.

## 6.4 Historical data

The simulator should generate enough historical order data to support meaningful forecasting.

**Target:** approximately 60–90 simulated historical days.

Exact amount is **TBD** based on model performance and runtime.

## 6.5 Main operator actions

Exactly four v2 decision actions:

1. **TRANSFER**
2. **REORDER**
3. **DISCOUNT**
4. **HOLD**

## 6.6 Transfer limitation

**LOCKED:** v2 supports one source store → one destination store for a transfer recommendation.

The data model may be extensible for multi-source transfers later, but multi-source optimization is out of scope for v2.

## 6.7 Customer interface

**LOCKED:** simulated WhatsApp experience inside the web application.

No real WhatsApp API is required.

## 6.8 Platform integrations

**LOCKED:** all platform, dark-store, supplier, checkout, payment, and WhatsApp integrations are simulated/mocked.

No real company credentials or private data are required or requested.

---

# 7. Non-goals / out of scope

Do not build:

- a standalone B2C grocery marketplace
- a real payment system
- real quick-commerce checkout integration
- real Swiggy/Blinkit/Zepto/BigBasket APIs
- real customer data ingestion
- production WhatsApp integration
- warehouse robotics
- smart pantry hardware
- barcode scanning
- manual pantry logging
- voice-note NLP
- a generic AI chatbot
- RAG/vector database purely because the project uses AI
- autonomous consequential inventory changes without approval
- Kubernetes/microservice infrastructure for the sake of appearing enterprise-grade
- Kafka solely for architecture theatre
- reinforcement learning unless a later validated requirement makes it necessary
- multi-source transfer optimization in v2
- a SaaS billing/multi-tenant layer

Optional recipe and commodity-price modules from the original prototype are **not core to v2** and should not distract from the inventory intelligence system.

---

# 8. Product architecture

```text
                         GROCER
                           │
             ┌─────────────┴─────────────┐
             │                           │
       CUSTOMER SIDE                OPERATIONS SIDE
       WhatsApp Demo                Control Center
             │                           │
             └─────────────┬─────────────┘
                           │
                    SHARED BACKEND
                           │
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
   Simulation         Intelligence        Execution
        │                  │                  │
        │          ┌───────┼────────┐         │
        │          ↓       ↓        ↓         │
        │      Forecast   Risk   Decision      │
        │                         Engine       │
        │                           │          │
        └───────────────────────────┼──────────┘
                                    ↓
                              Recommendation
                                    ↓
                              Human Approval
                                    ↓
                              LangGraph Agent
                                    ↓
                                  Tools
                                    ↓
                              State mutation
                                    ↓
                               Verification
                                    ↓
                                  Events
                                    ↓
                               New state
```

---

# 9. Architecture style

**LOCKED:** modular monolith.

Do not split the prototype into independent microservices.

The backend is one application with strong internal module boundaries.

Recommended shape:

```text
Next.js
   ↓
FastAPI
   ↓
Domain/service modules
   ↓
PostgreSQL
```

LangGraph operates inside the backend process/application boundary and calls controlled backend tools.

---

# 10. Technology stack

## Frontend

- Next.js
- React
- TypeScript
- existing project styling stack may be retained where practical

The existing repository already uses Next.js/React/Tailwind. Reuse working infrastructure instead of rewriting it without reason.

## Backend

- Python
- FastAPI

## Database

- PostgreSQL

## AI agent

- LangGraph
- configurable LLM provider/model

## ML

- Python
- lightweight statistical/time-series tooling
- scikit-learn where useful
- forecasting library chosen after baseline comparison

Prophet may be used, but **Prophet is not a product requirement**. Model choice should follow measured performance and implementation simplicity.

## Realtime

- WebSockets

## Local environment

- Docker Compose preferred for reproducible local development

---

# 11. AI engineering philosophy

GROCER must not become an “LLM wrapper.”

The system has four different responsibilities:

```text
ML
→ predicts what is likely to happen

Deterministic domain logic
→ calculates risk and feasible actions

Decision engine
→ ranks possible actions

LLM / agent
→ orchestrates approved execution and handles communication/recovery
```

The LLM must not be the source of truth for inventory quantities, expiry calculations, forecasts, constraints, or database mutations.

---

# 12. ML / forecasting scope

**LOCKED:** moderate ML depth.

The goal is enough ML depth to demonstrate competent applied forecasting without turning the project into an ML research thesis.

## 12.1 Forecasting levels

### Level 1 — baseline

Use recent demand statistics such as moving averages or similar simple baselines.

### Level 2 — time-series model

For products with enough data and useful temporal patterns, use a lightweight time-series model such as Prophet or another suitable model.

### Level 3 — deterministic business calculations

Some predictions do not need ML.

For example:

```text
inventory = 80
expected demand before expiry = 35

at-risk quantity = 45
```

This is domain mathematics, not an ML problem.

## 12.2 Model evaluation

Forecasting must be evaluated against known simulator ground truth.

Track appropriate metrics such as:

- MAE
- RMSE
- MAPE where appropriate

Do not present simulator accuracy as real-world company accuracy.

## 12.3 Confidence

Confidence should combine factors such as:

- forecast uncertainty
- amount/quality of historical data
- consistency of demand
- anomaly rate

The old fixed `0.85` threshold is **not automatically retained**.

Thresholds should be configurable and justified as prototype policy choices.

## 12.4 Anomalies

The forecasting pipeline should be able to exclude or reduce the influence of unusual events such as:

- bulk/guest purchase spikes
- travel/gaps
- simulator-generated abnormal events

The exact detection algorithm is **TBD**; start simple and test it.

---

# 13. Inventory model

Inventory is store-specific and product-specific.

Perishable inventory is batch-aware.

Example:

```text
Store 02
Milk

Batch A
20 units
expires in 8h

Batch B
45 units
expires in 3 days
```

This allows GROCER to distinguish total inventory from inventory that is actually at risk of expiry.

---

# 14. Decision Engine

The Decision Engine is the core deterministic decision layer.

Pipeline:

```text
Current state
   ↓
Forecast demand
   ↓
Calculate risks
   ↓
Generate feasible actions
   ↓
Apply hard constraints
   ↓
Score feasible actions
   ↓
Rank actions
   ↓
Generate recommendation + alternatives
```

## 14.1 Transfer

Prefer transfer when:

- destination stockout risk is high
- source has safe excess
- transfer can arrive before stockout
- source remains above safety stock
- destination actually needs the quantity
- transfer distance/time is reasonable

## 14.2 Reorder

Prefer reorder when:

- supplier can deliver in time
- multiple stores need replenishment
- no suitable source store has enough excess
- transfer is not feasible/economical

## 14.3 Discount

Prefer discount when:

- product is perishable
- expiry is approaching
- inventory exceeds expected sell-through before expiry
- accelerated sales are preferable to spoilage

Initial prototype discount tiers may be:

```text
>24h remaining   → 0%
12–24h           → 10%
6–12h            → 20%
<6h              → 30%
```

These are simulator policy defaults, not real pricing claims.

## 14.4 Hold

Hold is a legitimate decision.

Use it when intervention is unnecessary or harmful.

Example:

```text
inventory healthy
expiry distant
supplier reliable
stockout risk low

→ HOLD
```

---

# 15. Transfer logic

## 15.1 Safe excess

A source store cannot transfer inventory if doing so creates an unacceptable risk at the source.

Conceptually:

```text
safe_excess = current_inventory
              - expected_demand_during_safety_window
              - safety_buffer
```

The exact safety window and buffer are configurable simulator policies.

## 15.2 Candidate sources

The system may evaluate multiple candidate source stores.

Example:

```text
Store 02
20 transferable
2 km

Store 03
40 transferable
7 km
```

The decision engine compares them using the configured policy.

## 15.3 Hard transfer constraints

Reject a transfer if:

- source inventory is insufficient
- source would fall below safety stock
- destination does not need the product
- transfer cannot arrive before the critical window
- product is non-transferable under the simulator rules
- distance/time exceeds configured limits
- cold-chain requirement cannot be satisfied for applicable perishables

---

# 16. Decision scoring

v2 uses a **hybrid architecture**:

- start with transparent weighted scoring
- keep the interface replaceable so a real optimization solver can be introduced later

Conceptually:

```text
score =
    stockout_risk_reduction * weight
  + spoilage_reduction * weight
  + availability_improvement * weight
  - transfer_cost * weight
  - supplier_delay * weight
  - distance_penalty * weight
  - source_risk * weight
```

Weights must be configuration, not scattered magic numbers.

The exact numerical weights are **TBD** and must be calibrated against simulator scenarios rather than chosen to force a desired demo result.

The engine must preserve:

- selected action
- score
- alternatives
- structured reason codes
- relevant input facts

This makes the recommendation explainable and testable.

---

# 17. Recommendation object

A recommendation represents what GROCER currently believes should happen.

Conceptual structure:

```text
recommendation_id
risk_id
recommended_action
quantity
source_store
 destination_store
confidence
score
reason_codes
alternatives
created_at
status
```

Example reason codes:

```text
HIGH_STOCKOUT_RISK
SOURCE_HAS_SAFE_EXCESS
SUPPLIER_TOO_SLOW
LOW_TRANSFER_DISTANCE
HIGH_SPOILAGE_RISK
DISCOUNT_CAN_ACCELERATE_SELL_THROUGH
NO_SAFE_TRANSFER_SOURCE
```

The UI translates reason codes into readable explanations.

The LLM must not invent these underlying facts.

---

# 18. Human-in-the-loop policy

**LOCKED:** consequential inventory mutations require human approval in v2.

Approval required for:

- TRANSFER
- REORDER
- DISCOUNT

Read-only operations do not require approval:

- inspect inventory
- inspect batches
- calculate forecast
- inspect risks
- compare alternatives
- retrieve simulation state

The backend must enforce approval requirements.

Do not rely on an LLM system prompt to enforce this.

---

# 19. LangGraph agent

The agent executes an already-approved action.

It is not the primary inventory decision-maker.

Recommended graph:

```text
Approved recommendation
        ↓
1. Validate
        ↓
2. Pre-check
        ↓
3. Execute
        ↓
4. Verify
        ↓
Success? ────────────────┐
  │ yes                  │ no
  ↓                      ↓
5. Finalize          6. Recover
  │                      ↓
  └──────────────→ Recalculate alternatives
                         ↓
                    Human review required
                         ↓
                       Audit
```

The exact LangGraph node implementation is **TBD**, but the safety boundary is locked.

## 19.1 Agent autonomy level

**LOCKED:** Level 2.

The agent may:

- inspect state
- call read tools
- validate approved actions
- execute the exact approved action
- detect failures
- gather information
- trigger recalculation
- prepare a new recommendation

The agent may **not** autonomously execute a newly consequential action after the world changes.

A newly recommended action requires fresh human approval.

---

# 20. Agent tools

Initial controlled tools may include:

```text
get_recommendation()
get_inventory()
get_batch_details()
get_store_capacity()
find_nearby_excess()
validate_transfer()
create_transfer()
validate_reorder()
create_reorder()
apply_discount()
get_simulation_state()
recalculate_options()
log_event()
```

Tool access must be permission-aware.

Mutation tools must validate the approval state server-side.

The agent must never receive unrestricted SQL/database access.

---

# 21. Failure handling

A key design principle:

> **Retry technical failures; recalculate when the world has changed.**

Example technical failure:

```text
API timeout
    ↓
retry safely
```

Example state failure:

```text
approved transfer: 20
source inventory changed: only 12 available
    ↓
old recommendation is stale
    ↓
stop
    ↓
recalculate
    ↓
new recommendation
    ↓
human approval required
```

Do not blindly retry stale business decisions.

---

# 22. Customer / WhatsApp flow

The existing proactive replenishment concept remains part of v2.

Flow:

```text
Customer order history
       ↓
Consumption forecast
       ↓
Predicted depletion
       ↓
WhatsApp-style alert
       ↓
Confirm / Remind / Skip
```

Confirm:

```text
Confirm
 ↓
Build cart
 ↓
Check simulated availability
 ↓
Simulated order
 ↓
Inventory changes
```

Remind:

```text
schedule simulated reminder
```

Skip:

```text
record customer decision
```

The customer simulation and operations simulation must use the same underlying world.

---

# 23. Simulator

The simulator is a first-class component, not fake data pasted into the UI.

It provides:

- historical orders
- current inventory
- batches/expiry
- supplier deliveries
- demand variation
- store imbalance
- demand spikes
- supplier delays
- spoilage opportunities
- execution failures
- ground truth for model evaluation

## 23.1 Modes

### Controlled Simulation

For development and debugging.

Controls:

- advance time
- trigger demand spike
- trigger supplier delay
- create excess inventory
- create store imbalance
- force execution failure
- reset

### Scenario Mode

For demonstrations.

A scenario creates a realistic sequence of events automatically.

---

# 24. Simulation time

**LOCKED:** simulation supports both automatic and manual time control.

Controls:

```text
▶ Run
⏸ Pause
+1h
+6h
+24h
Reset
```

Scenario mode can automatically advance time.

## 24.1 Deterministic seeds

Every simulation can have a seed.

Example:

```text
Scenario: Store Imbalance
Seed: 48291
```

Same seed + same configuration should produce reproducible results.

Developer mode can use different seeds to explore variability.

---

# 25. Hero scenario

The primary demo should demonstrate the complete closed loop.

Example:

```text
NORMAL OPERATIONS
        ↓
Demand spike
        ↓
Store 04 stockout risk rises
        ↓
Store 02 develops safe excess
        ↓
GROCER detects risk
        ↓
Decision engine evaluates:
  Transfer
  Reorder
  Discount
  Hold
        ↓
Transfer ranked highest
        ↓
Operator opens WHY
        ↓
Operator approves
        ↓
LangGraph validates
        ↓
Agent executes
        ↓
Transfer verified
        ↓
Inventory changes
        ↓
Risk falls
        ↓
Before vs After metrics
```

This should be possible to demonstrate in roughly 2–3 minutes.

---

# 26. Second major scenario — perishables

Example:

```text
Store 01
Bread inventory = 80
Expiry = 8h
Expected sales before expiry = 30
```

GROCER calculates:

```text
~50 units at risk
```

It evaluates:

- transfer to another store
- discount
- hold

It recommends the lowest-risk feasible intervention.

The result should show:

```text
inventory rescued / sold
vs
simulated spoilage avoided
```

---

# 27. Optional failure scenario

A strong secondary demo should show:

```text
GROCER recommends transfer
        ↓
human approves
        ↓
source inventory unexpectedly changes
        ↓
agent pre-check fails
        ↓
agent does NOT execute stale action
        ↓
recalculate alternatives
        ↓
new recommendation
        ↓
human approval required
```

This demonstrates that the agent is not simply a happy-path automation script.

---

# 28. Baseline vs GROCER

The simulator must support comparison between:

### Baseline

A simple non-GROCER inventory policy.

### GROCER

Forecasting + risk detection + decision engine + approved execution.

Metrics may include:

- stockout events
- spoiled units
- emergency reorders
- service level / availability
- excess inventory
- transfer count
- estimated simulated waste/cost
- recommendation acceptance rate

All numbers are **simulation results**, not real-world company claims.

The baseline must be reasonably fair; do not tune it to make GROCER look artificially good.

---

# 29. Core data model

The initial model contains approximately 15 core entities.

```text
Company
Store
Product
Customer
Order
OrderItem
Supplier
Inventory
Batch
Forecast
Risk
Recommendation
Action
Event
Simulation
Scenario
```

`Company` can be minimal because this is not a SaaS product.

## 29.1 Store

```text
store_id
name
latitude
longitude
operating_status
```

## 29.2 Product

```text
product_id
name
category
unit
shelf_life
base_price
supplier_id
substitution_group (optional)
```

## 29.3 Customer

```text
customer_id
name/label
home_store_id
```

Use synthetic identities only.

## 29.4 Inventory

Logical store/product inventory view.

```text
store_id
product_id
quantity
```

Actual perishable stock is batch-backed.

## 29.5 Batch

```text
batch_id
store_id
product_id
quantity
received_at
expires_at
```

## 29.6 Order

```text
order_id
customer_id
store_id
created_at
status
```

## 29.7 OrderItem

```text
order_id
product_id
quantity
price
```

## 29.8 Supplier

```text
supplier_id
name
lead_time_hours
status
```

## 29.9 Forecast

```text
forecast_id
store_id/product_id or customer/product scope
forecast_window
predicted_demand
confidence
model
created_at
```

The exact schema should normalize shared dimensions without unnecessary complexity.

## 29.10 Risk

```text
risk_id
store_id
product_id
risk_type
severity
probability
expected_time
status
created_at
```

Initial risk types:

```text
STOCKOUT
SPOILAGE
```

## 29.11 Recommendation

```text
recommendation_id
risk_id
action_type
quantity
source_store_id
 destination_store_id
score
confidence
reason_codes
alternatives
status
created_at
```

## 29.12 Action

```text
action_id
recommendation_id
action_type
approved_by
approved_at
executed_at
status
failure_reason
```

Statuses:

```text
PENDING
APPROVED
EXECUTING
COMPLETED
FAILED
CANCELLED
REJECTED
```

## 29.13 Event

```text
event_id
event_type
timestamp
entity_type
entity_id
payload
```

Examples:

```text
ORDER_CREATED
INVENTORY_CHANGED
FORECAST_UPDATED
RISK_DETECTED
RECOMMENDATION_CREATED
ACTION_APPROVED
TRANSFER_STARTED
TRANSFER_COMPLETED
TRANSFER_FAILED
```

## 29.14 Simulation

```text
simulation_id
scenario_id
seed
current_time
status
configuration
```

## 29.15 Scenario

```text
scenario_id
name
description
configuration
```

---

# 30. Event-driven internal flow

**LOCKED:** use an in-process event mechanism rather than a distributed message broker.

Example:

```text
OrderCreated
    ↓
InventoryUpdated
    ↓
Forecast/Risk recalculation
    ↓
RiskDetected
    ↓
RecommendationCreated
```

Important events must be persisted to the event/audit log.

Do not add Kafka/RabbitMQ merely to simulate enterprise architecture.

---

# 31. Backend modules

Recommended internal modules:

```text
backend/
├── api/
├── models/
├── database/
├── services/
│   ├── simulation/
│   ├── inventory/
│   ├── forecasting/
│   ├── risk/
│   ├── decision/
│   ├── recommendation/
│   ├── customer/
│   └── metrics/
├── agents/
├── tools/
└── events/
```

Exact folder layout may change if it remains modular and understandable.

---

# 32. API contract

The API is the boundary between frontend and backend.

The frontend must not access PostgreSQL directly.

The LLM must not access PostgreSQL directly.

## 32.1 Simulation

```text
POST /simulations
GET  /simulations/{id}
POST /simulations/{id}/start
POST /simulations/{id}/pause
POST /simulations/{id}/advance
POST /simulations/{id}/reset
```

## 32.2 Scenarios

```text
GET  /scenarios
POST /scenarios/{id}/run
```

## 32.3 Stores

```text
GET /stores
GET /stores/{id}
GET /stores/{id}/inventory
GET /stores/{id}/risks
GET /stores/{id}/forecasts
```

## 32.4 Products

```text
GET /products
GET /products/{id}
```

## 32.5 Recommendations

```text
GET  /recommendations
GET  /recommendations/{id}
POST /recommendations/{id}/approve
POST /recommendations/{id}/reject
```

Reject may include an optional reason.

## 32.6 Actions

```text
GET /actions
GET /actions/{id}
```

## 32.7 Events

```text
GET /events
GET /events/{id}
```

## 32.8 Customer / WhatsApp simulation

```text
GET  /customers/{id}
GET  /customers/{id}/messages
POST /customers/{id}/messages
POST /customers/{id}/reorder
POST /customers/{id}/remind
POST /customers/{id}/skip
```

Exact request/response schemas are **TBD** and must be documented before implementation of each endpoint.

---

# 33. WebSockets

Use a simulation event stream such as:

```text
WS /simulations/{id}/events
```

Events can include:

```text
INVENTORY_CHANGED
RISK_DETECTED
RECOMMENDATION_CREATED
ACTION_STARTED
ACTION_COMPLETED
ACTION_FAILED
SIMULATION_TIME_ADVANCED
```

The frontend should update without manual refresh during live simulation.

---

# 34. Frontend information architecture

The product has two main modes.

```text
CUSTOMER
   ↕ switch
OPERATIONS
```

## 34.1 Customer mode

The existing iPhone/WhatsApp-style experience should remain polished and visually close to a real mobile interaction.

Core flow:

```text
Notification
 ↓
WhatsApp conversation
 ↓
Replenishment suggestion
 ↓
Confirm / Remind / Skip
 ↓
Cart/order state
```

## 34.2 Operations mode

This is the main new interface.

It should look like an internal operations/control-center application rather than a consumer shopping app.

Recommended information hierarchy:

```text
Top bar
  simulation status / time / scenario / controls

Overview
  critical risks
  stockout risk
  spoilage risk
  inventory health

Store network
  5 stores
  map or spatial representation
  risk/excess indicators

Active recommendations
  recommendation cards
  severity
  action
  confidence
  key facts

Recommendation detail
  problem
  recommended action
  alternatives
  WHY panel
  approval controls

Activity timeline
  events
  agent execution trace

Metrics
  baseline vs GROCER
```

The final visual design should be determined in implementation with the UI agent, but this information hierarchy is locked at the product level.

---

# 35. Recommendation UI

A recommendation should look roughly like:

```text
┌─────────────────────────────────────────┐
│ HIGH STOCKOUT RISK                      │
│ Store 04 · Milk                         │
│                                         │
│ Recommended                             │
│ TRANSFER 20 units                       │
│ Store 02 → Store 04                     │
│                                         │
│ Stockout in ~14h                        │
│ Supplier ETA ~30h                       │
│ Source safe excess: 20                  │
│ Transfer distance: 2.1 km               │
│                                         │
│ [ WHY? ]        [ APPROVE ] [ REJECT ]  │
└─────────────────────────────────────────┘
```

The exact visual design is flexible.

The information must remain understandable.

---

# 36. WHY panel

Every recommendation should expose structured reasoning.

Example:

```text
WHY THIS RECOMMENDATION?

Stockout risk             91%
Predicted stockout        14h
Supplier ETA              30h
Nearby safe excess        20 units
Transfer distance         2.1 km

Recommended: TRANSFER

Reason:
• destination has high stockout risk
• supplier is too slow
• source has safe excess
• transfer can arrive in time

Alternatives:
REORDER  — lower score because supplier is slow
DISCOUNT — does not solve destination shortage
HOLD     — leaves high stockout risk
```

The facts must originate from backend decision data.

---

# 37. Activity / audit UI

Important events should be visible as a timeline.

Example:

```text
14:21:03  ORDER_CREATED
14:21:04  INVENTORY_UPDATED
14:21:05  FORECAST_UPDATED
14:21:05  RISK_DETECTED
14:21:06  RECOMMENDATION_CREATED
14:23:11  HUMAN_APPROVED
14:23:12  AGENT_STARTED
14:23:13  TRANSFER_VALIDATED
14:23:14  TRANSFER_COMPLETED
```

This is both a debugging tool and a trust feature.

---

# 38. Security boundaries

Even though this is a simulated prototype, enforce realistic boundaries.

The system must:

- use synthetic data
- avoid real credentials
- keep integrations mocked
- prevent direct LLM database access
- validate all mutation requests server-side
- require human approval for consequential actions
- validate recommendation freshness before execution
- log mutations
- keep secrets out of source control

No real customer/platform access is required.

---

# 39. Observability

The prototype should have structured logs and persistent events.

Every meaningful action should answer:

```text
WHAT happened?
WHEN?
TO WHAT entity?
WHY?
WHO/WHAT initiated it?
WHAT was the result?
```

At minimum, log:

- simulation events
- forecast runs
- risk creation/resolution
- recommendations
- approvals/rejections
- agent tool calls
- execution results
- failures

No need for a large external observability stack in v2.

---

# 40. Testing strategy

Testing is part of implementation, not a final cleanup step.

## 40.1 Unit tests

Test deterministic business logic:

- stockout calculation
- spoilage calculation
- safe excess
- transfer constraints
- discount tiers
- scoring
- recommendation generation

Example:

```text
source inventory = 50
transfer = 20

→ valid
```

```text
source inventory = 50
transfer = 60

→ rejected
```

## 40.2 Integration tests

Test:

```text
order
 → inventory change
 → event
 → forecast/risk
 → recommendation
```

and:

```text
approval
 → agent
 → tool
 → state mutation
 → verification
 → event
```

## 40.3 Agent tests

Test:

- approved action executes
- unapproved mutation is rejected
- stale recommendation is rejected
- technical failure can retry safely
- world-state change causes recalculation
- failed execution cannot silently become a new autonomous action

## 40.4 API tests

Test request validation, permissions, state transitions, and error handling.

## 40.5 Frontend/E2E tests

At minimum, verify:

- hero scenario starts
- recommendation appears
- WHY panel displays correct data
- approve flow works
- reject flow works
- agent progress is visible
- state updates after execution
- WhatsApp reorder flow works

## 40.6 Simulation tests

Verify:

- time advancement is consistent
- inventory never becomes invalid
- deterministic seeds reproduce scenarios
- scenario triggers produce expected event sequences
- failures are reproducible

Do not chase 100% coverage.

Prioritize business-critical paths.

---

# 41. Debugging and diagnosis protocol

When something breaks, do not immediately rewrite code.

Use this sequence:

```text
1. Reproduce
2. Capture seed + simulation time
3. Inspect event timeline
4. Identify first incorrect state
5. Trace responsible service/tool
6. Write a minimal failing test
7. Fix root cause
8. Re-run failing test
9. Re-run relevant regression suite
10. Re-run hero scenario
```

## 41.1 Reproducible bug report

Every meaningful bug should record:

```text
scenario
seed
simulated time
entity
expected state
actual state
last successful event
first incorrect event
```

This is particularly important when using AI coding agents.

---

# 42. AI-assisted engineering workflow

Antigravity is the primary workbench.

Gemini and Claude can be used as implementation/review agents, but **the specification remains the source of truth**.

Recommended workflow:

```text
SPEC
 ↓
PLAN
 ↓
IMPLEMENT ONE SMALL SLICE
 ↓
RUN TESTS
 ↓
DIAGNOSE
 ↓
FIX
 ↓
REVIEW
 ↓
CHECKPOINT / COMMIT
 ↓
NEXT SLICE
```

Do not ask an AI agent to generate the entire application in one shot.

---

# 43. Model usage strategy

Model choice should be based on task difficulty, context size, and measured output quality.

Suggested development roles:

| Task | Preferred model role |
|---|---|
| Architecture reasoning | Claude Opus-class model |
| Difficult implementation | Claude Sonnet-class model |
| Large routine code changes | Gemini Flash-class model |
| Routine implementation/tests | Gemini Flash-class model |
| Difficult debugging | Claude Sonnet → Opus if needed |
| Deep code review | Claude Opus-class model |
| UI implementation/iteration | Gemini + Claude Sonnet |
| Final architecture review | Claude Opus-class model |

Model names/versions available in Antigravity may change. Do not couple the application architecture to a specific vendor/model.

The important rule is **role separation, not model worship**.

---

# 44. AI agent rules for coding

Every coding agent working on GROCER should follow these rules:

1. Read this file before changing architecture.
2. Inspect existing code before replacing it.
3. Reuse working components where appropriate.
4. Do not introduce a new dependency without justification.
5. Do not create a microservice when a module is sufficient.
6. Do not put business logic in React components.
7. Do not put business truth in prompts.
8. Do not allow direct LLM → database access.
9. Do not bypass human approval.
10. Add/update tests for business logic changes.
11. Run the smallest relevant test suite after each change.
12. Run the broader regression suite at milestone boundaries.
13. Preserve reproducibility with simulation seeds.
14. Update documentation when behavior changes.
15. Do not silently modify locked product decisions.

---

# 45. Implementation plan

Implementation must happen in vertical slices so every phase produces something testable.

## Phase 0 — Repository audit

**Goal:** understand the current v1 implementation before rewriting.

Tasks:

- inspect current frontend
- inspect current simulation engine
- inspect existing mock data/types
- identify reusable UI components
- identify code that should be replaced
- create migration plan
- establish backend/frontend local development structure

Acceptance:

- current app runs
- architecture gaps documented
- v2 target structure agreed

---

## Phase 1 — Backend foundation

Build:

- FastAPI application
- PostgreSQL connection
- migrations
- core models
- health endpoint
- basic configuration
- Docker Compose local environment

Acceptance:

```text
docker compose up
```

starts the required local services and backend health check succeeds.

---

## Phase 2 — Simulator foundation

Build:

- stores
- products
- customers
- suppliers
- synthetic order generation
- inventory
- batches
- simulated time
- deterministic seed
- reset/advance controls

Acceptance:

A new simulation can generate historical data and advance time without corrupting inventory.

---

## Phase 3 — Inventory/event system

Build:

- inventory service
- batch service
- event system
- order processing
- inventory mutation rules
- audit/event persistence

Acceptance:

An order reliably changes inventory and emits the correct events.

---

## Phase 4 — Forecasting

Build:

- baseline model
- time-series model where justified
- anomaly handling
- confidence calculation
- forecast evaluation

Acceptance:

Forecasts can be generated from simulator history and evaluated against future ground truth.

---

## Phase 5 — Risk engine

Build:

- stockout risk
- spoilage risk
- risk severity
- expected timing
- risk resolution/recalculation

Acceptance:

Known simulator scenarios create the expected risks.

---

## Phase 6 — Decision engine

Build:

- candidate generation
- hard constraints
- transfer logic
- reorder logic
- discount logic
- hold logic
- configurable scoring
- alternatives
- reason codes

Acceptance:

Decision tests demonstrate that the engine selects sensible feasible actions across multiple scenarios.

---

## Phase 7 — Recommendation API + operations UI

Build:

- recommendation endpoints
- store overview
- risk views
- recommendation cards
- WHY panel
- approve/reject controls
- activity timeline

Acceptance:

An evaluator can understand a detected problem, the recommended action, the alternatives, and the reason without reading code.

---

## Phase 8 — LangGraph execution

Build:

- agent state
- graph
- tools
- approval guard
- validation
- execution
- verification
- failure recovery
- audit logging

Acceptance:

Approved actions execute correctly; stale or unapproved actions cannot mutate state.

---

## Phase 9 — Customer/WhatsApp integration

Connect the existing customer experience to the new backend/simulation world.

Acceptance:

Customer replenishment changes the same simulated inventory world visible to operations.

---

## Phase 10 — Scenarios + failure simulation

Build:

- hero scenario
- perishables scenario
- failure scenario
- scenario controls
- deterministic replay

Acceptance:

Each scenario can be reproduced with a seed and produces the expected event chain.

---

## Phase 11 — Metrics / baseline comparison

Build:

- baseline policy
- GROCER policy
- comparison metrics
- before/after visualization

Acceptance:

The simulator can compare outcomes fairly and repeatably.

---

## Phase 12 — Hardening

Run:

- full tests
- lint
- type checks
- API validation
- frontend E2E
- failure scenarios
- performance sanity checks
- security review
- architecture review

Acceptance:

No known critical bugs remain in the hero flow.

---

## Phase 13 — Demo polish

Only after the system is stable:

- visual polish
- animations
- empty/loading/error states
- responsive behavior
- demo reset
- clear scenario labels
- demo-safe deterministic state

Do not sacrifice correctness for visual polish.

---

# 46. Implementation checkpoints

Each major phase ends with a checkpoint.

Recommended commit structure:

```text
phase-0-repository-audit
phase-1-backend-foundation
phase-2-simulator
phase-3-inventory-events
phase-4-forecasting
phase-5-risk-engine
phase-6-decision-engine
phase-7-operations-ui
phase-8-agent
phase-9-customer-flow
phase-10-scenarios
phase-11-metrics
phase-12-hardening
phase-13-demo
```

Exact commit names are flexible.

The principle is that each checkpoint should leave the repository in a runnable state.

---

# 47. Review gates

Do not move to the next major phase until the previous phase passes its review gate.

## Architecture review

Check:

- module boundaries
- dependency direction
- no accidental microservices
- no business logic in UI
- no direct LLM/database access

## Logic review

Check:

- formulas
- constraints
- edge cases
- decision ranking
- recommendation explanations

## Agent review

Check:

- approval enforcement
- stale recommendation handling
- tool permissions
- failure recovery
- audit trail

## ML review

Check:

- baseline comparison
- leakage
- anomaly behavior
- evaluation metrics
- confidence interpretation

## UX review

Check:

- evaluator understands problem quickly
- recommendation is clear
- WHY explanation is readable
- approval is obvious
- system state is visible
- customer and operator modes are distinguishable

## Demo review

Check:

- hero scenario deterministic
- reset works
- no external dependencies can break demo
- failure scenario works
- metrics are generated from the simulator

---

# 48. Definition of Done

GROCER v2 is ready for public demonstration when:

- [ ] simulator runs reliably
- [ ] 5 stores exist
- [ ] approximately 20–30 products exist
- [ ] approximately 20–30 customers exist
- [ ] historical demand can be generated
- [ ] forecasts are evaluated
- [ ] stockout risk works
- [ ] spoilage risk works
- [ ] transfer recommendation works
- [ ] reorder recommendation works
- [ ] discount recommendation works
- [ ] hold recommendation works
- [ ] hard constraints work
- [ ] recommendation explanations work
- [ ] human approval is enforced
- [ ] LangGraph executes approved actions
- [ ] stale actions are blocked
- [ ] failure recovery produces a new recommendation
- [ ] event/audit timeline works
- [ ] WebSocket updates work
- [ ] customer WhatsApp flow works
- [ ] customer actions affect shared simulation state
- [ ] baseline comparison works
- [ ] hero scenario works deterministically
- [ ] perishables scenario works
- [ ] tests cover critical logic
- [ ] application can be reset/replayed
- [ ] no real integrations or credentials are required
- [ ] demo can be explained in approximately 2–3 minutes

---

# 49. What success looks like to an evaluator

An evaluator should be able to understand this sequence without a long explanation:

```text
GROCER sees what is happening
        ↓
GROCER predicts what is likely to happen
        ↓
GROCER identifies the operational risk
        ↓
GROCER evaluates possible interventions
        ↓
GROCER recommends one and explains why
        ↓
Human approves
        ↓
Agent safely executes
        ↓
System verifies the result
        ↓
Inventory/risk state changes
        ↓
We can measure whether it helped
```

That is the product story.

The technology supports that story; the story should not be buried under technology.

---

# 50. Engineering principles

## Principle 1 — Don't fake intelligence

If a calculation can be deterministic, make it deterministic.

## Principle 2 — Don't fake integrations

Clearly label all simulated integrations.

## Principle 3 — Don't fake results

Simulation metrics must come from actual simulation runs.

## Principle 4 — Don't over-engineer

A modular monolith is enough.

## Principle 5 — Keep humans in the loop

Consequential actions require approval.

## Principle 6 — Make decisions explainable

Store structured reasons and inputs.

## Principle 7 — Make failures first-class

A system that handles changed state is more credible than a perfect happy path.

## Principle 8 — Build vertical slices

Always maintain a runnable system.

## Principle 9 — Measure before claiming

Do not make real-world performance claims without real-world evidence.

## Principle 10 — AI is a component, not the architecture

Use the best model available for the task, but keep the system's truth in code and data.

---

# 51. Known TBDs

These are intentionally not locked yet:

- exact forecasting library after baseline evaluation
- exact forecasting window per product category
- exact anomaly detection algorithm
- exact confidence formula
- exact scoring weights
- exact safety-buffer policy
- exact supplier policy parameters
- exact discount optimization formula beyond initial tiers
- exact database migration tooling
- exact WebSocket event serialization
- exact frontend visual styling
- exact deployment provider
- exact LLM model/version used in final demo

These should be resolved during implementation based on evidence, not guessed upfront.

---

# 52. Final architecture summary

```text
                         ┌─────────────────────────┐
                         │       NEXT.JS UI        │
                         │                         │
                         │  Customer | Operations  │
                         └────────────┬────────────┘
                                      │
                             REST + WebSocket
                                      │
                         ┌────────────▼────────────┐
                         │       FASTAPI           │
                         │     Modular Backend     │
                         ├─────────────────────────┤
                         │ Simulation               │
                         │ Inventory                │
                         │ Forecasting              │
                         │ Risk                     │
                         │ Decision                 │
                         │ Recommendation           │
                         │ Customer                 │
                         │ Metrics                  │
                         │ Events                   │
                         └───────┬─────────┬───────┘
                                 │         │
                         ┌───────▼───┐ ┌──▼────────────┐
                         │PostgreSQL │ │  LangGraph    │
                         │           │ │  Agent        │
                         └───────────┘ └──────┬────────┘
                                              │
                                         Controlled Tools
                                              │
                                   ┌──────────▼──────────┐
                                   │ Simulated Operations │
                                   │ transfer / reorder  │
                                   │ discount / state    │
                                   └─────────────────────┘
```

And the intelligence loop remains:

```text
OBSERVE
   ↓
PREDICT
   ↓
DETECT
   ↓
DECIDE
   ↓
EXPLAIN
   ↓
HUMAN APPROVAL
   ↓
AGENT EXECUTION
   ↓
VERIFY
   ↓
MEASURE
   ↓
OBSERVE AGAIN
```

---

# 53. Immediate next action

Do **not** ask an AI coding agent to build the whole system yet.

Start with **Phase 0 — Repository Audit**.

The agent should first inspect the existing `kwakhare5/Grocer` repository, compare the current v1 implementation with this specification, identify reusable code, identify obsolete code, and produce a concrete migration plan.

Only after that review should implementation begin.

**This file is the source of truth for that process.**
