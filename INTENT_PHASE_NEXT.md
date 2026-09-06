# Intent Phase Next

## Target

Prove one complete intent-preserving loop before expanding scope:

`WhatsApp message -> IntentContract -> product resolution -> live cart -> deterministic verification -> failure injection -> recovery -> re-fetch cart -> re-verification -> explicit confirmation`

## First failure

Product unavailable.

## Acceptance criteria

1. Hard constraints are never silently violated.
2. A compliant recovery is auto-applied only when PolicyEngine allows it.
3. Ambiguous substitutions produce a user choice instead of guessing.
4. Every recovery mutation is followed by a fresh cart fetch and verifier pass.
5. Checkout requires AWAITING_CONFIRMATION plus explicit confirmation.
6. Recovery failure ends safely with an actionable message.
