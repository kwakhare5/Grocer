# CONTEXT.md — GROCER Domain Context

> **Read at the START of EVERY coding session.**
> **Authoritative product spec:** `GROCER_V2_MASTER_SPEC.md`
> **Updated:** 2026-09-06

## 1. Project identity

**GROCER is the existing WhatsApp consumer grocery replenishment assistant being extended with an Intent layer.**

It is **not** a new standalone project, not a dark-store platform, and not a generic marketplace chatbot.

```text
GROCER today
WhatsApp replenishment
        +
Swiggy Instamart CommercePort
        +
Intent preservation
        +
Verification / recovery
```

The dark-store operations project is separate:

`kwakhare5/Dark-store-operator`

### Golden rule

> **Do not reinterpret GROCER. Extend the existing WhatsApp consumer assistant.**

## 2. Canonical terms

| Term | Meaning in GROCER | Do not turn it into |
|---|---|---|
| GROCER | WhatsApp grocery replenishment and intent-preserving commerce assistant | Dark-store system / generic shopping platform |
| Intent | User's desired shopping outcome represented as structured state | Mere NLP classification |
| IntentContract | Canonical representation of goal, items, constraints, preferences, policy, and authorization | A chat prompt |
| Hard constraint | Rule that must not be silently violated | A soft suggestion |
| Soft preference | Ranking preference that may yield to stronger information | Permanent rule |
| Intent verifier | Deterministic comparison of live commerce state with user intent | LLM-only judgment |
| Recovery engine | Bounded process for restoring a valid intent state after failure/drift | Infinite retry loop |
| CommercePort | Provider-neutral commerce interface | UI checkout iframe |
| SwiggyMCPAdapter | Swiggy-specific MCP implementation behind CommercePort | Provider logic exposed everywhere |
| MockCommerceAdapter | Deterministic commerce implementation for tests/demo/failure injection | Fake production integration |
| Explicit confirmation | Backend authorization required before consequential checkout | A frontend-only button click |
| Memory | Durable soft preferences used for convenience | Authority over the current request |
| Dark-store operator | Separate companion repository | GROCER subsystem |

## 3. Product objective

The core problem is not “how do I search for groceries?”

The core problem is:

> **A user's intended shopping outcome can become invalid while the live commerce state changes. GROCER should detect that drift and preserve intent.**

Core loop:

```text
intent
→ plan
→ act
→ observe
→ verify
→ recover / ask
→ verify again
→ approve
→ checkout
→ verify outcome
```

## 4. Intent precedence

Always apply:

```text
CURRENT EXPLICIT REQUEST
    >
CURRENT SESSION CHOICE
    >
STORED SOFT PREFERENCE
    >
AGENT DEFAULT
```

Memory must never silently override an explicit current instruction.

## 5. Autonomy rules

```text
Safe + deterministic + authorized
    → AUTO-ACT

Meaningful ambiguity / multiple valid choices
    → ASK USER

Financially consequential action
    → EXPLICIT CONFIRMATION
```

Checkout always requires backend-enforced explicit confirmation.

## 6. LLM vs deterministic code

### LLM may

- understand natural language;
- extract intent candidates;
- interpret context;
- propose substitutions/recovery actions;
- choose conversational wording;
- decide when clarification is useful.

### Deterministic code must

- enforce hard constraints;
- calculate totals;
- verify current commerce state;
- enforce authorization;
- enforce retry semantics;
- validate recovery candidates;
- control state transitions;
- verify consequential outcomes.

**Never let prompt wording become the only enforcement mechanism for a critical rule.**

## 7. Existing architecture to preserve

```text
WhatsApp
  ↓
Conversation Agent
  ↓
Intent Layer
  ↓
Customer Commerce Service
  ↓
CommercePort
  ├── MockCommerceAdapter
  └── SwiggyMCPAdapter
```

Build the new Intent/Verifier/Recovery capabilities on this foundation.

Do not replace it with a parallel architecture.

## 8. Anti-drift rules

### DO NOT

- bring the dark-store inventory/operations product back into GROCER;
- add stores, suppliers, warehouse flows, stock transfers, replenishment POs, discounts, batch optimization, or operations dashboards;
- build a generic “shop anything anywhere” agent as the primary product;
- create a second commerce abstraction beside `CommercePort`;
- spread Swiggy MCP calls through domain code;
- move business authority into React/Next.js;
- let the LLM bypass deterministic verification;
- allow autonomous checkout without explicit confirmation;
- invent Swiggy MCP tool names or arguments;
- build evaluation as a detached product instead of a GROCER reliability subsystem;
- rewrite working code just to fit a preferred framework.

### DO

- extend the current WhatsApp replenishment experience;
- model user intent explicitly;
- preserve intent across cart/state changes;
- verify after meaningful mutations;
- recover when safe;
- ask when uncertain;
- use failure injection against the existing commerce boundary;
- keep tests deterministic for hard rules;
- inspect actual code before claiming a feature exists.

## 9. First engineering target

Before adding broad Intent features, clean the current consumer boundary:

1. remove/isolate old dark-store API/model/service residue;
2. remove frontend fake operational inventory mutation from consumer checkout;
3. keep customer commerce tests green;
4. retain `CommercePort` and the checkout guard;
5. then introduce `IntentContract` and `IntentVerifier`.

## 10. UI rule

The existing polished WhatsApp/iPhone customer experience is the interface foundation.

Do not create a second UI identity for Intent.

The UI should communicate states such as:

```text
READY
RECOVERING
NEEDS DECISION
AWAITING CONFIRMATION
ORDERED
FAILED
```

## 11. External provider rule

Before changing Swiggy integration, read the current Swiggy Builders Club documentation and verify actual tool schemas/error semantics.

Never guess provider behavior.

## 12. Quality gate

Before declaring implementation complete:

```text
npm run lint
npm run build
pytest backend/tests
```

The exact test count may change as Intent tests are added. Never hard-code an old count as a proof of current correctness.
