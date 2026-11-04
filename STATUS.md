# STATUS.md — Grocer Current Truth

> **Updated:** 2026-11-04  
> **Authority:** This is the only current status document. `PRD.md` is the v1 target. `ARCHITECTURE.md` is the design plus known gaps. `DESIGN.md` is the WhatsApp UI plus the website landing page. `JOURNAL.md` is append-only history. `docs/adr/` records decisions, amended not rewritten.  
> **Rule:** DONE needs a proof command, date, and raw output. Everything else is PARTIAL, BROKEN, or NOT VERIFIED. A green test is not proof that the live product works.

---

## 0. Environment & Fixed Constraints

| Item | Current fact |
|---|---|
| Git branch | `main` only. Remote and local `main` are at `c16b924`, which carries the handset docs, graphics/motion and copy/phone passes. This proof sync is one local docs commit on top. It deploys Render and Vercel. Rollback target: `db6a297`. |
| Supabase | One project until launch. App data lives in the `postgres` database, schema `grocer` (8 app tables + `schema_migrations`). Both the app database and `grocer_test` are migrated through 010 (app DB applied 2026-10-28; `schema_migrations` lists 001–010). |
| LLM | Groq `openai/gpt-oss-120b` is the only LLM (ADR 0012 amendment 2026-11-04). |
| Swiggy auth | Allowlisted OAuth redirect: `https://grocerr.vercel.app/`. Backend calls `https://mcp.swiggy.com/im` with the customer token. |
| Checkout | `LIVE_CHECKOUT_ENABLED=false`. The build must stay real-order capable. No live order without Karan's explicit approval. |
| Order cap | ₹1,000 default (`100000` paise). |
| Hosting | Backend on Render free plan (sleeps when idle). Landing page on Vercel. |
| Landing page number | The page renders no phone number. The WhatsApp link comes only from `NEXT_PUBLIC_WHATSAPP_NUMBER`; Karan's real number is never committed or published. |
| Product goal | Chat is the front door to all 20 Instamart tools. `PRD.md` §3 journeys are examples, not a checklist. |
| Build-time order policy | No live order during the build. Checkout proof is simulated plus recorded responses. Karan places the first real order after handoff. |
| Address test writes | One throwaway address on Karan's account may be created and deleted. |
| Hosting | Render free plan; pollers reconcile from the DB on wake. No paid instance. |
| Landing OAuth | **Number-first, ownership-proven (2026-11-04).** The Connect form posts a +91 number to `/api/auth/whatsapp/start`, which rate-limits per IP and returns a signed 10-minute code. The page opens `wa.me` with `connect <code>`. The bot sends the Swiggy login link only when the sender's `wa_id` matches the code. No typed number is stored. The bot-sent `?t=` card still handles reconnect and callbacks. The state-cookie and origin-check hardening remains parked in `.scratch/parked/oauth-state-cookie.patch`; routes do not set a browser state cookie. **Handset PASS 2026-11-04:** connect and Swiggy OAuth completed on Karan's phone; the DB shows the token row updated 13:41 UTC and inbound messages through 13:43 UTC. |
| Landing page (Phase 8) | **LIVE 2026-11-02; exact palette, graphics/motion and copy+phone pass LIVE 2026-11-04 (`c16b924`).** Neutral canvas `#FFFFFF`, surface `#F7F7F7`, ink `#0B0B0C`; every primary action is black, including the connect submit. Header is logo / centered nav / one black **Connect Swiggy** action; nav labels are Features, How it works, Demo, Safety, FAQ. The frame is 1180px inside `clamp(24px, 6vw, 80px)` side padding, so 1440px shows 130px gutters. Accents are the exact Gumloop category colors from the home screenshot: blue `#03A2FE`, pink `#FB3C98`, green `#00A63E`, orange `#FE9A00`, red `#F54900`; violet and yellow are not used anywhere. Per-section marks: Connect blue, What pink, How green, Demo orange, Safety red, FAQ blue. Order: hero phone-style WhatsApp sample with a grocery cluster on wide screens, gray Connect band, four-fact white strip, eight ink feature marks in a ruled list + working **Try a message** panel (five real replies), a four-node illustrated How route, three steps, black demo stage with a REC chip, dark safety band with a white paper bill, red Sample stamp and an 18.7% sample cap meter, eight FAQs, gray CTA, white footer. The logo is the original smiling bag in brand blue `#1E8CFF` and is the avatar in the phone mock and Try panel. No dates, test labels, `/proof` link or yellow/cream page bands. Phone micro-facts stack without a dangling separator. Copy cleanup keeps four honesty anchors only: footer legal line, FAQ payment answer, Safety no-order sentence, and one Sample label per mock. Removed the connect meta block, demo payment lines and Try order line. Demo stage shows a black recording state until `public/demo.mp4` exists. Proof: `npm run build` passes 9 routes including the OG image; 1440/1024/768/390/360 have zero overflow, zero console errors and zero hidden reveals; the form blocks a bad number, returns a real signed token through the proxy for a valid one, and the sixth request from one IP returns 429; the Try reply, typing indicator, FAQ, mobile menu and all 31 anchors were tested in a browser; `verify.ps1 -Db` exit 0 (182 offline + 81 DB). Pushed palette; Vercel serves the palette version. Graphics/motion pass: route line 0 → 0.34 at 120ms → 1, nodes 0 → 1, bill item 0.96 at 150ms, stamp 0 → 1, reduced-motion and no-JS keep all content visible; gate v7 passes 9 routes, 182 offline + 81 DB, 0 overflow and 0 console errors at five widths. Copy/phone pass: phone bubbles stagger to opacity 1, cap meter fills to scaleX 0.187, no repeated disclaimer strings, dead CSS removed. **Production proof 2026-11-04:** pushed `61022f6..c16b924`; Vercel served it 30s later; production has 0 overflow, 0 console errors and 0 hidden reveals at 1440/1024/768/390/360; reduced-motion and no-JS keep all content visible; zero violet in markup; Render `/health` 200. Screenshots `.scratch/final_*` (production). **Handset connect + OAuth PASS 2026-11-04** (DB token and inbound receipts). Reconnect, address writes and the remaining live journeys are still open. |
| Landing audit fixes | **DONE 2026-11-01, shipped 2026-11-02:** removed all three skip links and dead chat/lock CSS; deleted the dead `hero-chat.tsx` and `lock-demo.tsx`; fixed invisible focus targets, full-bleed section edges (removed `scrollbar-gutter`), the 1024px hero squeeze, stamp overflow, and the sample Pay button. Security headers are live; the OAuth state cookie and origin check are parked for a handset test. Copy corrected: reorder/past-order claims, sample-only coupon, “no order leaves the chat”, delete-my-data wording, basket vs cart. |
| Recent Next advisories | **FIXED 2026-11-03:** upgraded Next 16.2.6 → 16.4.3 (`--save-exact`). `npm audit --omit=dev` → 0 vulnerabilities; `npm run build` passes all 7 routes. |

---

## 1. Current State — One Screen

