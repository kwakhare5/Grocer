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

## Evaluation design

The matrix contains 102 scenarios. Count is secondary to value; scenarios should be consolidated with parameterization where one invariant covers several inputs.

Metrics must be computed from actual scenario outcomes:

- intent preservation and hard-constraint satisfaction;
- explicit physical-quantity underfill rate;
- wrong-product/brand selection rate;
- unsafe autonomous checkout rate (target zero);
- duplicate checkout attempt rate (target zero);
- truthful pending/partial/unknown classification;
- recovery success and unnecessary clarification;
- provider calls per completed task.

A direct-selection baseline is useful only for the semantic scenarios where both systems receive the same catalog/cart fixtures. It must not perform checkout and must not be presented as a production competitor benchmark.
