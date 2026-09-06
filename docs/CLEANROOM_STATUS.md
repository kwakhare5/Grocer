# GROCER Cleanroom Status

This file records the repository-boundary cleanup that is being performed before further feature work.

## Target boundary

GROCER owns the consumer experience: WhatsApp conversation, intent, policy/preferences, cart verification, recovery, commerce integration, approval, checkout, and outcome verification.

The dark-store operator system is a separate repository and is not part of GROCER.

## Cleanup rules

- Remove old operations APIs, services, models, tests, and UI that are not required by the consumer path.
- Preserve `CommercePort` and provider adapters as the only commerce integration boundary.
- Preserve the current Intent subsystem while auditing and hardening it.
- Never reintroduce inventory-management, supplier, warehouse, risk, forecasting, transfer, or operations-dashboard functionality into GROCER.
- Generated Graphify output is local tooling output, not product source.

## Current worktree

The cleanup is being performed on `refactor/intent-cleanroom`, not directly on `main`.

## Completion gate

Phase 0 is complete only when:

1. No obsolete operations modules are reachable from the app.
2. No consumer path depends on store inventory simulation or old operations models.
3. No duplicate commerce execution path competes with `CommercePort`.
4. Stale/duplicate documentation is archived or removed.
5. Frontend and backend builds/tests pass.
6. A repository-wide search shows no accidental imports from the removed operations stack.