| Item | State |
|---|---|
| Documentation sync | **DONE 2026-10-27, scope corrected 2026-10-27.** Recipes are in v1 as plan-confirm-add; proactivity is money-and-truth only; replies stay English. Stale "current" notes were removed from PRD, ARCHITECTURE, DESIGN, GLOSSARY and the ADR index. The scope table lives in `TASKS.md`. |
| Doc truth pass | **DONE 2026-10-28:** corrected pre-Batch-3 claims in ARCHITECTURE Layer 2/4, DESIGN A2/A6/A8/A9, PRD payment, GLOSSARY fee term, ADR index rows 0003–0006/0009, STATUS counts/constraints/next action, and the verify-grocer skill. No code changed. |
| Lint | **PASS 2026-10-28:** `ruff check backend tests` → `All checks passed!` The `npm run lint` script was removed 2026-11-01; Next 16 no longer ships `next lint` and no ESLint is installed. |
| Verify 2026-11-04 | **PASS:** `verify.ps1 -Db` exit 0 (schema, ruff, 177 offline + 78 database tests, Next 16.4.3 build). Browser checks from 2026-11-01 still stand: 0 horizontal overflow at 1440/1024/768/390/360; first Tab lands on the brand; no skip link; `/privacy` and `/proof` render. Security headers are live; the OAuth state-cookie patch is parked. `npm audit --omit=dev` → 0 vulnerabilities. A real signed "show my addresses" turn proved the new trace (`.scratch/trace_turn_20261103.log`), a real cart-lock turn returned the recovery copy (`.scratch/trace_cart_lock_20261103.log`), and a real tracking turn returned "You have no active order right now." with no invented link (`.scratch/live_retest_tracking.log`). Retest proof: `.scratch/verify_retest_20261104.log`. Deletion proof: `.scratch/verify_lean_20261104.log`. |
| Offline tests | **PASS 2026-11-04:** 182 offline + 81 DB = 263 passed, 20 live deselected (`pytest -q -m "not live"`). |
| DB tests | **PASS 2026-11-04:** 78 passed on `grocer_test`, and `verify.ps1 -Db` exits 0 end to end (schema check, ruff, offline + DB tests, Next production build) after the batch-4 dedupe. |
| Basket path | **DONE 2026-10-28, merged in `2c63289`:** adds always add and increment an existing line; sizes are exact (200 g never becomes 400 g, 500 g never becomes 1 kg); every missing item is named; explicit set applies with a receipt; remove/clear still confirm. Abuse caps: 20 messages/hour/user, 10 items/message, quantity 1–99, media reply. Proof: 146 offline + 73 DB + Next build; exact paneer/rice regression test. Live route check: 3 cases pass; multi-item, eggs, Hinglish, bare "milk" and remove were blocked by the shared Groq TPM. |
| Swiggy error envelope | **DONE 2026-11-03:** a Swiggy tool answer with `success: false` now raises `SwiggyToolError` instead of being parsed as cart data, and the webhook replies "Swiggy couldn't complete that just now: <reason>. Check your basket before trying again." A live cart refusal that returned HTTP 500 on 2026-11-03 now returns 200 with that honest text. Proof: 5 new tests (2 client error-envelope, 2 picker labels, 1 webhook no-500) and `verify.ps1 -Db` exit 0. |
| Truth fallbacks + turn trace | **DONE (code) 2026-11-03:** a `pay` tap with no pool, approval or user now says "I couldn't start the payment just now. Nothing was charged. Please try again." and returns `checkout_unavailable`; an unknown button returns `unknown_action` with a resend message. Every processed text/button turn emits one JSON payload with the wamid as request id, capability, safety, status, latency, Swiggy calls, model calls and fallbacks; each Swiggy and model call logs its own line. No message text, phone or address is logged. The evaluator now reports `source: llm | fallback | rule`, and the live catalog file fails if a case skipped the model. Proof: 4 new tests; `verify.ps1 -Db` exit 0; real signed turn trace (`.scratch/trace_turn_20261103.log`). |
| Batch 2 — cart recovery and retries | **DONE (code) 2026-11-03:** a Swiggy cart-review error now replies with exact recovery steps ("Open Swiggy → Instamart → Cart, accept the adjusted quantities, then send your request again") on both the read path and the webhook path. A first-time texter's message is parked (`awaiting_link`) and replayed after they connect instead of being lost. Swiggy HTTP 429 and JSON-RPC -32000 retry once, honor `Retry-After` capped at 5s, log `swiggy_retry`, and a second cap gets an honest "Swiggy is busy" tool error. Proof: 5 new tests; live cart-lock turn returned the recovery copy (`.scratch/trace_cart_lock_20261103.log`); `verify.ps1 -Db` exit 0 (160 offline + 77 DB). |
| Batch 3 — honest button taps + one cap helper | **DONE (code) 2026-11-03:** every write button (cart, plan, reorder, address, item change, budget raise) now tells the customer "Nothing changed. Please try again." when the database or their account is missing, and the default fallback names a stale button. No branch returns silently or claims a change that did not happen. The three duplicated session-cap queries now go through `get_session_budget_cap`; a missing or zero cap still falls back to ₹1,000. Proof: 7 new tests; `verify.ps1 -Db` exit 0 (166 offline + 78 DB); `.scratch/verify_batch3_20261103.log`. |
| Batch 4 — dedupe money, plans, client building | **DONE (code) 2026-11-04:** one paise conversion (`rupees_to_paise`) now backs `parse_price_to_paise`; one `decode_pending_plan` replaces both stored-plan JSON decoders; one `resolve_user_client` builds a Swiggy client from the stored token for five button branches, the checkout pollers and parked replay. `send_add_receipt` was already the single receipt builder, so no new one was added. Deleted five uncited `.scratch` logs and the superseded `proof-final/` and `proof-redesign/` folders. Proof: 3 new tests; `verify.ps1 -Db` exit 0 (169 offline + 78 DB); `.scratch/verify_batch4_20261104.log`. |
| Item 5 — exact brand+size skips the evaluator | **DONE (code) 2026-11-04:** when the router extracted an add and every item names a brand and size that match exactly one in-stock candidate (with an address), the add path builds the result itself and makes no evaluator model call. Vague, ambiguous, missing-size or zero-address turns still use the model. Proof: 3 new tests, including a sentinel that fails if the evaluator runs for "Amul milk 500 ml" and a call-count check for "milk"; `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_item5_20261104.log`. Live before/after timing still waits for adds. |
| Cleanup — truth, dead code, over-engineering | **DONE (code) 2026-11-04:** removed the invented `swiggy.com/track/...` links and the default "10-15 mins" ETA; tracking shows only Swiggy's real status, ETA and rider. Deleted `CheckoutLockError`, `VALID_MILESTONES`, the `map_url` field, the stale `__all__`, the dead `answer_read_capability` wrapper and the one-method `AddressLifecycleManager` class. Inlined the single `delete my data` command, added one `MAX_BUDGET_CAP_PAISE`, made `migrate.py` reuse `verify_db.py`, and merged the duplicated pack-ratio math. Site now says 255 tests locally. Proof: `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_cleanup_20261104.log`. `backend/channels/command_router.py` was deleted after Karan named it. |
| Retest — different examples | **DONE 2026-11-04:** exact-match skip now also proven with Nandini milk 500 ml, Aashirvaad atta 5 kg and Maggi noodles 280 g; ambiguous Lay's 50 g and size-less "Amul milk" still call the evaluator; the confirmed milestone no longer says "10-15 mins" or carries a link. Live signed "where is my order?" returned HTTP 200 with "You have no active order right now." and no invented link. Proof: 5 new tests; `verify.ps1 -Db` exit 0 (177 offline + 78 DB); `.scratch/verify_retest_20261104.log`; `.scratch/live_retest_tracking.log`. | — |
| Cleanup — one provider | **DONE 2026-11-04:** deleted the Gemini adapter (`_gemini_json`), the three `GEMINI_*` settings, `google-genai` from `requirements.txt`, and the `gemini` choice in `eval_router.py`. `complete_json` now answers only through Groq; any other provider name fails honestly as unknown. ADR 0012 amended; AGENTS, PRD, ARCHITECTURE, GLOSSARY and STATUS synced. Proof: `verify.ps1 -Db` exit 0 (177 offline + 78 DB, ruff clean, Next build); `.scratch/verify_gemini_removal_20261104.log`. | 
| Live scorecard | **DONE 2026-11-04, 25/26 (96.2%):** half one 12/13, half two 13/13, against the deployed app with the real cart. The cart was cleared through the stored token first (0 items); every add returned 200 with a live receipt. Case 3 missed only because the live account returns no payment methods on an empty cart — case 21 later proved the UPI list with items, so the bot told the truth and the case expectation was wrong. Case 17 was mislabeled: dragon fruit is now in stock and was added correctly, so it proved nothing about a missing item; it is replaced by "add a unicorn steak". Raw: `.scratch/scorecard_live_20261104_1_13.json`, `.scratch/scorecard_live_20261104_14_26.json`; transcript: `.scratch/scorecard_20261104_1_13_transcript.log`. |
| Handset taps | **DONE 2026-11-04:** 10 button replies reached the bot from Karan's handset between 11:16 and 16:29 IST: `cart:clear` ×3, `cart:fresh` ×2, `item:change`, `pay` ×2, `addr:set`, `plan:add`. The plan Add all at 16:28 filled the basket with the pasta plan; both Pay taps hit the locked checkout and nothing was ordered. No phone number or address is recorded here. |
| Pass 2 — live test honesty | **DONE 2026-11-04:** case 3 now passes on either a method list or a truthful empty-basket answer; case 17 now asks for an item Swiggy does not sell and must not say "added". Live testing found one real bug: the remove-miss reply named only 3 basket lines and silently dropped the rest; it now says "and N more" for both the miss and the ambiguity reply. Proof: 2 new tests written red then green; `verify.ps1 -Db` exit 0 (179 offline + 78 DB, ruff, Next build); `.scratch/verify_pass2_20261104.log`. The internal `/proof` page shows 257; the landing no longer shows test counts. |
| Duplicate-name picker | **DONE (code) 2026-11-03:** "Which one do you mean" now names each line with its pack variant and current quantity, and a follow-up can match the variant ("500 ml"). Two same-name milk lines no longer render identical labels. Proof: 2 new offline tests. The `item:change` button was tapped on a handset on 2026-11-04; a same-name choice on a handset is still open. |
| Live route check | **PARTIAL 2026-10-28:** on the branch, "add 1 litre milk" → add 1 L; "add 1 more milk" → add 1; "make milk 3" → set 3. The remaining five live wordings were blocked by the shared Groq TPM, not by an error; the fixture tests for those paths pass. |
| Live deploy 2c63289 | **PASS 2026-10-28:** push `d61b142..2c63289` accepted; Render deploy `dep-dbh0vkavcj2c73e0ghqg` reached `live` on `2c63289`; `GET https://grocer-backend-qwk4.onrender.com/health` → HTTP 200 `{"status":"healthy","database":"connected","app":"Grocer","environment":"development"}`. GitHub Quality run `40712848895` succeeded on `2c63289`. |
| Live tests | **20 live-only tests collected, not run.** `test_catalog_search.py` calls the live router/model path and is marked `live`. |
| Full test collection | **283 tests collected 2026-11-04** (182 offline, 81 DB, 20 live). |
| Full suite claim | The old "136 passed, 0 skipped" claim is retired. The current verified set is 182 offline + 81 DB (283 collected, 20 of them live-only); live is excluded by default. Scripted tests are marked `scripted` and never counted as live proof. |
| Live Swiggy smoke | **PASS 2026-10-27:** real token, real MCP. 3 addresses, 20 milk products with live prices, 12-item cart read, 0 orders, 10 payment methods, 0 coupons. Cart add verified then restored (12 items, same spins and quantities). No order placed. Raw: `scripts/live_smoke.py`. |
| Live Groq pass | **PASS 2026-10-27:** 10 real messages → 10 correct routes (item_info ×3, list_addresses, order_history, list_coupons, payment_options, add_items, chat, track_order) with real read answers. 55s. |
| Live checkout lock | **PASS 2026-10-27:** with `LIVE_CHECKOUT_ENABLED=false`, the real path returned "Checkout is locked" and a sentinel client proved no Swiggy method ran. |
| Checkout deploy lock | **DONE 2026-10-27:** `LIVE_CHECKOUT_ENABLED=false` is enforced in `execute_3_lock_checkout` before any Swiggy call. A test proves no client call and no approval consumption while locked. |
| Checkout money core | **DONE (simulated) 2026-10-27:** claim, attempt row and result each commit separately; no transaction spans the Swiggy call. CAS binds approval + user. UPI sends `generateUPIQR`. Timeout/5xx reconciles against `get_orders` with one retry; stuck attempts are resolved by the payment poller. Cap raise returns the receipt to payable. Proof: 8 new DB tests incl. duplicate, concurrent, crash, timeout, unconfirmed and cap-raise. Never live-tested. |
| Inbound dedupe | **DONE 2026-10-27:** user + `inbound_messages` row commit before the turn; the per-user lock is session-scoped and asyncpg releases it on pool release (probe run). |
| Post-payment truth | **DONE (code) 2026-10-27:** `track_order` is called with saved coordinates, with `get_delivery_status` as the no-map fallback. `store_info` answers honestly instead of inventing a store or window. Split orders poll every order id; each order+milestone fires once via `notified_milestones` (migration 004). A payment made while Render slept is confirmed on wake; an auth failure leaves the row pending instead of failed. Proof: 3 new DB tests, 5 read tests. |
| Test isolation | **DONE 2026-10-27:** `grocer_test` database live; the DSN guard refuses any test DSN that is not `grocer_test`. |
| Account lifecycle | **DONE (code) 2026-10-27:** grounding uses Swiggy's default address, not `addresses[0]`. A mid-basket switch warns, then clears and rebuilds the basket at the new store and names what is missing. The active-delivery delete guard runs on the real delete path. Typed-text address add geocodes through `recommend_address(query=...)`. OAuth login only accepts a signed bot link. Parked lists replay automatically after login. |
| No fake sends | **DONE 2026-10-27:** the production mock branch in `WhatsAppClient` is gone. Tests inject a recording client instead, so a test can never silently "deliver" to nobody. |
| Conversation trust (Phase 7 Batch 1) | **DONE (code) 2026-10-27:** AI outage now says so instead of "I didn't catch that", with an 8-second deadline and one retry only when it can help (`backend/agent/router.py`, `backend/agent/llm.py`). Every inbound message is marked read with a typing indicator (`backend/channels/whatsapp_client.py`, `backend/channels/whatsapp.py`). Receipts show the delta, Swiggy's stock cap, the old basket and the total; `Keep only new` is stateless (`backend/agent/composite_cart.py`, `backend/agent/basket_actions.py`). A total above the ₹1,000 cap is named at add time. `view_basket` answers "what's in my basket". Address cards are shortened with up to 3 switch buttons. Vague staples auto-pick with a working `Change item` and swap; discretionary items show choices; the blind rank-1 fallback is gone. Out-of-stock answers name real `similarProducts`. Every route decision is logged as JSON with latency. A text after an hour idle with a non-empty basket gets a Keep/Clear prompt. |
| Code cleanup (repo audit) | **DONE 2026-10-27:** removed 1,212 lines and added 442 (including the new test fixture client), net -770. Deleted three dead formatter functions and module, a 97-line duplicate go-to/address-switch engine, the unused small-cart fee and launch-cap helpers, the test-only park helpers, the dead milestone helper, and the legacy 2-part cap raise. Removed seven settings with no reader, the duplicate `AddressReply`, the unused `LLMResult.model`, dead evaluator result fields, the parsed-but-unused button title, unused client header/footer params, and frontend dead paths. Moved the fixture playback engine out of the production Swiggy client into `tests/fixture_client.py`. Fixed `drive_grocer.py` checking 6 tables instead of 8. No money or lock logic changed. Dead schema columns and the unused approvals index are deferred to Phase 6. |
| Live Batch 1 check | **PASS (routing) 2026-10-28:** real signed messages to the Render app. `milk` → HTTP 200 `cart_updated` in 11.9s; latest approval is ₹283 with 2 items including milk. `what's in my basket` → HTTP 200 `view_basket` in 4.8s, 359-char reply with 2 item bullets. `show my addresses` → HTTP 200 `list_addresses` in 4.1s, 366-char card with 3 numbered entries. No order, no checkout. Blue ticks/typing are unproven because the wamid was simulated. Fixed 2026-10-28: session history now stores the real receipt (see the next row). |
| Live basket receipt | **PASS 2026-10-28:** after the receipt fix, a real `1 litre doodh` turn returned a full basket with `＋` on the new line, `You had 3 items (₹283)` and `Your Basket (4 items)`. No "Ask *what's in my basket*" copy. The receipt is stored in session history now. |
| Live natural-language eval (20 cases) | **MIXED 2026-10-28:** 20 messy messages against Render, real Groq + real Swiggy, no fixtures. 13/20 answered on the first pass. 7/20 got the honest AI-outage copy from Groq's 8k TPM burst limit; retried with 20s spacing, 5/7 then passed. Genuine failures: `make pizza for 5 people` asked "How many pizza bases?" instead of a recipe plan, and `add milk and bread` only handled the milk. Copy gap: the existing-milk prompt says "Do you want the total to be 1, or 1 more?" which is confusing. `show payment options` lists COD and Swiggy Money even though v1 supports UPI only; `is the store open` gives a quote, not a yes/no. Raw: `.scratch/live_eval_20.json` and `.scratch/live_eval_retry.json`. |
| Reactions and card emojis | **DONE (code) 2026-10-28:** one reaction per inbound message, chosen by Python from the turn outcome (`backend/channels/reactions.py`), sent off the critical path after the reply (`backend/channels/whatsapp.py`). 🏠 addresses, 🛒 basket, 📦 orders, 🛵 tracking, 🎟️ coupons, 💳 payments, 🍳 meal plan; ❓ when the bot needs a choice; 📍 when it asks for a pin. No reaction on chat, misses, locks, auth or outages. Cards carry at most one header emoji (address, orders, track, coupons, payments, reorder); error and money copy carries none. Payload: `backend/channels/whatsapp_client.py`. Proof: `verify.ps1 -Db` exit 0, 113 offline + 52 DB, including a signed-webhook test that asserts exactly one 🏠 for an address question. Meta's live reaction delivery is unproven until a real inbound wamid is reacted to. |
| Batch 2 first slice | **DONE (code) 2026-10-28:** multi-item text adds now process every requested item. Root cause of the eval failure `add milk and bread`: the single existing-item branch returned early and dropped bread. That branch now runs only when exactly one item is asked for, and its copy/buttons say "Add 1 more" / "Make total 1". Recipe plans are live in code as plan-confirm-add: a new `plan_meal` read capability carries dish + servings + ingredient packs from the model; `backend/agent/meal_planner.py` searches and prices each line; `[Add all]` re-checks live stock and writes all ingredients or none; `[Let me pick]` asks for item numbers. The plan card is stored in dialogue history. No hardcoded recipe list (ADR 0011). Proof: 5 new offline tests, 5 new webhook tests, 1 router test; full gate 113 offline + 52 DB. The live Groq route for "make pizza for 5" and a live Add-all tap are not tested yet. |
| Q3 AI load fix | **DONE (code) 2026-10-28:** one Groq call gate shared by routing and item evaluation (`backend/agent/llm.py`). Calls are spaced; a 429 or a zero-token header parks every thread until the reset; a wait longer than an 8-second call budget fails honestly instead of hanging. Multi-item turns now evaluate all items in one model call (`evaluate_customer_intents_batch`), with per-item deterministic fallback and no extra call (`backend/agent/candidate_evaluator.py`). A 4-item add drops from 5 model calls to 2. Proof: `verify.ps1 -Db` exit 0, 120 offline + 52 DB, 192 collected; 7 new queue/batch tests. Live Groq burst behavior is not re-tested. |
| Q1/Q2 stored plan and pack math | **DONE (code) 2026-10-28:** the exact priced recipe plan is stored in `grocer.sessions.pending_plan` with a 30-minute expiry (migration 005), replacing the old base64 button token. The model now gives each ingredient an amount and unit (`250 g`, `1 l`, `5 pieces`); Python reads the store pack size (`backend/agent/meal_planner.py:parse_pack_size`) and computes whole packs, falling back to the model's pack count when the store text cannot be compared. Add-all re-checks live stock and writes all or none; the confirmed SKU is never swapped for a lookalike — a gone SKU is reported missing. Picks write only the chosen rows. The plan is cleared after a write, on expiry, by the 24-hour DPDP scrub, and by "delete my data". The numbered reply to `Let me pick` is now real: number-shaped text ("1 and 3") picks items with no model call, and anything with words routes normally. Proof: new pack-math, stored-spin, gone-SKU, partial-pick, expired-plan, typed-picker and plan-cap tests; `verify.ps1 -Db` exit 0, 142 offline + 61 DB, 223 collected. Live recipe route and a live tap are still unproven. |
| Router eval (live Groq) | **PASS with one miss 2026-10-27:** 39/40 exact (97.5%), 0 unsafe writes, 0 under-acted writes, 0 LLM errors. Miss: "how long till my food arrives" → `store_info`, expected `track_order`. Latency was not recorded by the harness. Raw: `.scratch/eval_phase2.json`. |
| Router eval rerun (live Groq) | **PASS 2026-10-28:** 40/40 exact (100%), 0 unsafe writes, 0 under-acted writes, 0 remaining LLM errors. Latency: avg 1574ms, p95 2265ms, max 3422ms. One 429 on case 11 was retried and passed. Raw: `.scratch/eval_router_20261028_reviewfix.json`. |
| One LLM brain | **DONE 2026-10-27:** routing and candidate evaluation both call `backend/agent/llm.py`. Direct Gemini calls and the second classification call are gone. Gemini adapter and dependency removed 2026-11-04; Groq is the only provider. |
| Live reads | Recorded live on 2026-10-26: price/stock, addresses, order history, cancel help, payment options, coupons. Not re-run on 2026-10-27. |
| Live refresh | Recorded 2026-10-26: forced refresh returned a new token pair; new expiry 2026-11-25. Journal also records a fixture-only refresh proof. Treat the live proof as recorded, not re-verified. |
| Live checkout | **Never tested. No order placed.** |
| Migration 004 | **VERIFIED 2026-10-27:** `python scripts/migrate.py` applied `004_checkout_milestones.sql` to the app database; `verify_db.py` exits 0 with 8 tables, `notified_milestones` present, and the required indexes. `grocer_test` is also at 004. |
| Phase 6 privacy slice | **DONE (code) 2026-10-28:** 24h scrub clears onboarding state/context, plan-time coordinates, geocode rows older than 24h, and expired PKCE states. "delete my data" deletes inbound messages and geocodes, clears plan/onboarding/coords, and anonymizes the user row. Migration 006 adds `updated_at` triggers and non-negative money checks. Migration 007 adds the non-superuser `grocer_app` role (DML on the 8 app tables, no CREATE) and drops the two never-read columns; 009/010 make the migration ledger read-only for that role. App queries run as that role, a DDL attempt is refused, and a missing role fails loudly. `anon`/`authenticated` have zero schema usage and zero table grants, so RLS is skipped by design, not by omission. Migrations 001–010 are applied to the app DB. No Render env change was made. Live 24h scrub after a real TTL is pending. |
| Block 1 hardening | **DONE (code) 2026-10-28:** PKCE state moved from process memory to `grocer.oauth_states` with a 10-minute TTL and one-time consume (migration 008); expired rows are deleted on consume and by the scrub. Startup waits at most 5 seconds for the DB, then serves with `/health` 503 and retries migrations with backoff. Migrations run on a separate owner connection; the app pool refuses to run without `grocer_app`, so there is no owner fallback. Rupee-to-paise conversion uses `Decimal(str(value))` in every schema property and the order bill. Proof: 141 offline, 66 DB, 227 collected; real dead-DB subprocess test, role DDL/ledger-refusal test, PKCE TTL/expiry test, backdated scrub test. |
| Migration 005 | **APPLIED 2026-10-28:** `python scripts/migrate.py` added `sessions.pending_plan` and `sessions.pending_plan_expires_at` to the app database; `verify_db.py` exits 0. `grocer_test` applied it through the DB suite. Render applies pending migrations at startup on the next deploy. |
| Migrations 007–010 | **APPLIED 2026-10-28:** `python scripts/migrate.py` applied 007 (grocer_app role, two dropped columns), 008 (`grocer.oauth_states`), 009 (ledger write revoked), and 010 (ledger read restored) to the app database. `verify_db.py` exits 0 with 9 tables, proves app queries run as `grocer_app`, no CREATE on `grocer`, and no INSERT on `schema_migrations`. `grocer_test` applied them through the DB suite. |
| Live deploy 50fc967 | **PASS 2026-10-28:** pushed `b03573c..50fc967` to the branch then in use (now `main`); Render deploy `dep-dbgugmi9lscs7394rr80` built that commit and reached `live`. `GET https://grocer-backend-qwk4.onrender.com/health` → HTTP 200 `{"status":"healthy","database":"connected","app":"Grocer","environment":"development"}`. No env var was changed. |
| Repo and CI cleanup | **DONE 2026-10-28:** `main` and the old working branch had unrelated histories, so `main` was replaced by the current tree (`git push --force-with-lease`), not merged; old tips are kept as tags `legacy-main-2026-10-28` and `legacy-codex-2026-10-28`. `codex/full-whatsapp-recovery`, `feat/architecture-v1`, `redesign`, and the old working branch are deleted; `main` is the only branch. Old `v2.0.0` and `checkpoint-working` tags were deleted on 2026-10-28. Renamed the product from the old v1 label to "Grocer" in code headers, docs, package name, journal headings, and the env template; old branch names in journal lines now read `main`. Added `README.md` and two workflows (`quality.yml`, `keep_warm.yml`). The first CI run failed because CI installed ruff 0.17.3 while the local gate ran 0.16.6; 0.17.3 flagged seven `datetime.UTC` style findings, which were fixed, and `requirements.txt` now pins `ruff==0.17.3`. Proof: run 40688131830 backend failed on lint; the runs for `42d5b56`, `da5853a`, and `c4ea0a3` have backend and frontend `success`; local ruff 0.17.3 passes. |
| Live deploy 42d5b56 | **PASS 2026-10-28:** Render service branch changed to `main`; auto-deploy on commit. Deploy `dep-dbguma942hec739cfba0` for `42d5b56` is `live`; `/health` is 200 with `database: connected`. No env var was changed. |
| Landing page live | **PASS 2026-11-04:** pushed to `main`; Vercel serves the exact-palette landing (HTTP 200, no violet/yellow, five accents, `Connect Swiggy`, form present). Production passes 0 overflow and 0 console errors at 1440/1024/768/390/360, `/api/auth/whatsapp/start` returns a real signed 10-minute token, and the Render `/health` is 200. The number is never committed; it lives only in the Vercel env. Handset OAuth remains unproven. |
| Live eval 2026-10-28 (26 cases) | **MIXED:** 26 signed webhooks against Render with the real Swiggy MCP and Groq. Reads passed: basket, addresses (3 saved), payment (UPI only), coupons, store quote, orders/bill/tracking (none, honest). Writes passed: single add, multi add, banana, sugar, salt; a double text produced two separate approvals with no lost write. Honest limits passed: usual, last bill, report, cash. Recipe plan priced 5 items at ₹1014. Failures: "add 200g paneer, 1 packet gulab jamun and 500g rice" and the Hinglish milk+eggs message were routed to `change_item` and lost the other items; the router prompt and a multi-item guard were fixed (`f285b00`, 2 new tests). The paneer case passed after the fix but silently omitted the rice and added a second paneer SKU; the Hinglish retest was blocked by Groq's daily cap. "5 kg almonds" added one ₹1398 pack and only warned about the ₹1,000 cap. Reactions/read receipts cannot be tested with simulated wamids (Meta 400 "Invalid message_id"); a direct reaction to a real wamid returned 200. Groq hit its 200k tokens/day free cap (199,068 used; retry 8m50s) and the bot answered with the honest AI-offline copy. The webhook timing test was isolated from the real WhatsApp API after it failed on Meta latency. Full gate after the fixes: `verify.ps1 -Db` exit 0, 144 offline + 66 DB, build pass. Raw: `.scratch/live_eval_25.json`. |
| Scorecard (merged) | **BUILT 2026-10-28 on `scorecard`, merged 2026-10-31 in `a8e530c`:** `tests/test_scorecard.py` + `tests/scorecard_cases.json` (31 cases, expectations written from customer intent) and `scripts/scorecard_live.py` (26 cases against the deployed webhook). The offline run hands the plan to the pipeline, so it scores Python with the model out of the loop: **31/31 = 100%**, up from 28/31 before the three fixes below. Live on Render since 2026-10-31. |
| Offline scorecard findings | **FIXED 2026-10-28 on `scorecard`, merged 2026-10-31 in `a8e530c`:** candidates are now ranked by how many of the customer's words they match, so a qualifier like "brown" wins; when the picked pack does not fit the amount, the fewest exact packs are taken instead of asking ("2 kg atta" → 2 × 1 kg); and `pack_plan` splits across sizes ("1.5 litres" → 1 L + 500 ml), capped at 12 packs per line. Proof: `tests/test_scorecard.py` 31/31, `pytest -m "not live"` 221 passed, ruff clean. Candidate selection no longer uses keyword lists: the older `staple_terms`, `discretionary_hints` and `size_patterns` tables are deleted, leaving one ranking rule (unique best match wins, a tie takes Swiggy's first pick and offers Change). Net −49 lines in `backend/agent/candidate_evaluator.py`. |
| Live scorecard | **RUNNING 2026-11-04:** Karan authorized the stored token to read and add, no order. The cart was cleared through the token (`clear_cart` verified, 0 items) and cases 1–13 scored 12/13 (reads 7/8, adds 5/5). Case 3 (payment options) got a truthful empty list on an empty cart. Second half `--start 14 --end 26` earliest 12:25 IST because the bot allows 20 messages per rolling hour and six handset messages landed at 11:23–11:24. The 2026-11-03 pre-fix half scored 7/13 with 500s from the error envelope; after the fix a live add returns 200. Earlier: **25/26 = 96.2%** on 2026-11-02. Raw: `.scratch/scorecard_live_20261104_1_13.json`, transcript: `.scratch/scorecard_20261104_1_13_transcript.log`, earlier: `.scratch/scorecard_final_1_13.log`. |
| Router eval (branch, post four-verbs) | **PASS 2026-10-31:** 40/40 exact, 0 unsafe writes, 0 under-acted, 0 safe-path fallbacks, 0 errors; avg 1312ms, p95 1735ms, max 1889ms. Equal accuracy to the pre-change 40/40, faster latency. The 10 write-verb cases were 10/10 on 2026-10-29. Raw: `.scratch/eval_after_verbs.json`. |
| Live deploy a8e530c | **PASS 2026-10-31:** PR #3 CI green (backend + frontend on Linux + Postgres); fast-forward merge `db6a297..a8e530c`; Render deploy `dep-dbiupgivcj2c73edh5t0` reached `live` on `a8e530c`; `/health` → HTTP 200 `{"status":"healthy","database":"connected","app":"Grocer"}`. No migrations, no config or env changes. |
| Post-merge live smoke | **PARTIAL 2026-10-31:** on `a8e530c`, basket and addresses 2/2, add 1 litre milk 1/1, all HTTP 200. `make milk 3` and `remove the milk` both returned a 200 disambiguation prompt because the basket holds two milk lines with the same display name; the picker showed two identical labels. The labels are fixed in code on 2026-11-03 (variant + qty); the tap still needs a real handset. Raw: `.scratch/smoke_custom.py`. |
| Production readiness | **No.** |
| Current gate | **Gate 2 — Concierge Answers.** 6 of 8 pass; 1 partial (reorder needs a past order); 1 code-complete but not tapped live ("milk" now auto-picks with a working Change button, discretionary items show choices). See §2. |

