# Adversarial Test Matrix

> High-value deterministic scenarios for GROCER. No scenario may place a real order. `Mock` means `MockCommerceAdapter`; `Contract` means mocked official MCP payloads exercised through `SwiggyMCPAdapter`.

## Quantity and pack semantics

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| Q01 | 1 L milk, only 500 ml packs | select 2 packs; never underfill | unit |
| Q02 | 1 L milk, only 750 ml packs | clarify or apply explicit overfill policy; never buy 750 ml silently | unit |
| Q03 | 1.5 L milk, 500 ml packs | select 3 packs | unit |
| Q04 | 2 L milk, 500 ml packs | select 4 packs | unit |
| Q05 | 2 kg rice, 500 g packs | select 4 packs | unit |
| Q06 | 750 g paneer, 250 g packs | select 3 packs | unit |
| Q07 | 12 eggs, 6-count packs | select 2 packs, not 12 | unit |
| Q08 | 2 dozen eggs, 6-count packs | select 4 packs | unit |
| Q09 | 3 packs biscuits | preserve pack count, not physical mass | unit |
| Q10 | 3 milk with no unit | surface material count/volume ambiguity before cart mutation | integration |
| Q11 | 500 ml request vs 500 g product | reject dimension mismatch | unit |
| Q12 | provider pack string `1.5 l` | normalize case/space/decimal correctly | unit |
| Q13 | provider pack string `2 x 500 ml` | normalize multipack to 1000 ml | unit |
| Q14 | malformed/missing pack metadata | mark quantity unverifiable; do not assume one unit satisfies volume | unit |
| Q15 | cheapest candidate underfills; dearer candidate satisfies | choose semantically valid candidate before price ranking | unit |
| Q16 | max provider quantity below required amount | clarify/blocked; never claim full quantity | integration |
| Q17 | 6 individual pieces vs 6-piece or 1-piece provider packs | choose 1 or 6 packs respectively; reject non-divisible fill | unit |

## Product identity, brand, and dietary intent

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| I01 | milk request vs milk powder | reject derivative product | unit |
| I02 | milk request vs chocolate milkshake | reject derivative product | unit |
| I03 | rice request vs rice flour | reject derivative product | unit |
| I04 | bread request vs breadcrumbs | reject derivative product | unit |
| I05 | butter request vs peanut butter | reject incompatible product head/category | unit |
| I06 | Mother Dairy milk available | preserve explicit multi-word brand | integration |
| I07 | Mother Dairy milk unavailable, Amul available | ask or follow explicit substitution policy; no silent switch | integration |
| I08 | stored Amul preference, current Mother Dairy request | current request wins | unit |
| I09 | prior turn selected Amul, current explicit Mother Dairy | current turn wins | integration |
| I10 | hard vegetarian request, product metadata contradicts | reject item | unit |
| I11 | dietary metadata absent | do not claim compliance; clarify when material | unit |
| I12 | two equally valid brands under soft policy | clarify only when ranking cannot decide safely | integration |
| I13 | any currently parsed hard dietary tag lacks authoritative metadata | fail closed as dietary-unverifiable | unit |

## Intent mutation, policy, and recovery

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| R01 | item becomes unavailable after add | observe, classify, generate, filter, mutate, refetch, reverify | integration |
| R02 | mutation reports success but cart unchanged | recovery fails/blocks after refetch | integration |
| R03 | partial cart update | reconcile each requested item; no blanket success | integration |
| R04 | price drift breaches hard budget | block and require changed intent | integration |
| R05 | delivery/packaging fee drift breaches budget | same as item-price drift | integration |
| R06 | safe transient read failure | bounded retry with backoff policy | unit |
| R07 | transient cart mutation failure | retry only documented idempotent mutation | integration |
| R08 | recovery exhausts maximum attempts | terminal blocked/failed without loop | unit |
| R09 | stale substitution choice after new clarification | reject old action token | integration |
| R10 | user says remove bread before confirmation | intent and cart update; approval invalidated | integration |
| R11 | user says make milk 3 L | update explicit intent, rebuild, reverify, invalidate approval | integration |
| R12 | user changes brand/payment before checkout | update authoritative state and require new approval | integration |

