# GROCER final delivery checklist

## Baseline and safety

- [x] Audit the deployed WhatsApp path and prove the new task core is disconnected.
- [x] Lock the final product scope and architecture in `implementation_plan.md`.
- [ ] Add red-capable transcript reproductions for the reported human-language failures.
- [ ] Fix CI dependency paths and the `main` branch trigger.
- [ ] Make the Swiggy smoke test read-only and truthful by default.

## Single task engine

- [x] Define `ShoppingTask`, desired basket, provider-cart binding, and basket plan.
- [x] Add the initial basket reducer, catalogue resolver, and cart-adoption guard.
- [ ] Add address selection/change operations and state transitions.
- [ ] Add payment selection/change operations and state transitions.
- [ ] Add product choice, quantity change, cancellation, help, and tracking operations.
- [ ] Invalidate confirmation after every basket, address, payment, price, or availability change.
- [ ] Make unknown or uncertain language clarify instead of defaulting to a mutation.
- [ ] Ensure text and WhatsApp buttons produce the same typed operations.

## Application service and provider safety

- [ ] Build one `ShoppingTaskApplicationService` as the only conversation brain.
- [ ] Resolve all essentials before any provider mutation.
- [ ] Read the Swiggy cart at every cart-affecting turn boundary.
- [ ] Require Keep / Start fresh / Cancel for an existing provider cart.
- [ ] Read back and verify the provider cart after every mutation.
- [ ] Build versioned final confirmation snapshots.
- [ ] Implement COD, UPI, uncertain-checkout, and tracking contracts.
- [ ] Keep `CHECKOUT_MODE=review` and stop before checkout.

## Durability and security

- [ ] Configure the private Supabase Session Pooler URL directly in Render.
- [ ] Apply the private-schema migration.
- [ ] Wire task, inbound dedupe, and outbound delivery storage into the live route.
- [ ] Encrypt Swiggy access tokens using `DATA_ENCRYPTION_KEY`.
- [ ] Persist OAuth PKCE state and remove `/tmp` plaintext token storage.
- [ ] Test restart recovery, duplicate webhook delivery, concurrency, and outbound retry.

## Cutover and verification

- [ ] Route WhatsApp to the new service behind one temporary rollback flag.
- [ ] Pass reducer, application-service, channel, and signed-webhook transcript suites.
- [ ] Pass sanitized real Swiggy response replays.
- [ ] Pass real WhatsApp review-mode scenarios through the final checkout preview.
- [ ] Verify Vercel, Render, Meta, OAuth, address, catalogue, cart, payment, and tracking configuration.
- [ ] Run `pytest backend/tests`, `npm run lint`, and `npm run build`.
- [ ] Scan for secrets, personal data, raw provider errors, and legacy runtime imports.

## Final cleanup

- [ ] Switch the new route on permanently after all gates pass.
- [ ] Complete the rollback observation window.
- [ ] Delete the legacy conversation/controller/orchestrator/session/stage/recovery runtime.
- [ ] Replace or delete legacy-only tests after equivalent transcript coverage exists.
- [ ] Consolidate active documentation and remove superseded evidence files.
- [ ] Remove the temporary route flag.
- [ ] Enable a real order only after a separate explicit authorization.