---

## 2. Gate 2 — Actual Results

Gate 2 is read-only. No checkout, order, payment call, or address write is in scope.

| # | Customer says | Required | Actual | Result |
|---|---|---|---|---|
| 1 | "How much is Amul milk?" | Real price and pack size; cart untouched | Read path built; live result recorded 2026-10-26 | **PASS (recorded)** |
| 2 | "Is Amul milk in stock?" | Real availability at the default store | Read path built; live result recorded 2026-10-26 | **PASS (recorded)** |
| 3 | "Which store? When will it arrive?" | Real store and delivery window | Honest: the cart quote plus "Swiggy doesn't share the dark store name or a delivery window before an order is placed" (`backend/agent/read_actions.py:66`) | **PASS (honest)** |
| 4 | "What addresses do I have?" | The 3 saved addresses, default marked | Live 2026-10-27: 3 addresses, default marked | **PASS** |
| 5 | "Show my last orders" | Real history; 0 is truth | Live 2026-10-27: 0 orders, said so | **PASS** |
| 6 | "Where is my order?" | Track the order or say there are none | `track_order` with saved coords, `get_delivery_status` fallback; with 0 orders says so (`backend/agent/read_actions.py:129`) | **PASS (no-order path live)** |
| 7 | "Reorder that" | Build the basket, stop before checkout | Fixture-proven only; live write blocked because the account has 0 orders | **PARTIAL** |
| 8 | "milk" | Never silently substitute; name the pick and offer a working Change, or show real products | A staple auto-picks with a `Change item` button that lists real alternatives and swaps on tap. Discretionary items show choices. Blind rank-1 fallback removed | **PASS (code) — live tap pending** |

