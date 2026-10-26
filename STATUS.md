# STATUS.md — Grocer v1.0 Single Source of Truth

> **Updated:** 2026-10-26
> **Read this first.** `TASKS.md` is the historical roadmap and contains outdated "complete" claims.
> **Maintenance rule:** every session updates this file before it ends.

---

## 0. Product Scope

Grocer is a full Swiggy Instamart concierge on WhatsApp. The customer should be able to do anything the Swiggy Instamart MCP allows, through natural WhatsApp conversation.

That includes shopping, price/stock/store questions, saved addresses, adding and switching addresses, order history, live tracking, coupons, reorders, recipes, payments, support escalation, and privacy controls. Ordering is one capability, not the whole product.

The boundary is the Swiggy Instamart MCP surface, plus an honest fallback where Swiggy does not support an action. Examples are illustrations only; they are not the scope limit.

**Hard rules:**

- No fake Swiggy MCP in production.
- No fake Gemini in production.
- No order or checkout without Karan's explicit approval.
- Cart changes are allowed for testing; checkout is not.
- No tests against the live production database.
- No deleting customer data without listing it first and getting approval.
- No weakening a test to make it pass.

---

## 1. Current State — One Screen

| Item | State |
|---|---|
| Branch | `grocer-v1` |
| Gate 0 live check | Passed: token works, 3 addresses, live search returns 10 products |
| Gate 1 code | Committed locally on `grocer-v1` (`1ae6431`); **not pushed** |
| Migration 002 | Tracked in git and applied to Supabase |
| Last recorded test run | 109/109 passed (42 fast + 37 checkout/e2e/channels + 30 Gemini) |
| Test integrity | One location-pin test was weakened to expect `auth_required` |
| Live refresh | Not tested; refresh does not run on normal token expiry |
| Live checkout | Not tested; no order placed |
| Account order history | `get_orders` returns 0 orders |
| Token expiry | **2026-10-31 14:51 UTC** |
| Gemini | Works; primary model hit a free-tier 429, fallback answered |
| Production readiness | **No** |

---

## 2. Status Legend

| Label | Meaning |
|---|---|
| **FIXED** | Implemented and proven with a live call or a real captured response |
| **FIXED-UNCOMMITTED** | Code exists but is not committed, deployed, or fully proven |
| **PARTIAL** | Some code exists, but it is not wired, not proven, or misses cases |
| **BROKEN** | Code exists and is known to be wrong or dangerous |
| **NOT STARTED** | No implementation yet |
| **BLOCKED** | Cannot proceed without a decision, credential, or external approval |

---

## 3. Phase Table

| Phase | Fixed | Partial | Broken / Remaining | Acceptance Condition |
|---|---|---|---|---|
| **0. Truth and baseline** | Scope docs corrected; 6 DB tables exist; migration 001 applied; `STATUS.md` created | Migration 002 untracked; handoff and journal stale | Fake production branches; tests use live DB; old docs claim all phases complete | Clean git tree; migration tracked; no fake production branch; isolated test DB; docs agree with code |
| **1. Live Swiggy spine** | Correct field names for `update_cart`, `create_address`, `get_orders`, `track_order`, `confirm_order`; all 20 tool methods exist; refresh token stored; checkout copy fixed | Refresh-on-401 only; multi-store not modeled; confirm-order error not caught; tracking coords missing for existing users; payment options unused | Refresh on expiry; refresh in buttons/pollers; UPI args; live read-only and cart proof | Live read-only and cart test pass; refresh works on expiry and 401; multi-store parsed; confirm errors handled; tracking works or tells the truth |
| **2. Concierge conversations** | Greeting, Q&A, recipe proposal, grocery-list extraction; 12-turn history; multi-item extraction | Q&A is not grounded in live data; per-item Gemini calls; disambiguation is broken; fallback keyword tables remain | Intents for price/stock/store, addresses, order history, tracking, cancel, reorder, post-order additions, fee questions | Every capability in the product scope has a real intent and a live proof |
| **3. Address and account lifecycle** | Pin onboarding → flat → name → city/PIN → `create_address`; full address fields; display name; pin coordinates | Only onboarding; no list/add-another/switch/delete; every pin restarts onboarding; hardcoded `HOME`; contradicts Swiggy's one-address guidance | Address list, switch, delete guardrail, default-address grounding, one-time destination, address-type choices | All address journeys work live, including switch and delete guardrail |
| **4. Cart and wallet** | Composite cart read/merge/update/verify; `skuId` threaded; coupon optimizer; net-savings guard; fingerprint | Out-of-stock alternatives missing; cart clear is a stub; change-item is a stub; fee-shock dead; reorder dead; float math remains; invented `sku_<spin>` fallback | Real clear, change item, fee warning, reorder, alternatives, integer-only money | Live add/remove/clear; fee warning; coupon savings; no invented IDs; no float money |
| **5. Orders and payments** | 3-lock gate; CAS; fingerprint; HTTPS bridge; `confirm_order` call added; premature "placed" copy fixed | Payment poller not scheduled; delivery poller has no token; payment options unused; multi-store fails; cap-raise flow broken; milestones can spam | Payment settlement loop; per-user tokens; payment method choice; multi-store; cap raise; delivery milestones; cancellation; post-order additions | No order until approved; after approval, live payment → confirm → tracking works |
| **6. Privacy and operations** | 24h DPDP scrubber; encrypted token vault; `delete my data` handler | Delete leaves the user row; onboarding context stores PII unencrypted/unpruned; outbound failures swallowed; Render free plan can sleep | Full purge; retention for onboarding data; retries; observability; always-on deploy; landing-page fixes | DPDP verified on isolated DB; workers stay alive; no fake UI copy |
| **7. Real proof** | Gate 0 read-only live proof | Test suite mixes real calls with hand-written fixtures and live DB writes | One real low-value order (only with approval); live refresh; live confirm; live tracking; live address add/switch/delete | Evidence recorded in `JOURNAL.md` and `STATUS.md`; no green-chasing |

