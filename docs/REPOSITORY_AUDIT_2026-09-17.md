# GROCER repository audit — 2026-09-17

## Verdict

**Target architecture: GREEN.** The single ShoppingTask service, deterministic
reducer, CommercePort boundary, durable task state, and review-only checkout
boundary are the right direction for this product.

**Current reliability implementation: RED.** Inbox recording, task persistence,
provider mutation, and outbox enqueue are not one recoverable transaction. A
failure can consume an inbound message or mutate Swiggy without a durable task
result.

**Release readiness: RED.** The repository does not yet prove the complete
hosted WhatsApp → Render → Supabase → Gemini → Swiggy journey. The latest user
failure occurred after basket confirmation, and the exact exception is not yet
captured in a red-capable replay.

**Scope: GREEN.** Saved addresses, English WhatsApp ordering, bounded buttons,
Swiggy cart verification, and review-only checkout are appropriate. Tracking,
multilingual input, voice, coupons, and live checkout remain outside this first
submission.

## What is working locally

- One active WhatsApp route and one ShoppingTask application service.
- Gemini is wired as a proposal-only language boundary with a deterministic fallback.
- Buttons, lists, ordinals, and price references resolve against persisted offered choices.
- Product resolution, cart adoption, stock recovery, address selection, payment
  selection, and checkout review states exist.
- Swiggy calls are behind `CommercePort` and the adapter performs cart read-back.
- The active backend test suite passes locally.

## What is not proven

- The exact real confirmation failure reported over WhatsApp.
- Real provider authentication/session continuity after deployment.
- Exact current Swiggy response shapes for every live tool result.
- Duplicate Meta webhook and outbound delivery behavior under retry.
- Restart/concurrency recovery on the hosted database.
- The full review-mode journey through a real authenticated Swiggy session.

## Findings

1. The reported failure is consistent with the post-confirmation synchronization
   boundary, but the exact production exception is unproven. `CONFIRM_BASKET`
   enters `_synchronize`, which can call `get_cart`, resolve every item again,
   call `update_cart`, and read the cart back.
2. Unexpected exceptions escape the task service and become a generic WhatsApp
   fallback. The fallback does not identify the failing provider boundary and is
   not sufficient evidence that external state was unchanged.
3. Product resolution currently happens after basket approval. This can force a
   user through repeated review screens when multiple requested items are
   ambiguous. The permanent flow must resolve all essentials before approval.
4. The basket can retain the customer's original words instead of the selected
   provider product name. That is confusing and weakens the review contract.
5. The Render blueprint uses the free plan. Cold starts and webhook timing can
   contribute to retries, but they do not explain the backend synchronization
   failure by themselves.
6. `gemini-3.5-flash-lite` is a valid structured-output model. Changing models
   is not the first fix; instrumentation and state/provider correctness are.
7. The old runtime has been removed from this checkout. Restoring it would create
   the competing conversation brain that caused the earlier test illusion.
8. An inbound event is inserted before processing, while task save and outbox
   enqueue are separate statements. A crash or version conflict can permanently
   consume a message with no durable reply.
9. Two concurrent messages for one customer can both reach Swiggy before one
   optimistic task save loses. Provider state may then diverge from task state.
10. The webhook fallback can falsely say nothing changed after `update_cart`
    succeeded but read-back or persistence failed. That fallback is sent directly,
    outside the durable outbox.
11. Meta delivery occurs before the outbox row is marked sent. A crash in that
    gap can resend the same reply; the unique row prevents duplicate records, not
    duplicate WhatsApp delivery.
12. OAuth login binds a Swiggy session to a caller-supplied phone number without
    proving control of that WhatsApp number. Identity also hashes only the final
    ten digits, creating cross-country collision risk.
13. Existing-cart adoption can merge provider extras into the Swiggy update but
    later persist only the requested plan as `desired_basket`, breaking the rule
    that desired basket is authoritative.
14. Cart verification checks expected quantities but does not reject unexpected
    extra items. Start-fresh correctness therefore depends on provider replacement
    semantics that are not proven by the current live replay.
15. The final review snapshot does not include an item fingerprint, and review-mode
    confirmation rereads and renders the cart without enforcing equality with the
    stored snapshot.
16. Health reports availability without checking database/provider readiness;
    migrations are not automatically applied by the Render blueprint.

## Implementation order

1. Make inbox claim, task compare-and-save, and outbox enqueue an atomic database
   operation with explicit processing/retry status; serialize one customer's turns.
2. Add unknown-provider-outcome reconciliation and remove every unverified
   “nothing changed” claim.
3. Prove WhatsApp outbound delivery semantics and make pending delivery recoverable
   without relying only on Meta replay.
4. Require proof that the OAuth initiator controls the WhatsApp identity being
   linked; preserve full E.164 identity.
5. Add a generalized multi-item replay that fails on the reported confirmation
   symptom and captures sanitized correlation data.
6. Fix all-essential preflight resolution, selected-product rendering, cart
   adoption authority, and exact cart verification.
7. Enforce the complete checkout-review snapshot before reporting review complete.
8. Run the hosted review-mode matrix against the authenticated Swiggy session.
9. Only after those gates pass, prepare the Swiggy submission.

## Non-goals for this gate

Do not add tracking, voice, multilingual support, coupons, live checkout, a
second web shopping runtime, or another architecture. A browser/CLI replay
harness may be used to isolate the same backend service; it is not a replacement
for the WhatsApp product.
