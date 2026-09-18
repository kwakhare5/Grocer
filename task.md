# GROCER final delivery checklist

## Baseline and safety

- [x] Audit the deployed WhatsApp path and prove the new task core is disconnected.
- [x] Lock the final product scope and architecture in `implementation_plan.md`.
- [x] Add red-capable transcript reproductions for the reported human-language failures.
- [x] Fix CI dependency paths and the `main` branch trigger.
- [x] Make the Swiggy smoke test read-only and truthful by default.

## Single task engine

- [x] Define `ShoppingTask`, desired basket, provider-cart binding, and basket plan.
- [x] Add the initial basket reducer, catalogue resolver, and cart-adoption guard.
- [x] Add address selection/change operations and state transitions.
- [x] Add payment selection/change operations and state transitions.
- [ ] Add product choice, quantity change, cancellation, help, and tracking operations.
- [x] Invalidate confirmation after every basket, address, payment, price, or availability change.
- [ ] Make unknown or uncertain language clarify instead of defaulting to a mutation.
- [x] Ensure text and WhatsApp buttons produce the same typed operations.
- [x] Inject a context-aware Gemini structured interpreter into the live route.
- [x] Persist bounded product/address/payment/adoption/confirmation choices with each task and resolve typed ordinals against them.

## Application service and provider safety

- [x] Build one `ShoppingTaskApplicationService` as the active conversation brain.
- [x] Resolve all essentials before any provider mutation.
- [x] Read the Swiggy cart at every cart-affecting turn boundary.
- [x] Require Keep / Start fresh / Cancel for an existing provider cart.
- [x] Read back and verify the provider cart after every mutation.
- [x] Store final checkout-confirmation snapshots and invalidate them on any basket/address/payment change.
- [x] Convert verified Swiggy quantity reductions into Keep available / Choose another / Remove item recovery with fresh basket approval.
- [ ] Implement COD, UPI, uncertain-checkout, and tracking contracts.
- [x] Keep `CHECKOUT_MODE=review` and stop before checkout.

## Durability and security

- [x] Configure the private Supabase Session Pooler URL directly in Render.
- [x] Apply the private-schema migration.
- [x] Wire task, inbound dedupe, and outbound delivery storage into the live route.
- [x] Encrypt Swiggy access tokens using `DATA_ENCRYPTION_KEY`.
- [x] Persist OAuth PKCE state and remove `/tmp` plaintext token storage.
- [ ] Test restart recovery, duplicate webhook delivery, concurrency, and outbound retry.

## Cutover and verification

- [x] Route WhatsApp to the new service as the only conversation path.
- [x] Pass reducer, application-service, channel, and signed-webhook transcript suites.
- [x] Pass sanitized real Swiggy response replays.
- [ ] Pass real WhatsApp review-mode scenarios through the final checkout preview.
- [ ] Verify Vercel, Render, Meta, OAuth, address, catalogue, cart, payment, and tracking configuration.
- [x] Run `pytest backend/tests`, `npm run lint`, and `npm run build`.
- [x] Scan for secrets, personal data, raw provider errors, and legacy runtime imports.

## Final cleanup

- [ ] Prove the single active route after all hosted gates pass.
- [ ] Consolidate active documentation and remove superseded evidence files.
- [x] Remove the temporary route flag.
- [ ] Enable a real order only after a separate explicit authorization.
- [x] Lock the website to landing/OAuth scope; remove the legacy browser chat at cutover.