## Confirmation, concurrency, and idempotency

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| C01 | confirm without pending approval | reject; zero checkout calls | integration |
| C02 | confirmation missing/wrong nonce | reject; zero checkout calls | integration |
| C03 | expired confirmation | show/refetch basket and require new approval | integration |
| C04 | same confirmation submitted twice sequentially | one checkout attempt; stable outcome | integration |
| C05 | two simultaneous confirmations | one checkout attempt | concurrency |
| C06 | price changes after display | fingerprint mismatch; no checkout | integration |
| C07 | fee changes after display | fingerprint mismatch; no checkout | integration |
| C08 | discount changes after display | fingerprint mismatch; no checkout | integration |
| C09 | SKU changes but name stays same | fingerprint mismatch; no checkout | integration |
| C10 | quantity composition changes with same total volume | renewed approval because material basket changed | integration |
| C11 | address changes after display | no checkout; new approval | integration |
| C12 | payment choice changes after display | no checkout; new approval | integration |
| C13 | cart ID changes | no checkout; new approval | integration |
| C14 | intent version changes | old approval invalid | integration |
| C15 | “Change Items” button | invalidate approval and return to editable flow | integration |
| C16 | checkout timeout creates unknown outcome | lock attempt, reconcile; never blind retry or say success | integration |

## Swiggy payment and order contract

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| P01 | payment options returns only one UPI intent app | expose exactly that method/id | contract |
| P02 | payment options excludes COD | never offer COD | contract |
| P03 | empty payment options | block/unknown; never invent rails | contract |
| P04 | UPI checkout returns pending fields | state is PAYMENT_PENDING with provider cadence/cap | contract |
| P05 | payment remains pending until max time | stay pending; no order success claim | contract |
| P06 | payment succeeds and auto-confirms | transition to order placed without duplicate confirm call | contract |
| P07 | payment succeeds but not confirmed | call `confirm_order` once with orderId/paasId | contract |
| P08 | payment failed/cancelled | PAYMENT_FAILED; never confirm order | contract |
| P09 | payment reports cart changed | require fresh cart/approval/payment | contract |
| P10 | COD checkout succeeds | skip UPI polling; use returned order state only | contract |
| P11 | Swiggy single-order response missing order ID | unknown/failure; never fabricate ID | contract |
| P12 | multi-store all children succeed | preserve each child and aggregate truthfully | contract |
| P13 | one multi-store child fails | PARTIAL_ORDER; expose child outcomes | contract |
| P14 | all multi-store children fail | failed, not ordered | contract |
| P15 | checkout 5xx then matching order is observed | reconcile to returned real order without retry | contract |
| P16 | checkout 5xx then unrelated historical order exists | ORDER_STATE_UNKNOWN; do not attach it | contract |
| P17 | auth 401/419 | require reauthentication; do not retry with stale token | contract |
| P18 | unsupported/malformed provider response | normalized provider-contract error, safe user state | contract |
| P19 | multiple usable payment methods | require exact live choice and bind a fresh confirmation | integration |
| P20 | provider failure during address/search/recovery/payment lookup | preserve auth/revoked/timeout/provider failure; do not report empty | integration |
| P21 | adapter omits a supported lifecycle method | adapter cannot instantiate | contract |

## Tracking and order-detail truthfulness

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| T01 | unknown order status string | normalized UNKNOWN plus raw status | contract |
| T02 | ETA absent/null | return unknown ETA; no numeric default | contract |
| T03 | coordinates absent | remain absent; no Mumbai fallback | contract |
| T04 | rider/store absent | remain absent | contract |
| T05 | cancelled order | normalized CANCELLED with raw provider state | contract |
| T06 | delivered order | terminal DELIVERED, no further poll recommendation | contract |
| T07 | multi-store children at different states | report each child; aggregate conservatively | integration |
| T08 | `get_order_details` unavailable for account | explain unavailable; do not synthesize items/payment | contract |
| T09 | “what did I order?” with known details | answer only returned item/quantity facts | integration |
| T10 | “how much did I pay?” while payment pending | say payment pending, not paid | integration |
| T11 | unchanged tracking polls | no duplicate user notification | unit |
| T12 | meaningful transition/ETA change | one semantic notification event | unit |
| T13 | conversational tracking phrases with/without trusted coordinates | use rich tracking or explicit structured ETA fallback; never synthesize coordinates | integration |

