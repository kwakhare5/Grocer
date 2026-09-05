# ARCHITECTURE.md — GROCER v2

> **Source of truth:** `GROCER_V2_MASTER_SPEC.md`
> **Status:** LOCKED consumer-commerce architecture
> **Updated:** 2026-09-06

## 1. System identity

GROCER is the **existing WhatsApp consumer grocery replenishment assistant**, extended with an intent-preservation layer.

It is not a dark-store operations platform, a generic marketplace assistant, or a second standalone agent infrastructure product.

The separate dark-store operations system lives in:

`https://github.com/kwakhare5/Dark-store-operator`

## 2. Core architecture

```text
                         WHATSAPP
                            │
                            ▼
                 CONVERSATION / AGENT LAYER
                            │
                            ▼
                      INTENT PARSER
                            │
                            ▼
                    INTENT CONTRACT
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
       POLICY / MEMORY              CLARIFICATION
             │                             │
             └──────────────┬──────────────┘
                            ▼
                  CUSTOMER COMMERCE SERVICE
                            │
                            ▼
                      COMMERCE PORT
                       /          \
                      /            \
             MOCK ADAPTER      SWIGGY MCP ADAPTER
                      \            /
                       \          /
                        ▼        ▼
                         COMMERCE STATE
                              │
                              ▼
                       INTENT VERIFIER
                              │
                 ┌────────────┴────────────┐
                 │                         │
                PASS                      FAIL
                 │                         │
                 ▼                         ▼
          APPROVAL / CONTINUE       RECOVERY ENGINE
                 │                         │
                 │                   REPLAN / SUBSTITUTE /
                 │                   REPAIR / CLARIFY
                 │                         │
                 └──────────────┬──────────┘
                                ▼
                           VERIFY AGAIN
                                │
                                ▼
                    EXPLICIT CHECKOUT APPROVAL
                                │
                                ▼
                             CHECKOUT
                                │
                                ▼
                         OUTCOME VERIFICATION
```

## 3. Architecture principles

### 3.1 Intent is the source of truth for the user's goal

The live cart can change. The `IntentContract` captures what the user actually asked for.

### 3.2 Backend is authoritative

The backend owns session state, intent, policies, commerce operations, verification, recovery state, and checkout authorization.

The frontend is a presentation/conversation surface and must not become a competing authority.

### 3.3 Deterministic enforcement beats LLM confidence

```text
LLM
  → interprets language
  → proposes actions
  → communicates

Deterministic services
  → enforce hard constraints
  → verify cart state
  → calculate totals
  → enforce authorization
  → classify failures
  → control retries
  → verify outcomes
```

### 3.4 Provider isolation

All Swiggy-specific MCP tool calls remain inside `SwiggyMCPAdapter`.

Higher layers depend on `CommercePort` rather than raw provider APIs.

## 4. Major modules

### Conversation / WhatsApp layer

Responsibilities:

- receive the user's natural-language request;
- show proactive replenishment messages;
- present recovery/clarification decisions;
- show cart and approval state;
- communicate final outcome.

It must not enforce hard commerce rules by itself.

### Intent layer

Responsibilities:

- parse goal;
- normalize requested items;
- distinguish hard constraints from soft preferences;
- capture budget, quantity, pack size, brand, dietary and substitution requirements;
- identify ambiguity;
- maintain intent versioning.

### Policy / memory layer

Responsibilities:

- store durable soft preferences;
- apply precedence rules;
- produce permitted substitution/recovery policies.

Precedence:

```text
current explicit request
    > current session choice
    > stored soft preference
    > default
```

### Customer Commerce Service

Coordinates the consumer workflow without exposing provider details upward.

It delegates commerce operations through `CommercePort`.

### CommercePort

Abstract boundary for:

- addresses;
- product discovery;
- cart reads/writes;
- payment/checkout state where supported;
- order details/tracking where supported.

Implementations currently include:

- `MockCommerceAdapter`;
- `SwiggyMCPAdapter`.

### Intent Verifier

Compares current commerce state against the intent contract after meaningful mutations and before checkout.

Outputs should distinguish:

- hard violations;
- soft preference deviations;
- unresolved items;
- budget drift;
- stale state;
- possible recovery paths.

### Recovery Engine

Consumes verifier failures and attempts a bounded path back to a valid intent state.

Initial recovery classes:

- unavailable product;
- unavailable preferred brand;
- changed pack size;
- budget drift;
- stale cart;
- safely retryable transient failure;
- partial success;
- basket-validity/minimum-order failure where policy permits repair.

### Evaluation / failure simulation

Lives at the commerce boundary and domain-test layer.

It is an internal reliability capability, not a separate product.

## 5. State model

Minimum useful conceptual state:

```text
ConversationSession
IntentContract
CommerceSnapshot
ActionAttempt
RecoveryAttempt
ApprovalState
OutcomeEvent
```

Persist only what is required to reason about the current task, debug failures, evaluate reliability, and preserve useful preferences.

Do not introduce a heavyweight event-sourcing platform without a demonstrated need.

## 6. Safety model

### Checkout

```text
cart valid
   ↓
intent verified
   ↓
explicit user confirmation
   ↓
backend authorization check
   ↓
checkout
   ↓
verify result
```

No agent prompt can bypass the backend checkout guard.

### Recovery

Automatic recovery is allowed only when:

- the action is inside the user's policy/authorization;
- hard constraints remain satisfied;
- the outcome can be verified;
- retry semantics are safe.

Otherwise the agent asks the user or terminates safely.

## 7. Failure handling

The system must distinguish:

```text
BUSINESS FAILURE
STALE STATE
TRANSIENT FAILURE
PROVIDER REJECTION
AUTH FAILURE
PARTIAL SUCCESS
UNKNOWN OUTCOME
USER AMBIGUITY
```

The adapter/domain layer normalizes raw provider behavior into stable internal semantics.

Consequential operations are never blindly retried.

## 8. Frontend architecture

The current WhatsApp/iPhone customer experience remains the primary interface.

The Intent feature should make that experience more intelligent rather than replacing it with an unrelated UI.

Use concise message states such as:

```text
NORMAL
RECOVERING
NEEDS_DECISION
AWAITING_APPROVAL
SUCCESS
FAILED
```

Do not rebuild the removed dark-store cockpit inside GROCER.

## 9. Repository boundary

### Keep and extend

- `components/customer/`
- WhatsApp demo/interaction components where they support the customer experience
- `CustomerService`
- `backend/integrations/commerce/`
- `CommercePort`
- `MockCommerceAdapter`
- `SwiggyMCPAdapter`
- commerce exceptions/models
- checkout authorization guard

### Clean or isolate

- dark-store-only routes;
- stale operations services/models;
- frontend mutations of fake operational inventory caused by customer checkout;
- documentation that claims both systems belong to GROCER.

Cleanup must be incremental and evidence-driven.

## 10. Technology posture

Use the existing Next.js + React + TypeScript frontend and Python + FastAPI backend.

Use the existing agent framework where useful. Do not introduce microservices or a new orchestration stack merely because the product is being extended.

## 11. Architectural non-goals

Do not optimize for:

- enterprise-scale distributed infrastructure;
- speculative multi-provider commerce;
- generic autonomous purchasing;
- real-world dark-store simulation;
- UI theatre;
- a giant ML planner.

The architecture exists to make one thing reliable:

> **preserve the user's intent while commerce state changes.**