**Done means:** every case shows its real answer, `ruff` clean, offline tests green, and docs updated. That is not met.

---

## 3. Capability Truth

| Safety class | Capabilities | Reality |
|---|---|---|
| **read** (13) | chat, item_info, store_info, view_basket, list_addresses, order_history, order_bill, track_order, list_coupons, payment_options, cancel_help, plan_meal, placed_order_add | Ten are live-proven. `view_basket` reads the real cart and is fixture-tested; it needs a WhatsApp read. `plan_meal` is built and fixture-proven (2026-10-28), stores its priced plan for 30 minutes, and accepts a typed numbered pick; the live Groq route for "make pizza for 5" is not tested. `store_info` gives the live cart quote and says Swiggy does not expose the store or window. `track_order` calls the tracking tool when coordinates are saved, else delivery status. |
| **basket** (5) | add_items, set_item, remove_item, clear_basket, reorder | Four are live-proven: add, set ("make milk 3"), remove ("remove the milk") and clear each routed correctly on 2026-10-29. Reorder's live write is blocked by the locked checkout. One routing call plus one batched evaluation call per turn (ADR 0012, amended 2026-10-29 to four write verbs). |
| **account** (4) | add_address, switch_address, delete_address, report_issue | Address list works live. Switch warns, clears and rebuilds the basket at the new store. Delete is blocked while a delivery is in flight and guarded again on the final tap. Typed-text add geocodes and reuses the flat/name/city steps. Live add/delete is still unproven (needs the one throwaway address). |
| **money** (1) | checkout | Button path is wired end to end and no longer holds a DB transaction across the Swiggy call. Text "place the order" returns a not-ready reply by design: Lock 1 requires a physical tap. Never live-tested; no order placed. |