## WhatsApp, API, auth, privacy, and persistence

| ID | Scenario | Expected behavior | Level |
|---|---|---|---|
| S01 | live mode missing app secret | startup/reception fails closed | integration |
| S02 | missing/malformed/wrong HMAC | 401/403; no dispatch | integration |
| S03 | valid signed JSON array/wrong object/phone ID | predictable validation rejection | integration |
| S04 | oversized webhook | reject before JSON/domain processing | integration |
| S05 | simultaneous duplicate message ID | one local dispatch | concurrency |
| S06 | dispatch fails before completion | event remains retryable; no false processed count | integration |
| S07 | outbound Meta failure after commerce success | retain truthful outcome; retry delivery without checkout | integration |
| S08 | unauthenticated browser confirm/read/delete | forbidden | integration |
| S09 | one session capability used for another session | forbidden | integration |
| S10 | same session ID with different customer | ownership rejected | integration |
| S11 | terminal-session reset | new opaque session with no old intent/cart/order | integration |
| S12 | OAuth callback customer override | ignored/rejected; state binding wins | integration |
| S13 | user A and user B live tokens/carts | resolved independently or live mode refuses unsupported isolation | integration |
| S14 | expired token | removed/re-auth required; token never logged | unit |
| S15 | logs under normal/error flows | no full phone, raw message, token, address, payment/order detail | unit |
| S16 | session deletion | removes session and intent history; capability invalid | integration |
| S17 | provider returns one or many saved addresses | require exact user choice before commerce calls | integration |

## Evaluation design

## Verified coverage ledger

Coverage was re-audited against the targeted-remediation branch on 2026-09-09. AUTOMATED means a deterministic test directly exercises the stated invariant. PARTIALLY COVERED means some layers or variants are tested but the complete scenario is not. MANUAL-LIVE ONLY is reserved for behavior for which the only current evidence is a controlled provider exercise; none was claimed because this audit placed no live order. NOT COVERED is an explicit remaining gap. NOT APPLICABLE means the exposed behavior was intentionally removed.

Evidence aliases: QI = backend/tests/test_quantity_and_identity_semantics.py; DC = test_dietary_constraint_verification.py; TP = test_targeted_provider_contract_regressions.py; PC = test_commerce_port_contract.py; RE = test_recovery_engine.py; AF = test_all_failure_scenarios.py; CR = test_canonical_recovery_regression.py; CI = test_confirmation_integrity.py; PL = test_payment_order_lifecycle.py; SA = test_swiggy_adapter.py; WA = test_whatsapp_channel.py; AS = test_api_session_security.py; PI = test_provider_identity_isolation.py; EH = test_evaluation_harness.py.