---

## 4. P0 Blockers — Fix Before Commit or Deploy

| # | Blocker | File | Why It Matters | Fix |
|---|---|---|---|---|
| 1 | Refresh is not used on normal expiry | `backend/channels/whatsapp.py:197`, `backend/integrations/commerce/token_vault.py:120` | Token dies 2026-10-31; bot asks for login instead of refreshing | Add one token resolver: valid → use; expired/401 → refresh once → retry; then reconnect |
| 2 | Migration 002 is untracked | `migrations/002_oauth_refresh_token.sql` | Git deploy will miss columns the code now uses | Track and commit the migration; apply on startup |
| 3 | Multi-store checkout schema | `backend/integrations/commerce/schemas.py:225` | Swiggy split orders return `orders[]`; code expects one `orderId`; can mark success as failure and invite duplicates | Model both single and split responses; store every order ID |
| 4 | `confirm_order` errors are uncaught | `backend/agent/checkout_executor.py:438` | Payment succeeds, confirm fails, checkout stays stuck | Catch, retry, keep a safe pending state, notify the user |
| 5 | Tracking coordinates missing for existing users | `backend/agent/checkout_executor.py:477` | Existing accounts have no pin coordinates, so tracking is skipped | Use coordinates from the order data; fall back to a stored pin |
| 6 | Payment poller is never scheduled | `backend/main.py:70` | Paid orders are never settled by Grocer | Start a durable poller with each user's token |
| 7 | Location-pin test was weakened | `tests/test_channels.py:462` | The test proves parsing, not post-login onboarding | Add a real test with a stored token and live/contract onboarding |
| 8 | Migrations are not applied at startup | `backend/database.py:64` | Fresh deploy starts against an empty schema | Run migrations in lifespan or deployment step |

---

## 5. P1 Blockers — Fix Before Calling It a Working Concierge

| # | Blocker | File | Why It Matters | Fix |
|---|---|---|---|---|
| 9 | Payment options are not used | `backend/integrations/commerce/swiggy_client.py:495` | Checkout cannot choose UPI app, QR, Cash, or Swiggy Money correctly | Fetch options, show choices, pass the selected method |
| 10 | UPI checkout arguments incomplete | `backend/integrations/commerce/swiggy_client.py:440` | Missing `intentApp` / QR path can fail live | Wire the chosen payment option into checkout |
| 11 | Onboarding contradicts Swiggy docs | `backend/agent/address_lifecycle.py:75` | Swiggy asks for one full address; code asks components separately | Align the flow or document the deliberate difference |
| 12 | Address type hardcoded to HOME | `backend/agent/address_lifecycle.py:140` | Wrong category for work/family addresses | Ask or infer only with confirmation |
| 13 | Every location pin restarts onboarding | `backend/channels/whatsapp.py:217` | Existing users get a new address instead of a choice | Distinguish add-new vs switch |
| 14 | Fake production branches remain | `backend/integrations/commerce/swiggy_client.py:105`, `backend/channels/whatsapp_client.py:48` | Violates zero-mock and hides live failures | Remove fixture/catalog/mock branches from production |
| 15 | Tests write to live Supabase | `tests/conftest.py`, multiple test files | Pollutes real data and can scrub real users | Use a separate test schema/database |
| 16 | Webhook is synchronous | `backend/channels/whatsapp.py` | Gemini + Swiggy calls block the 200 response | ACK first, process from a durable queue |
| 17 | Button router stubs | `backend/channels/button_router.py:30,124,167` | Clear cart, address switch, recipe, change-item do nothing | Wire every button to a real action or remove it |
| 18 | Missing concierge intents | `backend/agent/candidate_evaluator.py:173` | Price, stock, store, address, history, track, cancel, reorder fail as shopping searches | Expand the intent contract |
| 19 | Disambiguation is broken | `backend/channels/whatsapp.py:394,454` | Ambiguous items fall into "couldn't find" | Add tappable options and pending state |
| 20 | Fee-shock warning is dead | `backend/agent/customer_advocate.py:81` | Small carts can surprise customers with fees | Call it before checkout |
| 21 | Post-order additions and split receipts are dead | `backend/agent/checkout_executor.py:31` | Promised journeys never run | Wire or remove |
| 22 | One-time destination is dead | `backend/agent/address_lifecycle.py:53` | Send-to-Mom journey does not exist | Wire or remove |
| 23 | DPDP delete is partial | `backend/agent/dpdp.py:112` | User row and audit rows remain | Define and implement the full purge |
| 24 | Outbound WhatsApp failures are swallowed | `backend/channels/whatsapp_client.py:63` | Receipts can vanish unseen | Retry, log, and surface failure |
| 25 | Receipt body is truncated at 1024 chars | `backend/channels/whatsapp_client.py:105` | Long bills silently lose lines | Split messages or summarize honestly |
| 26 | Float money and invented SKU fallback | `backend/agent/composite_cart.py:135,143` | Violates integer-paise and "do not invent IDs" | Use real `skuId`; integer math only |
| 27 | `store_user_token` can wipe refresh token | `backend/integrations/commerce/token_vault.py:95` | A call without a refresh token sets it to NULL | Preserve existing refresh token unless explicitly replacing |
| 28 | Approval is not bound to the tapping user | `backend/agent/checkout_executor.py:255` | Ownership check is missing | Add `user_id` to CAS |
| 29 | Frontend fallback WhatsApp number is fake | `app/page.tsx:76` | Landing page can send users to a stranger | Require the env var and fail loudly |
| 30 | Render free plan sleeps | `render.yaml:1` | Pollers stop | Use an always-on service/worker |
| 31 | Gemini free-tier quota | `.env` | Full live tests hit 20 requests/day | Paid key or quota-aware tests |
| 32 | OAuth state is in memory and login accepts any phone | `backend/integrations/commerce/token_vault.py:24`, `backend/channels/swiggy_auth.py:63` | Account hijack and lost login state | DB-backed state plus signed WhatsApp ticket |
| 33 | Docs still overclaim | `TASKS.md`, `JOURNAL.md` | Future chats repeat false assumptions | Keep `STATUS.md` authoritative; correct stale docs |
| 34 | Green-chasing tests | `tests/` | Passing tests do not prove live behavior | Test user-visible outcomes and real contracts |