**Capability count:** 23 declared. 22 are dispatched from the router; `checkout` is reachable only from the pay button, by design (Lock 1).

---

## 4. P0 — Fix Before Any Live Order

**No P0 is open as of 2026-10-27.** The last one is fixed in Phase 5 below.

**Fixed in Phase 3 (2026-10-27):**

1. **Checkout ran inside a DB transaction.** `execute_3_lock_checkout` now takes the pool and commits the CAS, the attempt row and the result separately. No transaction spans a Swiggy call, and `button_router` no longer opens one. Proof: duplicate-tap, concurrent-tap and crash tests in `tests/test_checkout_locks.py`.
2. **UPI arguments were incomplete.** `SwiggyClient.checkout` sends `generateUPIQR=true` for UPI, or `intentApp` when one is given. Proof: `test_upi_checkout_sends_qr_request`.
3. **Not idempotent; retry guard unused.** The pre-checkout snapshot is now required. On timeout/5xx the order list is compared with it, the call retries once only, and `reconcile_attempting_checkouts` resolves attempts left by a crash. Proof: timeout-recovered, clean-failure, unconfirmed and crash tests.
4. **Lock 1 did not bind the approval to the tapper.** The CAS matches `id + user_id`, and the webhook passes the real `message_type` instead of a hardcoded one. Proof: `test_lock_3_cas_rejects_another_user`.
5. **Budget-raise was a dead end.** A cap failure returns the approval to `shown`. The button carries `budget:raise:<approval_id>:<paise>`; the handler raises the cap and re-sends the pay button. Proof: `test_cap_raise_keeps_receipt_payable`.
8. **Dedupe could roll back.** The user and `inbound_messages` rows commit before the turn runs. The per-user lock is session-scoped; a probe proved asyncpg releases it when the connection returns to the pool.

**Fixed in Phase 4 (2026-10-27):**

7. **Pollers could die, spam and skip orders.** `SwiggyAuthExpiredError` is now caught by every loop and by each row inside the payment batch, so one 401 no longer aborts the batch or marks a payment failed. Each order id in a split checkout is polled, and `notified_milestones` (migration 004) sends each order+milestone once. A pending payment older than five minutes is checked on wake rather than failed blindly. Proof: split-milestone, wake-payment and auth-failure tests.

**Fixed in Phase 5 (2026-10-27):**

6. **Park and replay were disconnected.** The webhook now parks as `awaiting_link`, the OAuth callback stores the token and schedules `replay_parked_request`, and the replay runs the stored message through the normal webhook pipeline under a fresh `wamid.replay.*` id. A failed replay puts the row back to `awaiting_link` instead of losing the list. Proof: `test_park_sends_a_signed_reconnect_link`, `test_replay_reruns_a_parked_text_once`, `test_token_expiration_parks_request_and_replays`.

**Honest limit:** none of this is proof that a live order works. It is proof that a live order cannot double-place or charge without a tap.

---

## 5. P1 — Real, Lower Blast Radius

- Every write button now answers honestly when the database or the customer's account is missing; no tap returns a silent no-op. Fixed 2026-11-03 (batch 3).
- A first-time location pin is still not parked for replay; the customer must resend it after connecting. First-time text is parked.
- Money conversion uses `Decimal(str(value))` in every schema property and the order bill; no float `round()` remains in the paise path. The charge percentage is integer math.
- Coupons run on every cart write (text, buttons, plans, picks, reorder, address switch). Only the first two applicable coupons are tried, a coupon that changes items or quantities is refused, and savings show on the receipt and in reorder/switch replies.
- Receipts over the 1024-char button limit are sent whole as a text message, with Pay/Clear in a short follow-up (`send_receipt`). The interactive body limit itself still truncates any other long body; those bodies are short by design.
- The dead go-to add and post-order add buttons were deleted with their dead code in the 2026-10-27 cleanup. `item:change` works. `report_issue` now files a Swiggy report and returns the reference and support email; itemised bills use `get_order_details`.
- Rapid messages: the second waits up to 12 seconds for the first turn, then answers against the fresh cart. A turn still running after that gets an honest resend reply (`concurrency_wait_timeout`).
- Recipes are built in code (2026-10-28) with a stored plan, typed picks, queueing, whole-message evaluation, duplicate grouping and receipt chunking. Batch 3 is code-complete: coupons on every cart path, savings line, 35% charges warning, itemised bill, support report, payment truth, store-open truth and post-order add truth.
- DPDP: the 24h scrub clears history, plan, onboarding state/context, plan-time coordinates, the geocode cache and expired PKCE states; "delete my data" deletes inbound messages and cached geocodes and anonymizes the user row (`deleted-<uuid>`, no name, no Swiggy id) while audit rows keep an anonymous id. App queries run as `grocer_app`, which has DML on the 8 app tables and read-only access to the ledger; the backdated-row scrub is proven on `grocer_test`, while live TTL verification is pending.
- No RLS policies, by design: `anon` and `authenticated` have zero schema usage and zero table grants (checked 2026-10-28). PII is plaintext except Swiggy tokens; disk encryption is Supabase's. The caller-supplied-phone hole was closed in Phase 5 with signed bot links; PKCE state now lives in `grocer.oauth_states`, not process memory.
- The landing page was rebuilt on 2026-11-01 and went live on 2026-11-02: no health badge, no fake uptime, no fallback WhatsApp link, and no phone number on the page. Missing `NEXT_PUBLIC_WHATSAPP_NUMBER` disables the button with a visible note. The OAuth card appears only for a bot link or callback.
- Render free plan sleeps, so pollers stop when idle (`render.yaml:6`).
- Startup waits at most 5 seconds for the database, then serves with `/health` returning 503 and retries migrations with backoff. A dead DB no longer crashes the process.