| ID | Coverage | Evidence / limitation |
|---|---|---|
| Q01 | AUTOMATED | QI exact-pack-count parameterization |
| Q02 | AUTOMATED | QI rejects silent underfill and overfill |
| Q03 | AUTOMATED | QI preserves explicit 1.5 L quantity |
| Q04 | PARTIALLY COVERED | QI covers the same exact-multiple rule, not this fixture |
| Q05 | PARTIALLY COVERED | QI covers mass normalization, not this fixture |
| Q06 | PARTIALLY COVERED | QI covers exact pack arithmetic, not paneer fixture |
| Q07 | AUTOMATED | QI egg count-pack test |
| Q08 | PARTIALLY COVERED | QI covers dozen/count conversion, not this fixture |
| Q09 | AUTOMATED | QI preserves explicit pack count independently of provider unit count |
| Q10 | PARTIALLY COVERED | Parser ambiguity behavior tested; no full mutation assertion |
| Q11 | AUTOMATED | QI dimension mismatch |
| Q12 | AUTOMATED | QI decimal/case normalization |
| Q13 | AUTOMATED | QI multipack normalization |
| Q14 | NOT COVERED | Missing-pack metadata has no direct regression |
| Q15 | AUTOMATED | QI semantic validity precedes price |
| Q16 | NOT COVERED | No max-quantity integration test |
| Q17 | AUTOMATED | QI covers exact 6-piece/1-piece conversion and rejects non-divisible fill in selection, verification, and recovery |
| I01 | AUTOMATED | QI derivative exclusion |
| I02 | AUTOMATED | QI derivative exclusion |
| I03 | AUTOMATED | QI derivative exclusion |
| I04 | AUTOMATED | QI derivative exclusion |
| I05 | AUTOMATED | QI incompatible product-head exclusion |
| I06 | PARTIALLY COVERED | QI multi-word brand matcher; not full selection flow |
| I07 | PARTIALLY COVERED | RE policy behavior; exact integration fixture absent |
| I08 | AUTOMATED | test_intent_contract.py current-request precedence |
| I09 | PARTIALLY COVERED | Merge/precedence tests do not cover this full turn sequence |
| I10 | AUTOMATED | RE hard dietary violation |
| I11 | AUTOMATED | DC fails closed when authoritative dietary metadata is absent |
| I12 | AUTOMATED | RE ambiguity handling |
| I13 | AUTOMATED | DC parameterizes every dietary tag currently accepted by the parser |
| R01 | AUTOMATED | CR out-of-stock recovery loop |
| R02 | PARTIALLY COVERED | CR refetch/reverify, not unchanged-success fixture |
| R03 | AUTOMATED | AF partial-cart scenario |
| R04 | AUTOMATED | RE/EH hard budget drift |
| R05 | PARTIALLY COVERED | CI fee fingerprint plus budget checks; no end-to-end drift |
| R06 | AUTOMATED | AF/EH bounded transient-read scenario |
| R07 | NOT COVERED | No documented idempotent mutation-retry test |
| R08 | AUTOMATED | RE max-attempt terminal behavior |
| R09 | AUTOMATED | test_orchestrator.py stale clarification token |
| R10 | NOT COVERED | No remove-before-confirmation integration test |
| R11 | NOT COVERED | No quantity-change-before-confirmation integration test |
| R12 | PARTIALLY COVERED | CI payment-change invalidation; brand path incomplete |
| C01 | AUTOMATED | CI/orchestrator wrong-state rejection |
| C02 | AUTOMATED | CI missing and wrong nonce; zero checkout |
| C03 | AUTOMATED | CI expired nonce; zero checkout |
| C04 | AUTOMATED | CI sequential one-time confirmation |
| C05 | AUTOMATED | CI concurrent confirmation |
| C06 | AUTOMATED | CI price fingerprint invalidation |
| C07 | AUTOMATED | CI fee fingerprint invalidation |
| C08 | NOT COVERED | Discount-specific integration regression absent |
| C09 | NOT COVERED | Same-name SKU-swap regression absent |
| C10 | NOT COVERED | Composition-change regression absent |
| C11 | NOT COVERED | Address-change regression absent |
| C12 | AUTOMATED | CI payment-choice invalidation |
| C13 | NOT COVERED | Cart-ID-change regression absent |
| C14 | NOT COVERED | Intent-version-change regression absent |
| C15 | NOT COVERED | Change-items action lacks direct integration test |
| C16 | AUTOMATED | PL/SA uncertain checkout maps unknown; no blind retry |
| P01 | AUTOMATED | PL preserves sole exact provider ID/kind/label |
| P02 | AUTOMATED | PL excludes unavailable COD |
| P03 | AUTOMATED | PL empty-options fail closed |
| P04 | AUTOMATED | PL pending state and provider cadence fields |
| P05 | AUTOMATED | PL/TP enforce cadence and call confirm_order once at the polling cap without checkout retry |
| P06 | NOT COVERED | No direct already-confirmed payment orchestration test |
| P07 | AUTOMATED | PL confirm-once with returned orderId/paasId |
| P08 | AUTOMATED | PL failed payment never confirms |
| P09 | NOT COVERED | Cart-changed payment response not classified |
| P10 | NOT COVERED | No direct COD lifecycle regression |
| P11 | AUTOMATED | SA missing order ID normalizes unknown |
| P12 | PARTIALLY COVERED | SA parses children; all-success aggregate variant incomplete |
| P13 | AUTOMATED | PL/SA partial child failure |
| P14 | NOT COVERED | All-children-failed fixture absent |
| P15 | NOT COVERED | Documented positive timeout reconciliation cannot be proven by current schema |
| P16 | AUTOMATED | SA rejects unrelated historical order after timeout |
| P17 | PARTIALLY COVERED | SA auth errors; integrated token eviction/reauth absent |
| P18 | PARTIALLY COVERED | SA malformed/unknown fields fail safely; not exhaustive |
| P19 | AUTOMATED | TP requires exact live option IDs, rejects stale choices, and renews confirmation |
| P20 | AUTOMATED | TP distinguishes auth, revoked session, timeout/network, provider failure, and true empty results across lookup phases |
| P21 | AUTOMATED | PC proves incomplete lifecycle adapters cannot instantiate and production adapters do |
| T01 | AUTOMATED | PL unknown raw order status |
| T02 | AUTOMATED | PL/SA absent ETA remains absent |
| T03 | AUTOMATED | SA rejects absent coordinates; TP makes zero rich calls and uses the explicit structured fallback |
| T04 | PARTIALLY COVERED | SA nullable rider/store parsing |
| T05 | NOT COVERED | No cancelled tracking fixture |
| T06 | PARTIALLY COVERED | Status normalization exists; terminal poll behavior not tested |
| T07 | NOT COVERED | No heterogeneous child-tracking aggregate |
| T08 | NOT COVERED | No unavailable-details user-message regression |
| T09 | AUTOMATED | PL known details use returned facts |
| T10 | NOT COVERED | No conversational pending-payment price question |
| T11 | NOT COVERED | Proactive notification deduplication is deferred |
| T12 | NOT COVERED | Semantic tracking notifications are deferred |
| T13 | AUTOMATED | WA routes all four conversational phrases; TP selects rich tracking only with trusted coordinates |
| S01 | PARTIALLY COVERED | WA live-secret fail-closed paths; startup matrix incomplete |
| S02 | PARTIALLY COVERED | WA HMAC rejection variants |
| S03 | NOT COVERED | JSON-shape/phone-ID validation matrix absent |
| S04 | NOT COVERED | Fixed 1 MB pre-parse limit exists; no boundary regression/configurability |
| S05 | PARTIALLY COVERED | WA concurrent reservation, not full webhook dispatch |
| S06 | AUTOMATED | WA failed dispatch remains retryable |
| S07 | AUTOMATED | WA outbound retry does not repeat commerce |
| S08 | PARTIALLY COVERED | AS protects session APIs; route matrix incomplete |
| S09 | AUTOMATED | AS cross-session capability rejection |
| S10 | AUTOMATED | AS customer/session ownership rejection |
| S11 | NOT COVERED | No terminal-session reset test |
| S12 | NOT APPLICABLE | Public OAuth callback removed; AS verifies it is not exposed |
| S13 | PARTIALLY COVERED | PI token resolution/refusal; two-user cart isolation not exercised |
| S14 | PARTIALLY COVERED | OAuth expiry is unit tested; automatic eviction incomplete |
| S15 | PARTIALLY COVERED | Redaction helpers tested; full normal/error log audit incomplete |
| S16 | PARTIALLY COVERED | Session and intent history deletion covered; post-delete capability rejection absent |
| S17 | AUTOMATED | TP/SA require explicit one-or-many saved-address selection and exact offered IDs |

Summary: **58 AUTOMATED**, **24 PARTIALLY COVERED**, **26 NOT COVERED**, **0 MANUAL-LIVE ONLY**, **1 NOT APPLICABLE** (109 total).

The matrix contains 109 scenarios. Count is secondary to value; scenarios should be consolidated with parameterization where one invariant covers several inputs.

Metrics must be computed from actual scenario outcomes:

- intent preservation and hard-constraint satisfaction;
- explicit physical-quantity underfill rate;
- wrong-product/brand selection rate;
- unsafe autonomous checkout rate (target zero; verified by confirmation tests, not inferred from the recovery harness);
- duplicate checkout attempt rate (target zero);
- truthful pending/partial/unknown classification;
- recovery success and unnecessary clarification;
- provider calls per completed task.

A direct-selection baseline is useful only for the semantic scenarios where both systems receive the same catalog/cart fixtures. It must not perform checkout and must not be presented as a production competitor benchmark.
