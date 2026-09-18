# GROCER final scope and dependency audit

> Read-only audit at the current `main` workspace. No application code was changed.

## Verdict

The permanent product boundary is sound: English WhatsApp input, durable `ShoppingTask`, deterministic safety, Swiggy MCP behind `CommercePort`, verified cart truth, and review-only checkout. The main defect is not that this architecture exists; it is that the live language boundary is still rule-based while a second legacy runtime remains importable and publicly mounted.

Deleting all "old" files now would break startup. The correct sequence is **cut dependencies first, prove the durable route, then delete the disconnected legacy cluster**.

## Evidence from the live dependency path

- `render.yaml:25-26` enables `SHOPPING_TASK_ROUTE=true`.
- `backend/main.py:56-60` constructs `ShoppingTaskApplicationService` without injecting a model-backed understanding service.
- `backend/intent/task_service.py:71` therefore defaults to `MessageUnderstandingService()`.
- `backend/intent/message_understanding.py:11` imports `RuleBasedExtractor`; its operation selection is regex/rules, not Gemini.
- `backend/api/whatsapp.py:75` chooses the durable route at request time, but line 13 and module initialization still import/create `GrocerOrchestrator`.
- `backend/main.py:92` always mounts `intent_chat_router`; `backend/api/intent_chat.py:20-25` imports and constructs the legacy orchestrator.
- Therefore the legacy cluster is not dead yet even when the WhatsApp flag is true.

## Classification

### Live and required

- `backend/main.py`, `backend/config.py`
- `backend/api/health.py`, `oauth.py`, `whatsapp.py`
- `backend/channels/*`
- `backend/intent/task_model.py`, `task_reducer.py`, `task_service.py`, `task_repository.py`
- `backend/intent/message_understanding.py` **as a boundary**, but its rule-only implementation must be replaced/deepened
- `backend/intent/catalog_resolution.py`, `cart_adoption.py`
- `backend/integrations/commerce/*` except mock-only production use
- migrations `001` and `002`
- Vercel landing/OAuth/webhook proxy under `app/`, shared UI components, deployment configuration

### Legacy but still imported — unsafe to delete now

- `backend/intent/orchestrator*.py`, `conversation.py`, `session.py`, `storage.py`, `stages/*`, `formatters.py`
- `models.py`, `enums.py`, `policy.py`, `preferences.py`, `recovery*.py`, `verifier.py`
- `parser.py`, `taxonomies.py`, `validator.py`
- `backend/api/intent_chat.py` and much of `backend/api/schemas.py`

These form one connected legacy cluster. In addition, the new rule service imports `RuleBasedExtractor` from legacy `parser.py`, so `parser.py` cannot be removed until the extractor is replaced or moved.

### Potentially removable after dependency cut and verification

- The entire legacy cluster above.
- The browser `/api/intent/*` surface if the landing page has no legitimate consumer for it.
- Legacy-oriented tests after equivalent live-route acceptance coverage exists.
- `backend/evaluation/*` only if it remains coupled to the legacy contract; evaluation itself is useful, but a second product/runtime is not.
- `MockCommerceAdapter` must remain for unit/contract tests, but must never be selected in the hosted submission.
- `graphify-out/` is generated analysis output, not product source, and should not ship if tracked.

No individual file in these groups is declared safe for immediate deletion solely from static reachability. Dynamic imports, package exports, tests, and deployment entry points must be cut first and then verified.

## Scope drift and contradictions

1. Two public runtimes exist: durable WhatsApp ShoppingTask and legacy `/api/intent`. This contradicts the "one state owner" goal.
2. Docs say "natural-language operation boundary" is implemented, but the live boundary is regex-only. That wording overstates product readiness.
3. README/package copy emphasizes deterministic recovery and intent verification more than the primary user promise: order groceries naturally on WhatsApp.
4. The legacy evaluation/recovery framework is extensive but does not prove the deployed human conversation.
5. `CURRENT_STATE.md` says the legacy runtime is rollback code, but it is still imported at startup and mounted as an API, not isolated rollback-only code.

## Missing critical product behavior

1. A context-aware, model-backed structured interpreter in the **live** ShoppingTask service.
2. Model input containing current task state, desired/pending basket, pending question, and currently offered choices.
3. Deterministic validation of model proposals and exact handling of button IDs.
4. Transcript acceptance tests against the live service, including greetings, corrections, pronouns, ordinal choices, quantity changes, address/payment changes, cancellation, and interruptions.
5. Hosted review-mode evidence through real WhatsApp + authenticated Swiggy for the complete journey.
6. Explicit reconciliation language for partial availability and changed provider results without overwriting original customer intent.

## Hidden hosted-operation risks

- **No independent outbox worker:** `CURRENT_STATE.md` and repository code show pending delivery is retried through webhook replay. If Meta accepts an inbound event once and outbound delivery fails without a replay, the customer may receive no reply.
- **Cold start / synchronous webhook work:** the Render web request performs understanding, provider calls, and WhatsApp send before returning. Free-host cold starts or slow Swiggy/Gemini calls can cause Meta retries and poor latency.
- **Broad exception fallback is not durable:** the durable route's exception reply in `backend/api/whatsapp.py:94-110` is sent directly and is not clearly enqueued/marked through the normal outbox lifecycle.
- **Two webhook surfaces:** Meta may point at Vercel, which proxies to Render. Both deployment secrets and `BACKEND_INTERNAL_URL` must agree; otherwise verification can succeed while POST delivery fails.
- **Live configuration is not startup-validated completely:** database/encryption are checked for Swiggy, but required Meta, Swiggy client, Gemini/model, redirect, and Vercel proxy variables should be validated as a deployment contract.
- **Test-count illusion:** most current coverage protects legacy/mock behavior. Green local tests are necessary but not evidence of hosted conversational correctness.
- **Review/live safety:** `CHECKOUT_MODE=review` must remain forced for the submission until a separately authorized live release gate.

## Safe deletion order

1. Implement and inject the model-backed structured understanding service into `ShoppingTaskApplicationService`.
2. Add live-service transcript tests and hosted review-mode replay; make them release gates.
3. Remove the `/api/intent` router from `backend/main.py` and remove the unconditional legacy orchestrator import/instance from `backend/api/whatsapp.py`.
4. Remove the new route's dependency on legacy `RuleBasedExtractor`.
5. Use import/static analysis plus `pytest backend/tests`, `npm run lint`, and `npm run build` to identify the now-disconnected legacy cluster.
6. Delete the legacy API, orchestrator/session/stages/parser/policy/recovery cluster and its legacy-only tests in one controlled change.
7. Re-run all gates and a real hosted replay before declaring cleanup complete.

## Final decision

Do not delete old architecture merely because it is old. Delete it because the live runtime no longer imports, mounts, or depends on it and the replacement has passed real acceptance gates. Today that condition is **not** satisfied. The immediate permanent fix is to connect the model at the live language boundary and remove the legacy dependencies in the order above; a wholesale deletion first would create a deployment failure, not solve language understanding.