**Fixed in Phase 1 (2026-10-27):** `verify_db.py` table/column/index check, `verify.ps1` offline default, `/health` 503 mapping, `ruff` dev requirements, real test database, DSN guard, live-test marker, mock-based "live" test rename.

**Fixed in Phase 3 (2026-10-27):** checkout transaction boundary, CAS ownership, UPI args, timeout/5xx reconcile, crash reconcile, cap-raise loop, checkout `response_total_paise`, independent inbound dedupe.

**Fixed in Phase 4 (2026-10-27):** real `track_order` with map fallback, honest `store_info`, tappable choices for one-word requests, split-order milestone latch, wake reconciliation, 401 isolation per row.

**Fixed in Phase 5 (2026-10-27):** default-address grounding, switch-with-rebuild, delete guard on the real path, typed-text address add, signed OAuth links, park/replay wired, production WhatsApp mock branch deleted, scripted tests labeled.

**Observed live 2026-10-27:** calling `update_cart` on a 12-item real cart (₹1751 quote) left all 12 items and quantities intact but Swiggy priced three lines at ₹0 (NOICE peanut butter, Alt Co almond beverage, Amul butter), so its own total became ₹753. Nothing was removed by Grocer. Lock 2 would abort checkout on that drift, which is the intended behavior, but the cause is Swiggy-side and worth watching.

---

## 6. Test Truth (2026-11-03)

**What each kind of test proves.**

| Kind | Where | Proves | Does not prove |
|---|---|---|---|
| Live smoke | `scripts/live_smoke.py` (run by hand with real tokens) | Real Swiggy reads, a real cart add/restore, real Groq routing, the checkout lock stopping before Swiggy | That a live order completes |
| Scripted tests | `tests/test_checkout_locks.py`, `ScriptedClient` | Grocer's own logic on failure paths that cannot be triggered on demand (timeout, 5xx, crash, another user's tap) | Any live Swiggy behavior |
| Fixture tests | `tests/test_staging_fixtures.py` | Response shapes parse correctly | That the live service returns them today |
| DB tests | `-m db` on `grocer_test` | Real SQL, constraints, CAS, pollers against real Postgres | Nothing about Swiggy |
| Turn trace | `backend/observability.py` + one real signed turn | Request id, capability, safety, latency, Swiggy/model counts per turn | Nothing about correctness; it measures, it does not grade |

Scripted tests are not fake product tests. They inject failures the live API will not produce on request. They are never counted as proof of a live capability; every live claim in this file is tied to a dated smoke run.

```
ruff check backend tests
All checks passed!

pytest -q -m "not db and not live"
177 passed, 98 deselected

pytest -q -m "db"
78 passed, 197 deselected

pytest --collect-only -q
275 tests collected

python scripts/eval_router.py --provider groq
Exact capability match: 40/40 (100.0%)
Latency (last call per case): avg 1312ms, p95 1735ms, max 1889ms
Unsafe writes: 0, under-acted: 0, errors: 0
# 2026-11-03 batch 2 (truth, trace, recovery, retries): schema check
# exit 0 (9 tables, grocer_app), ruff clean, 160 offline + 77 DB,
# Next build, verify.ps1 exit 0
# (.scratch/verify_batch2_20261103.log)

# 2026-11-03 batch 3 (honest button taps, one cap helper): schema check
# exit 0 (9 tables, grocer_app), ruff clean, 166 offline + 78 DB,
# Next build, verify.ps1 exit 0
# (.scratch/verify_batch3_20261103.log)

# 2026-11-04 batch 4 (one money parser, one plan decoder, one client builder):
# schema check exit 0 (9 tables, grocer_app), ruff clean, 169 offline + 78 DB,
# Next build, verify.ps1 exit 0
# (.scratch/verify_batch4_20261104.log)

# 2026-11-04 item 5 (exact brand+size skips the evaluator): schema check
# exit 0 (9 tables, grocer_app), ruff clean, 172 offline + 78 DB,
# Next build, verify.ps1 exit 0
# (.scratch/verify_item5_20261104.log)

# 2026-11-04 retest (other brands, ambiguous cases, live tracking turn):
# schema check exit 0 (9 tables, grocer_app), ruff clean, 177 offline + 78 DB,
# Next build, verify.ps1 exit 0
# (.scratch/verify_retest_20261104.log)
# live signed "where is my order?" -> HTTP 200
# REPLY "You have no active order right now." (no invented link)
# (.scratch/live_retest_tracking.log)

# real signed "show my addresses" turn, one payload per event
{"event":"swiggy_call","request_id":"wamid.traceproof.…","tool":"get_cart","latency_ms":1047,"ok":false}
{"event":"model_call","request_id":"wamid.traceproof.…","provider":"groq","latency_ms":968,"ok":true}
{"event":"swiggy_call","request_id":"wamid.traceproof.…","tool":"get_addresses","latency_ms":547,"ok":true}
{"event":"turn","request_id":"wamid.traceproof.…","status":"capability_answered","capability":"list_addresses","safety":"read","latency_ms":2593,"swiggy_calls":2,"model_calls":1,"fallbacks":0}
# (.scratch/trace_turn_20261103.log)

# real signed "what's in my basket" turn under Swiggy's cart lock
{"event":"swiggy_call","request_id":"wamid.cartlock.…","tool":"get_cart","latency_ms":984,"ok":false}
{"event":"model_call","request_id":"wamid.cartlock.…","provider":"groq","latency_ms":1515,"ok":true}
{"event":"swiggy_call","request_id":"wamid.cartlock.…","tool":"get_cart","latency_ms":1000,"ok":false}
{"event":"turn","request_id":"wamid.cartlock.…","status":"capability_answered","capability":"view_basket","safety":"read","latency_ms":3561,"swiggy_calls":2,"model_calls":1,"fallbacks":0}
# REPLY "Swiggy needs you to review the basket first. Open Swiggy → Instamart → Cart, accept the adjusted quantities, then send your request again."
# (.scratch/trace_cart_lock_20261103.log)
```

**New in the Swiggy-error fix (2026-11-03):** `tests/test_swiggy_client_errors.py` proves a structured `success:false` payload raises `SwiggyToolError` and that string and dict error messages are read; `tests/test_whatsapp_webhook.py` proves a Swiggy tool error gets an honest reply and a `swiggy_error` status instead of a 500; `tests/test_basket_actions.py` proves two same-name lines get distinct labels and that a variant query matches the right line. The picker labels are code-proven; the handset tap is not.

**New in the truth/observability batch (2026-11-03):** `tests/test_button_truth.py` proves a pay tap with no database says nothing was charged and an unknown button says it is stale. `tests/test_evaluator_truth.py` proves the model path is marked `llm` and a forced failure is marked `fallback`; the live catalog file now fails if a case skipped the model. The trace is proven by a real signed "show my addresses" turn: `get_cart` failed with Swiggy's cart reason, Groq answered in 968ms, `get_addresses` in 547ms, and the turn closed at 2593ms with 2 Swiggy calls and 1 model call (`.scratch/trace_turn_20261103.log`).

**New in batch 3 (2026-11-03):** `tests/test_button_truth.py` adds one parametrized case per write button (`cart:clear`, `plan:add`, `reorder:last`, `addr:set:a1`, `item:change:spin`, `budget:raise:approval:150000`) that taps with no database and requires a `button_unavailable` status plus "nothing changed"; and one DB test taps as an unknown number and requires `unknown_user` plus "couldn't find your account". `backend/agent/customer_advocate.py` now owns `get_session_budget_cap`, used by the button router, the webhook and the checkout executor; the missing/zero cap still returns ₹1,000. Proof: 7 new tests; `verify.ps1 -Db` exit 0; `.scratch/verify_batch3_20261103.log`.

**New in batch 4 (2026-11-04):** `tests/test_meal_planner.py` proves `decode_pending_plan` accepts fresh JSON strings and dicts, and rejects expired, malformed, non-object and empty rows. `tests/test_swiggy_auth.py` proves `resolve_user_client` builds a client from the stored token and returns `None` when there is no token; `tests/test_checkout_locks.py` proves the shared paise parser rounds ₹1.005 to 101 paise. Proof: 3 new tests; `verify.ps1 -Db` exit 0; `.scratch/verify_batch4_20261104.log`.

**New for item 5 (2026-11-04):** `tests/test_add_matching.py` uses the recorded catalog fixture. "Amul milk 500 ml" resolves to the one exact Amul 500 ml candidate with a sentinel that fails if the evaluator runs; "milk" calls the evaluator exactly once; two same-brand, same-size candidates refuse the skip. Proof: 3 new tests; `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_item5_20261104.log`.

**Cleanup (2026-11-04):** the tracking tests now require Swiggy's real ETA and reject any `swiggy.com/track` link (`tests/test_read_actions.py`, `tests/test_checkout_locks.py`, `tests/test_e2e_staging.py`). No test was deleted or weakened; the read wrapper and one-method class were replaced by the functions they wrapped. The site's 229-test claim is corrected to 255 in source. Proof: `verify.ps1 -Db` exit 0; `.scratch/verify_cleanup_20261104.log`.

**Retest (2026-11-04):** `tests/test_add_matching.py` adds three more exact-skip products (Nandini, Aashirvaad, Maggi), two ambiguous/size-less cases that must call the evaluator, and the confirmed-milestone copy test rejects the default ETA and any link. A real signed "where is my order?" turn on the deployed build returned HTTP 200 with the honest empty reply and no invented URL. Proof: `verify.ps1 -Db` exit 0 (177 offline + 78 DB); `.scratch/verify_retest_20261104.log`; `.scratch/live_retest_tracking.log`.

