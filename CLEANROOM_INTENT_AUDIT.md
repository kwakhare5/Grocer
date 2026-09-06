# Intent Cleanroom Audit

The Intent subsystem is being retained, not replaced wholesale.

## Decisions

- `intent_chat.py`: KEEP
- `models.py`: KEEP + REFACTOR
- `parser.py`: REFACTOR toward structured extraction with deterministic validation
- `policy.py`: KEEP + REFACTOR
- `verifier.py`: KEEP + HARDEN
- `recovery.py`: REFACTOR into candidate generation, policy gate, execution, and re-verification
- `session.py`: KEEP + REFACTOR
- `orchestrator.py`: REFACTOR so orchestration owns lifecycle, not business rules
- `integrations/commerce/port.py`: KEEP

## Golden path

`message -> intent contract -> product resolution -> cart -> verification -> awaiting confirmation -> explicit checkout`

## First failure scenario

`item unavailable -> classify drift -> generate compliant alternatives -> policy gate -> replace -> fetch cart -> verify again -> awaiting confirmation`

## Non-goals

- No dark-store inventory logic in Grocer.
- No autonomous checkout.
- No autonomous refunds.
- No competitor benchmarking.
- No second standalone evaluation product.