---

## 6. What Is Actually Fixed

### Gate 0 — Live proof

- Swiggy token decrypts and works.
- `get_addresses` returns 3 addresses with a default.
- `search_products("Amul milk")` returns 10 live products.
- `get_orders(count=10, orderType=INSTAMART)` works and returns 0 orders.
- Gemini 3.5 works; primary model can hit a free-tier 429, fallback answers.

### Gate 1 — Code written, not committed

- Swiggy field names fixed for `update_cart`, `create_address`, `get_orders`, `track_order`, `confirm_order`.
- All 20 Instamart tool methods exist, including `get_payment_options` and `report_error`.
- Encrypted refresh-token storage and refresh-on-401 added.
- Address onboarding flow added.
- Checkout copy no longer says "placed" on `PENDING_PAYMENT`.
- `confirm_order` is called after payment when Swiggy does not auto-confirm.
- Migration 002 applied to Supabase.
- Last recorded run: 109/109 tests, Ruff clean, Next build clean.

**Not fixed:** the P0 and P1 items above.

---

## 7. Rules for Every Future Chat

1. Read `STATUS.md`, `.scratch/HANDOFF.md`, and the latest `JOURNAL.md` entry before planning.
2. Do not edit code without showing the exact plan and getting `proceed`.
3. Do not place an order or call checkout without explicit approval.
4. Cart changes are allowed only with approval.
5. Do not fake Swiggy, Gemini, WhatsApp, or the database.
6. Do not run destructive tests against the live database.
7. Do not delete data without listing it first.
8. Do not weaken a test to pass. If the feature is broken, say so.
9. Show `git diff`, test output, and database proof.
10. Update `STATUS.md`, `.scratch/HANDOFF.md`, and `JOURNAL.md` before ending the session.

---

## 8. Current Next Gate

**Gate 1.1 — close the P0 blockers. No commit, no deploy until they pass.**

Order:

1. Add one token resolver: valid → use; expired or 401 → refresh once → retry; then reconnect.
2. Track migration 002 and apply migrations on startup.
3. Fix multi-store checkout responses.
4. Catch and retry `confirm_order`.
5. Get tracking coordinates from order data.
6. Schedule the payment poller with the user's token.
7. Replace the weakened location test with a real onboarding test.

After that:

- Run live read-only Swiggy checks.
- Run a live cart test. No checkout. No order.
- Commit Gate 1 and update this file.
- Then start Gate 2: concierge intents and the full product surface.

---

## 9. Maintenance Contract

| File | Purpose | When to Update |
|---|---|---|
| `STATUS.md` | Single source of truth: fixed, partial, broken, next | Every session start and end |
| `.scratch/HANDOFF.md` | Five-line resume note | End of session |
| `JOURNAL.md` | Proof log: problem, change, proof, still broken | Every change |
| `TASKS.md` | Historical roadmap only | Do not use for current status |
| `AGENTS.md` | Rules and product scope | When rules or scope change |
| `PRD.md` | Product requirements | When product requirements change |

If code and docs disagree, the code plus live proof win. Update the docs.