**New in batch 2 (2026-11-03):** `tests/test_read_actions.py` proves a cart-review error returns the recovery steps; `tests/test_whatsapp_webhook.py` proves the same copy on the webhook path and proves a first-time text row is parked as `awaiting_link`; `tests/test_swiggy_client_errors.py` proves a 429 and a JSON-RPC -32000 retry once with `Retry-After`, and a second 429 becomes an honest busy tool error. The live cart-lock turn returned the exact recovery copy, with both `get_cart` calls failing and the turn closing at 3561ms (`.scratch/trace_cart_lock_20261103.log`).

**New in Block 1 (2026-10-28):** restricted-role test (`current_user = grocer_app`, DDL refused), live/expired PKCE state test, backdated 24-hour scrub test, and a subprocess boot test with an unreachable DB. The router eval rerun scored 40/40 with latency.

**New in Q1/Q2 (2026-10-28):** pack math (`packs_for`: g/kg, ml/l, pieces), stored-plan shape, stored-spin preference, add-all all-or-nothing, partial picks that name the missing rows, numbered-reply parsing, an expired-plan tap that writes nothing, a typed pick that adds only the chosen row, a normal text that is not hijacked, and numbers with an expired plan that route normally. Proof: 12 planner tests, 8 webhook tests, 1 router test.

**New in Batch 2 first slice and reactions (2026-10-28):** 5 meal-planner tests (`test_meal_planner.py`: card contents, Add-all rebuild, missing ingredient blocks the whole write, button-length limit), 1 router test (plan fields and read safety), 2 payload/mapping tests (reaction payload, sparse map), 1 webhook reaction test (exactly one 🏠 for an address question), and 5 webhook tests (multi-item merge, clearer existing-item prompt, recipe card with no write, Add-all tap with Pay, missing ingredient with no write). The unsent savings line, coupon paths, queue/merge and receipt chunking remain unproven by design.

**New in Phase 5:** 12 DB tests in `tests/test_phase5_account.py` (default grounding, switch rebuild, missing-item report, delete guard both ways, typed add with and without PIN, unresolvable text, link-token roundtrip/tamper/expiry, phone-only login rejected, parked replay) and 3 webhook tests in `tests/test_whatsapp_webhook.py` that post the exact Meta JSON for a button tap: duplicate tap, pay tap while locked (spy client never called), and a signed reconnect link. The outbound mock branch was deleted; tests inject a recording client instead.

**New in Phase 4:** 5 read-path tests (track with coords, track without coords, no active order, honest store info, tappable choices) and 3 DB tests (split milestones sent once, wake payment confirmed, 401 keeps the row pending). `npm run build` passes. `verify.ps1 -Db` now exits 0 after migration 004 was applied to the app database on 2026-10-27.

**New in Phase 3:** duplicate tap, two simultaneous taps, another user's button, timeout with a recovered order, clean failure that leaves the receipt payable, unverifiable outcome that blocks retry, crash reconcile with and without an order, cap raise, and UPI QR args. Raw log: `.scratch/verify_phase3.log`.

**Guard proof:** with `TEST_DATABASE_URL` set to the app DSN, pytest exits 1:
```
RuntimeError: Refusing to run tests against database 'postgres'. TEST_DATABASE_URL must point at grocer_test.
```

**Real schema proof:** before and after the DB run, `grocer` held the same counts
(`users=1, sessions=1, approvals=0, checkouts=0, inbound_messages=10, oauth_tokens=1, address_coords=0`).
`grocer_test.users` was 0 after cleanup.

**Not run:** live Swiggy calls, live WhatsApp sends, live Groq eval, and checkout. `test_catalog_search` is marked `live` and excluded by default.

---

## 7. ADR Status

| ADR | Status | Current note |
|---|---|---|
| 0001 | Amended | 25ms ACK and 50ms button path are targets. The webhook is synchronous today. |
| 0002 | Active | Grounding now uses Swiggy's default address. Fingerprint includes payable paise, so any paise change fails. |
| 0003 | Active | Coupon guard works, a coupon that changes cart items is refused, savings are on the receipt, and reorder/switch replies name them. Tracking now calls `track_order` with saved coordinates and falls back to delivery status. |
| 0004 | Amended | The 5-day/no-refresh claim is obsolete. Refresh token exists. Park and replay are wired. Vague staples auto-pick with a working Change/swap; discretionary items show choices. |
| 0005 | Partial | Receipt buttons are Pay, Keep only new (when the basket had items), Change item (vague staples) and Clear. COD is parked; address change happens from the address card. |
| 0006 | Partial | ₹1,000 cap stays. Cap-raise now re-opens the same receipt. The DPDP scrub and delete cascade are built; app queries run as `grocer_app` with no DDL. RLS is skipped because public roles have zero schema access. |
| 0007 | Active | Switch clears and rebuilds the basket at the new store. Delete guard runs on the real delete path. Split orders poll every id. |
| 0008 | Partial | Typed-text address add is built. Reorder is fixture-only and needs a past order. |
| 0009 | Amended | Recipes are in v1 as a plan-confirm-add flow (decided 2026-10-27; built in code 2026-10-28). The exact priced plan is stored in `grocer.sessions.pending_plan` for 30 minutes; the model gives amounts and units and Python computes packs. The fee warning and post-order truth are built. One-time destination is parked. |
| 0010 | Active | Refresh first, park only on refresh failure. Park status matches replay, and the callback replays in the background. |
| 0011 | Superseded | Replaced by ADR 0012. No extra classification call; candidate evaluation is one call per item and is intentional. |
| 0012 | Active, amended 2026-11-04 | Groq is the only LLM; the Gemini adapter and dependency are gone. Item evaluation is one batched call per turn, not one per item. |

---

## 8. Next Action

**Where we are (2026-11-04).** Remote and local `main` are at `c16b924`; Vercel serves the graphics, phone mock, fact strip and cap meter, and Render `/health` returns 200. The live scorecard is done at 25/26 (12/13 and 13/13); the one miss was a case expectation on an empty cart. Last gate: `verify.ps1 -Db` exit 0 on 2026-11-04 — schema, ruff, 182 offline + 81 DB tests, Next 16.4.3 build with 9 routes. Production passes zero overflow, zero console errors and zero hidden reveals at 1440/1024/768/390/360; reduced-motion and no-JS show all content. The connect form ran from the browser through the Next proxy to the local backend and received a real signed code. Handset connect + OAuth passed 2026-11-04 (DB receipts only).

**Remaining live needs:** live OAuth reconnect, address add/delete, the 24h scrub and the demo video. Do not fake any of them.

**Do next, in order:**
1. Add `public/demo.mp4` and verify the player, or leave the black recording stage.
2. Live OAuth reconnect, address add/delete, the 24h scrub.
3. The first real order is Karan's, after handoff. Checkout stays locked.

**Remaining, in order:**

