# GROCER submission checklist

- [x] Remove the direct LLM commerce path and keep one canonical controller.
- [x] Remove public OAuth-status enumeration and unsafe deployed fallbacks.
- [x] Make the landing page English-only, accessible, and clearly non-interactive where illustrative.
- [x] Add submission review checkout behavior and truthful user messages.
- [x] Add direct conversation-controller/evaluation contract coverage, including stale interactive choices.
- [ ] Move session, OAuth, idempotency, and lock state to a durable encrypted database.
- [ ] Verify the whitelisted OAuth redirect, Meta test number, and real Swiggy review flow.
- [x] Add CI and a reviewer walkthrough. Redacted deployment telemetry remains a live-integration gate.