| # | Item | State | Blocker |
|---|---|---|---|
| 1 | 40-case live router eval (`scripts/eval_router.py`) | **DONE 2026-10-29:** 40/40 exact, 0 unsafe writes, 0 under-acted, 0 errors; avg 1535ms, p95 2187ms, max 2719ms. Raw: `.scratch/eval_b1.json`, `.scratch/eval_rest.json`. | — |
| 2 | 26-case live scorecard (`scripts/scorecard_live.py`) | **DONE 2026-11-04, 25/26 (96.2%):** half one 12/13, half two 13/13. The single miss was case 3's empty-cart payment expectation; case 21 proved the UPI list with items. Case 17 was replaced because dragon fruit is now in stock. Raw: `.scratch/scorecard_live_20261104_1_13.json`, `.scratch/scorecard_live_20261104_14_26.json`. | — |
| 3 | Collapse the write path to four verbs | **DONE (code) 2026-10-29:** `set_item` and `remove_item` carry the action; `change_action` and the router patch are gone; a change naming several items is refused. 223 passed twice, ruff clean. Live verb cases 22–31: **10/10**, 0 unsafe. | — |
| 4 | Full 40-case live run **on the branch after the four-verb change** | **DONE 2026-10-31:** 40/40 exact, 0 unsafe, 0 under-acted, 0 errors; avg 1312ms, p95 1735ms, max 1889ms. Raw: `.scratch/eval_after_verbs.json`. Merge gate passed. | — |
| 5 | Skip the second model call when brand and size already match | **DONE (code) 2026-11-04:** a unique exact brand+size match is resolved by Python before the evaluator; vague, ambiguous, missing-size and zero-address turns still call the model. Proof: 3 new tests, sentinel proves no evaluator call for "Amul milk 500 ml"; `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_item5_20261104.log`. Live before/after waits for adds. | Live timing needs the cart to accept adds |
| 6 | Phone taps: Add-all, Change item, typed pick | **PARTIAL 2026-11-04:** `plan:add` and `item:change` reached the bot; the pasta plan filled the basket. A typed plan pick ("1 and 3") is still open. | Needs one plan pick on the handset |
| 7 | Address add/delete, OAuth reconnect, reaction on a real wamid | **PARTIAL 2026-11-04:** an address switch (`addr:set`) reached the bot. Add, delete, live OAuth reconnect and a real reaction remain open. | Needs a throwaway address and one reconnect |
| 8 | Merge `scorecard` into `main` | **DONE 2026-10-31:** fast-forward `db6a297..a8e530c`; PR #3 merged; Render `dep-dbiupgivcj2c73edh5t0` live on `a8e530c`; `/health` 200. | — |
| 9 | Full 26-case scorecard on current code | **DONE 2026-11-04:** 12/13 + 13/13 = 25/26; the one miss was an empty-cart payment expectation, later disproved with items. Raw: `.scratch/scorecard_live_20261104_1_13.json`, `.scratch/scorecard_live_20261104_14_26.json`. | — |
| 10 | Handset taps: Add-all, Change item, typed pick, set/remove picker | **PARTIAL 2026-11-04:** 10 button replies received: clear, keep-only-new, change item, address switch, plan Add all and Pay ×2. Pay stayed locked. Typed pick and same-name picker choice remain open. | Needs one typed pick and one same-name choice |
| 11 | Case 16, "5 kg almonds" | **DONE (honest) 2026-11-02 in `38dc084`:** a multi-pack size ("100 g x 2") now folds its multiplier, and an explicit amount is filled with the fewest exact packs across candidates instead of a pick prompt; when stock cannot reach the amount, the reply adds what exists and names the shortfall. Offline test fails first without the fix; live case 16 re-run passes 1/1 — the store had only 2 × (100 g × 2), so it added 400 g and said "I asked for 5, so I added 2" instead of asking. Full 26-case re-run still pending. | — |
| 12 | Swiggy business errors, duplicate-name picker, Next advisories | **DONE (code) 2026-11-03:** business errors raise `SwiggyToolError` and get an honest 200 reply instead of a 500; set/remove pickers name the pack and quantity and accept a variant match; Next 16.4.3 has 0 production advisories. Proof: 5 new tests, full gate exit 0. `item:change` was received on 2026-11-04; a full set/remove choice is still unlogged. | — |
| 13 | Cart-lock recovery, first-connect replay, 429 retry | **DONE (code) 2026-11-03:** the cart-review error returns exact recovery steps on the read path and the webhook path; a first-time text is parked as `awaiting_link` and replayed after login; a 429 or JSON-RPC -32000 retries once with `Retry-After` capped at 5s, then fails honestly. Proof: 5 new tests; live cart-lock turn returned the copy (`.scratch/trace_cart_lock_20261103.log`); `verify.ps1 -Db` exit 0 (160 offline + 77 DB). | — |
| 14 | Honest write-button taps + one session-cap helper | **DONE (code) 2026-11-03:** cart, plan, reorder, address, item and budget taps say "Nothing changed" when the database or account is missing; unknown buttons say they are stale. The three cap SQL blocks are one `get_session_budget_cap`. Proof: 7 new tests; `verify.ps1 -Db` exit 0 (166 offline + 78 DB); `.scratch/verify_batch3_20261103.log`. | — |
| 15 | Dedupe money, plan decode, token-to-client | **DONE (code) 2026-11-04:** `parse_price_to_paise` delegates to `rupees_to_paise`; `decode_pending_plan` replaces both stored-plan decoders; `resolve_user_client` replaces seven inline token-to-client builders. `send_add_receipt` was already single. Proof: 3 new tests; `verify.ps1 -Db` exit 0 (169 offline + 78 DB); `.scratch/verify_batch4_20261104.log`. | — |
| 16 | Cleanup — fake claims, dead code, over-engineering | **DONE (code) 2026-11-04:** removed invented tracking URLs and the default ETA; deleted dead exceptions, constants, fields, wrapper, one-method class and `command_router.py`; inlined `delete my data`; one max-cap setting; `migrate.py` reuses `verify_db.py`; pack math merged. Proof: `verify.ps1 -Db` exit 0 (172 offline + 78 DB); `.scratch/verify_cleanup_20261104.log`. | — |

**Phase 7 backlog — code-complete; live proofs open.**

| # | Item | State | Proof needed |
|---|---|---|---|
| 1 | LLM queue/backoff for Groq free-tier bursts | **DONE (code) 2026-10-28** | 20-case live run with 0 first-pass outages |
| 1b | Batch item evaluation in one call | **DONE (code) 2026-10-28** | Live multi-item turn shows 2 model calls, not 5 |
| 1c | Stored plan + amount-to-pack math | **DONE (code) 2026-10-28** | Live recipe route; a live Add-all tap that reads the stored plan |
| 2 | List pickers that accept a typed number | **DONE (code) 2026-10-28** | Live reply "1 and 3" against a real plan card |
| 3 | Message merge/queue for rapid second text | **DONE (code) 2026-10-28** | two quick messages both answered, conflicting writes serialized; live double-text unproven |
| 4 | Full message in the model prompt | **DONE (code) 2026-10-28** | batch test proves the whole text reaches the evaluator; live check pending |
| 5 | Grouped search for related items | **DONE (code), narrowed 2026-10-28** | identical queries share one search and one evaluation; cross-item grouping rejected because it mixes candidate pools |
| 6 | Receipt chunking over 1024 chars | **DONE (code) 2026-10-28** | long receipt sent whole as text, Pay/Clear follow in a short message; live long basket pending |
| 7 | Coupons on every cart path; savings line sent | **DONE (code) 2026-10-28** | every cart write optimizes (text, buttons, plan, picks, reorder, address switch); savings show on the receipt and in reorder/switch replies; a coupon that changes items is refused |
| 8 | Fee warning | **DONE (code) 2026-10-28** | charges at 35% or more of item value get one honest warning line on the receipt |
| 9 | Itemized bill (`get_order_details`) | **DONE (code) 2026-10-28** | `order_bill` capability; fixture-proven; live bill waits for a real past order |
| 10 | Support report (`report_error`) | **DONE (code) 2026-10-28** | `report_issue` (account) files with the order id and returns the reference; live filing unproven |
| 11 | Payment-method truth (UPI only) | **DONE (code) 2026-10-28** | answer names UPI as the only supported method and says COD/Swiggy Money cannot be used here |
| 12 | Store-open truth | **DONE (code) 2026-10-28** | cart quote plus the honest open signal: items adding means the store is taking orders; no invented flag |
| 13 | Post-order add truth | **DONE (code) 2026-10-28** | `placed_order_add` says the order is locked and offers a new basket |

**After Phase 7:** Phase 6 is done in code (DPDP scrub/delete, `grocer_app` role, dead columns, durable PKCE state, lazy boot, integer paise). Live 24h TTL proof is pending. Phase 8 is live on Vercel (2026-10-28); only a phone tap on the CTA is unproven. Phase 9 handoff remains. No live order during the build.

**Open proofs:** reactions drawn on a real handset (direct Meta call returns 200; simulated wamids cannot be reacted to); live Groq route for "make pizza for 5" and a live Add-all tap; live Change-item tap; blue ticks/typing with a real wamid; live address add/delete; Gate 2 case 7 (needs a past order) and case 8 (live tap); live 24-hour scrub after real traffic; Groq free-tier daily cap behavior (a 40-case run needs about half the day's 200k tokens). The live multi-item and Hinglish wordings now pass on the 40-case eval. Re-run the full gate at launch.

---

## 9. Rules for Every Future Chat

1. Read `STATUS.md`, `.scratch/HANDOFF.md`, and the latest `JOURNAL.md` entry before planning.
2. Do not edit code without showing the exact plan and getting `proceed`.
3. Do not place an order during the build. Karan places the first real order himself after handoff. `LIVE_CHECKOUT_ENABLED=false` must be enforced in code.
4. Cart changes need approval. Tests never write the real `grocer` schema.
5. Do not fake Swiggy, Groq, WhatsApp, or the database.
6. Do not claim a live result you did not run. Label it "recorded" or "not verified".
7. Do not delete data without listing it first.
8. Do not weaken a test to pass. If the feature is broken, say so.
9. Show `git diff`, test output, and database proof.
10. Update `STATUS.md`, `.scratch/HANDOFF.md`, and `JOURNAL.md` before ending the session.
11. A Swiggy `success:false` answer is an error, not data. Raise `SwiggyToolError` with Swiggy's reason; never parse it as `CartData` or another success model. The customer gets the reason with HTTP 200, never a 500.

---

## 10. Handoff Checklist (Phase 9)

Run in this order. Do not press Pay; checkout stays locked.

1. ~~Commit and push the current tree after Karan approves.~~ DONE 2026-10-28: `main` replaced the old history; live commit `42d5b56`.
2. ~~Render deploy: wait for `/health` 200.~~ DONE 2026-10-28: service branch is `main`; deploy `dep-dbguma942hec739cfba0` for `42d5b56` is `live`; `/health` is 200 with `database: connected`. Still open: a live reaction/blue-tick check on a real wamid (the basket read and addresses passed live on 2026-10-31). No env changes.
3. ~~Vercel: set `NEXT_PUBLIC_WHATSAPP_NUMBER` and deploy.~~ DONE 2026-10-28: production env set, site redeployed; `grocerr.vercel.app` returns 200 with 3 `wa.me` links and no disabled note. Still open: tap the CTA from a phone and confirm it opens the chat.
4. WhatsApp, non-payment:
   - `1 litre milk` → receipt plus one reaction. (Receipt passed live 2026-10-31; reaction unproven.)
   - `what's in my basket` → full basket. (Passed live 2026-10-31.)
   - `make pizza for 5` → plan card; tap Add all; then try a typed pick on a fresh plan.
   - tap `Change item` on a vague staple.
   - send two messages quickly → both answered, no lost write.
   - long basket → whole receipt, Pay/Clear follow-up.
   - `show payment options` → UPI only, no COD claim.
   - `is the store open` → honest cart signal.
   - `show my addresses` → real addresses; add and delete one throwaway address. (List passed live 2026-10-31; add/delete open.)
   - Reconnect Swiggy once from a bot link; confirm the callback returns to WhatsApp.
   - Check blue ticks/typing on a real inbound message.
5. Leave `delete my data` off the main account; it is proven on `grocer_test` and would wipe the only real token.
6. After 24 hours of real traffic, verify the scrub with a read-only query.
7. Record each result in `STATUS.md`; any failure stays open.

Not included: checkout, reorder, live bill, Gate 2 case 7. They need a real past order, and no order will be placed.
