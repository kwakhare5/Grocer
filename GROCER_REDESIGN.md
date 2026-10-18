GROCER FINAL DESIGN DOCUMENT
Updated Saturday 17 October 2026 after the 11:44 PM decisions.
From the walkthrough with Karan (subsystems S1 to S12, questions Q1 to Q22).
Baseline: the earlier review read commit 9d06dc3. This revision updates the agreed design, not the live code. No new code or Swiggy tests were run to make this document.
Status: the eight follow-up items are resolved. Remaining experiments are evidence still to gather, not decisions to ask again. Slice 0 and Slice 1 prompts have been sent; completion is not verified here.
Historical test counts and model limits below are the figures recorded during the October 17 review, not a fresh check of the repo or account.


1. GOAL AND SCOPE

Objective
A person chats on WhatsApp in normal language (English, Hinglish) and gets Swiggy Instamart groceries ordered safely.

Rules everything is built on
- The AI model understands language. Code only guards money, cart, checkout, login and safety.
- No hardcoded word lists or regex to guess what a person means.
- Permanent root-cause fixes, not patches.

Who it is for right now (Q18)
- Swiggy reviewers and interviewers only. A demo.
- Friends and family testers come later, only after tests are green, and we tell them first that Google's free tier may use chats.
- Public customers are out of scope (needs a paid API, privacy policy, support).

What it will not do
- No order cancel (Swiggy has no cancel tool for Instamart). The bot gives the customer care number 080-67466729.
- No restock reminder in this version (moved to version 2).
- No submission to Swiggy until you say so.
- No live checkout until the money tests are green. Review mode stays on.

Weak points of this scope
- A demo proves you can build, not that people use it.
- The redesign is big. On Oct 10 you said "submit, don't rebuild again". Small commits with tests after each keep it from dragging. The stop line is: build order in section 9, then freeze.


2. THE FLOW OF ONE MESSAGE

1. Customer sends a WhatsApp message. Meta calls our webhook (straight to the Render backend, no Vercel proxy).
2. Code checks the signature. Unsigned or forged gets 401.
3. The message is turned into one simple record and saved to the Postgres inbox first. The phone number becomes an internal id.
4. A worker picks it up. One turn per customer at a time (short claim in the database that expires after 90 seconds, plus a 60 second cap per turn).
5. We send the WhatsApp "typing" signal right away so the customer sees the bot working.
6. The brain (Gemini Flash-Lite) hears every message. No word-list doorman before it. It gets: the last 10 user turns word for word, plus the live cart and address every turn.
7. The brain can use a small set of tools: search, get cart, addresses, set budget, ONE basket-change tool, checkout, track order. Up to 8 steps per message.
8. For each product the model picks from the 5 to 8 real candidates and names the product id. Code checks that the id is real.
9. For remove or change, the model reads the cart first and names the cart line id. Code checks the id is in the live cart.
10. Code checks every cart write: real total with all fees against the cap, read-back of the cart, rollback if over.
11. The reply goes into the outbox and is sent to WhatsApp. If the model fails, the customer still gets an answer, never silence.
12. Checkout only happens after explicit confirmation tied to the exact cart shown: a Confirm tap, or typed yes that passes the small yes/no check and all code gates. Code writes the order message from the real result.

Weak point
- Steps 6 to 9 rely on Flash-Lite judgment. Not yet proven on tricky Hinglish or full-cart multi-step turns. The experiments in section 8 test this.


3. SUBSYSTEM DECISIONS (S1 to S12)

S1 WhatsApp channel: KEEP, plus two changes
- Keep whatsapp.py, whatsapp_crypto.py, whatsapp_parser.py, whatsapp_formatter.py, models.py, identity.py. Each does one job.
- Delete the Vercel proxy route (app/api/whatsapp/webhook/route.ts). Point Meta straight at Render URL + /api/whatsapp/webhook. You change the URL once in the Meta app.
- Keep Vercel for the landing page and the Swiggy OAuth redirect (grocerr.vercel.app is Swiggy's approved redirect, do not touch it).
- Add a free UptimeRobot ping every 5 minutes on /api/health to keep Render awake.
- Delete the "same message hash" dedupe in channels/whatsapp.py (about 6 lines). It can silently skip a real repeat reply. The outbox already handles real duplicates.
- Later: monitoring for inbound stopped, replies failing, stuck checkouts.
- Weak point: nothing alerts if Meta stops sending while the backend is up. Fine at zero users.

S2 Queue and workers: KEEP, fix one bug, add monitoring
- Keep the Postgres inbox/outbox queue.
- Fix payment reconciliation: after the deadline, mark the attempt UNKNOWN and send one message "I couldn't verify your payment, please check the order in Swiggy". Today it checks forever and the customer is never told.
- Same file: only an order matching THIS attempt may block it, not any old delivered order.
- Free monitoring: UptimeRobot keyword check on /api/ready, Sentry free plan (about 10 lines in main.py).
- Do not put queue length in the health check (Render would restart in a loop).
- Render database port is 5432 (direct). The short claim lock in S3 works normally.

S3 Engine, state and locks: SIMPLIFY (A and B final, C confirmed after S4)
- A: replace the long database lock with an in-process lock plus a short database claim that expires after 90 seconds, and a 60 second cap per turn.
- B: one typed CustomerState saved and loaded whole. Delete the dict wrapper, the two leftover dicts, the copy-back, the dump and restore functions.
  Keep: history, address, pending approval, cart fingerprint, budget, payment choice, pending_request_text (the "try again" memory), unresolved_items (blocks checkout when Swiggy changed or dropped items), budget_blocked_items (the "Keep These Items" step).
  Cut: pending_variant_selection, ingredient budget, ingredient extras, _pending_checkout and pending_clarification. The last 10 turns hold the open question. Before removing pending_clarification, inspect its dependencies and the existing answer-plus-original-request path. Report any behaviour that would be lost before deleting it; do not guess that history already replaces every use.
  Keep the 30 minute reset that drops a pending approval (move it into the new state, do not delete it).
- C: a small separate agent/loop.py owns the Gemini client, prompt and loop. Engine just calls it. Money gates stay in code inside the tools. No framework like LangGraph. Step cap 8.
- History: last 10 user turns word for word (a judgment, not a sourced number), live cart and address re-added every turn, no summary calls, old tool results shortened to one line.
- The aim is less duplicate state and a clear loop boundary, not a line-count target.

S4 Preflight and guards (the "doorman"): DELETE most, keep the money doors
- Delete all fast paths and word lists (reset, show cart, cancel, retry, hesitation, address-change word check, variant check). The brain hears every message.
- Wipe cart gets a "Clear cart?" button. Only the tap clears. This ends "don't clear my cart" emptying the real cart.
- Confirmation: button is the main gate. The button carries a token tied to the exact cart. Old tokens are rejected.
- Typed "yes" also works (your call): one small Flash-Lite yes/no check ("did they confirm THIS exact cart: yes, no, unclear"). Unclear counts as no. Code still checks cart, address, budget, expiry. Weak point: here the model's judgment helps decide on money. drift_guard.py has its own typed-yes word list; it goes into this same replacement.
- Checks on what the brain says: keep only checks with no words (item count 1 to 45, quantity 1 to 99, item exists in cart). Delete the 7 "claimed success" word patterns.
- After checkout, code writes the order message from the real result (Q1).
- Stays as locked code: checkout refuses without confirmation, re-reads cart, checks address, total, budget; cart fingerprint and approval expiry; budget limits.
- Keep only necessary safety checks in preflight. Line counts are not the target.
- Answers recorded: Q1 to Q6 in section 4 and section 6.

S5 Finding the right product: model picks from candidates, code validates
- Search returns the top 5 to 8 real products (name, pack, price, id). The model replies with the id. Code checks the id is in the list. The cart read-back still runs.
- catalog_ranker.py (146 lines) and its word rules go, but ONLY after the ranker experiment passes (Q15). Until then the ranker stays.
- Weak point: Flash-Lite picks may be worse than a bigger model. The experiment measures it. 30 searches is a small sample.

S6 Tools: one basket-write tool
- One tool for basket changes (manage_basket: add, remove, set quantity). Everything else read only: get cart, search, addresses, track order, plus checkout.
- Remove quick_add_items, update_cart, check_replenishment.
- Remove and change use the cart line id (Q16). The brain must read the cart first. Wrong id is rejected. Two identical lines: the brain asks which one (needs a test).
- Weak point: the one write tool becomes the most important, so it gets the most tests.

S7 Budget code: clean budget.py
- budget.py holds read_budget_cap (live, used by _read_budget_cap and preflight). Dead regex parsers (extract_total_budget, extract_ingredient_budget, is_explicit_extra) were deleted. Keep set_budget as the only way in and keep the code checks (exact decimal compare against the real total, rollback if over).
- The budget cap code checks remain active.

S8 Gemini connection and history: delete the salvage retry, fix the history
- Delete the 400 "strip all tool parts and retry" hack in gemini.py. On a 400, stop the turn and use the existing "I saved your request, try again" path. Log the full error body.
- One fallback model constant (config.py and engine.py disagree today).
- Root-cause history fix (from code reading, not a live repro):
  1. Never rewrite the model's own parts (react_coordinator.py throws away the thoughtSignature when rebuilding parallel calls).
  2. Save call and result together, only after tools finish. Every call always gets a result, even on errors.
  3. Trim history only at the start of a whole turn, never mid pair (session_manager.py cuts entries one by one).
  4. One check before saving: pairs complete, stamps present. A bad turn is refused at save.
  5. Separate data fix: reset the history of customers already poisoned.
- Weak point: which cause fired for you is not proven. The new error log will show it.

S9 Restock reminder: remove (5 steps, table dropped later). See section 6.

S10 Landing page honesty: fix all false claims
- Demo chat: relabel "Verified" as "Example WhatsApp conversation". Remove invented speeds (180ms, 1250ms, "<200ms", "Sub-Second").
- Payment step: "Review mode: no real order, no money moves".
- Remove the landing-page test count. Show the live CI badge instead. It reports the current CI result, not proof that every behaviour is safe. Weak point: it will show red while CI is red, and its meaning depends on honest test coverage.
- Delete "guarantees 100% accurate pricing and stock", Blinkit and Zepto claim, dietary exclusions claim (only in the prompt, not enforced).
- Fix wrong tool details in the demo (a budget field search does not have, wrong parameter names).
- Footer: "Built for the Swiggy Builders Club" (not a badge that looks like Swiggy endorses it).
- Restock wording goes with S9.

S11 Tests: fix the net first. See section 7.

S12 Repo cleanup: words after code
- Delete "Grocer Audit.md" from the repo root (git history keeps it).
- After the code work, rewrite README and ARCHITECTURE from the final code, short and true, real test numbers only. Remove false "94 passing", "114 100% green", "32/32 green".
- Mark old spec files (MASTER_SPEC, AGENTS, GLOSSARY, old ARCHITECTURE parts) as "old design" or delete them. List links from your application doc first so none break.
- JOURNAL: one honest entry of what changed and why.
- Last step, not first.


4. MONEY SAFETY RULES

- Spending cap (Q10, Q11, Q19): the cap means the final amount the customer pays, including delivery, handling and every other fee. The model reads the cap from the message (Flash-Lite, a small call), code stores and enforces it. No regex. The check uses the real total from the Swiggy cart bill after each add, and again at checkout. If the bill is incomplete, it is not treated as under the cap.
- Over the cap: build the closest basket, show the real total with every fee line, say how far over, and let the customer choose (keep it, drop an item, raise the cap). "OK keep it" sets the new limit. Nothing goes to confirm until they answer. Never silently round up.
- The "add Rs X more to remove the delivery fee" idea: only with real numbers from the Swiggy cart. The model never invents a threshold. Whether the cart shows one is unverified.
- Both caps stay (Q7): whole basket cap and recipe cap. The recipe cap counts only recipe items. Both numbers come from what the customer types, nothing is fixed.
- Never hardcode Rs 99 or a free-delivery limit. Use Swiggy's real cart bill and refusal message. Show a fee-saving tip only when Swiggy supplies the needed numbers. Include a tiny cart in the live test. Weak point: the customer may learn the minimum only when Swiggy refuses.
- Confirmation (S4): a button tied to the exact cart, or typed yes through the cart-specific yes/no check and all code gates.
- The pass mark is "no order without explicit confirmation", meaning a valid button tap or checked typed yes. The later phrase "no order without a tap" was loose wording, not a change to S4. The 50-message script never confirms or orders.
- Approval valid 15 minutes (Q12). Any change or late tap gets "that basket has changed or timed out" and a fresh summary with a new button. The 15 is my judgment, one setting.
- Stale button (Q5): "that basket has changed", then the live cart summary with a new button. If the cart is empty: "your basket is empty now", no button.
- Checkout is not idempotent (Q3): Swiggy has no duplicate protection. On an error or lost reply: wait 2 to 5 seconds, check recent orders. Compare order time and total with the cart we sent. Found: tell the customer it went through. Not found: tell the customer and offer a "Try again" button, with text "if you see the order in your Swiggy app, don't tap again". No auto retry. Never use confirmDuplicate to retry. A normal "failed" answer from Swiggy (out of stock, slot gone) is final.
- Order messages (Q1): code writes the facts (id, total, status, pay link). The model adds a line ONLY when the order failed or waits for payment, never on success.
- No cancel tool (Q4): the model replies with the care number as a fact in its instructions. No tool is called. This case is tested.
- Address change with items in the cart (Q2): ask first with a button, then clear, switch, re-search each item by name and quantity (not Swiggy ids), re-add, and show found, missing and new total. Changed items are marked. Swiggy requires clearing before an address change.
- Address asked (Q9): not at "Hi". Asked before the first item search. Shown again at checkout.
- Unclear item (Q8): model auto picks when one product clearly fits, asks one plain question only when choices really differ. The basket summary always shows what was picked.
- Never silently lose an item (Q20): code compares the model's own list with the cart result and names anything missing. The summary shows the full cart. A forgotten item that the model never listed relies on the customer reading the summary.
- Checkout needs a confirmation that code verifies. This gate is our own safety choice, not a Swiggy rule.
- Rate limit (Q17 and 17b): see section 5. Never silence.


5. MODEL PLAN

Brain and yes/no check (Q17)
- gemini-3.5-flash-lite, low thinking. One config constant.
- Why: your live test showed about 1.85 seconds per message, 0 errors, 8 of 8 turns finished. Free limit on your key: 500 per day, 15 per minute.

Helper
- gemini-3.6-flash ("3.5 Flash" and "3.6 Flash" share one pool of 20 per day, 5 per minute on your key).
- Used rarely. Code, not the model, decides. A turn is retried once on the helper only if Flash-Lite visibly fails: names a cart line that does not exist, bad tool arguments, or a loop.
- Daily counter, capped at about 15 helper calls. It stops using the helper for the rest of the day at that cap. No change to this share is approved merely because a test scores poorly; inspect the results and propose a prompt fix or revised share.
- If the helper says "too many requests", return a safe answer through the available path. Do not claim an invalid Flash-Lite action succeeded. If neither model can answer, say to try again. Never silent.

Rate limits (Q17b)
- On a 429: one short message "One moment, I'm a bit busy", then one retry after the wait Google gives (or on the cheaper model), then "Please try again in a minute". Never silent, never the same message twice. Cart and money rules do not change.

Fallback
- gemini-flash-lite-latest on a rate limit. Weak point: it may share the same daily pool as 3.5 Flash-Lite. Unknown, so the fallback may give no extra room.

Other settings
- Do not send temperature, top_p or top_k (Google is removing them). Do not end a request with a prefilled model turn.
- Free tier: the earlier review recorded that Google may use chats to improve its products. Tell friends and family before testing, and check the current terms before expanding access.

Facts from your tests
- The recorded 3.7 and 3.8 runs took 70 to 165 seconds per message and looped on get_cart. Rate-limit waiting may explain this. Intrinsic slowness of either model is unproven; do not turn this run into a general speed claim.
- 3.1 Flash-Lite had one 45 second spike. gemini-3-flash-preview: 5 per minute.

Weak points
- Wrong answers that still pass the checks will not escalate. Only visible failures do.
- Two models means two behaviours to test.
- The test was single messages with an empty cart.
- Hinglish quality has no published score for any model. Only your tests.
- Loops: the step cap of 8 must end in a reply, never spin.


6. DELETE LIST, IN SAFE ORDER

Rule: risky deletions wait for their safety tests and replacement paths. Clearly dead code may go first only after its uses are checked. Each deletion is a small reviewed change with the relevant tests. The cleanup method in section 9 does not override these prerequisites. The whole-repo delete list was read at 9d06dc3 by reading code. "Dead" calls outside backend/agent were checked by grep. Re-grep before each delete.

A. Restock reminder (S9), 5 steps, small commits
1. Cut the doors: main.py startup check, engine.py, preflight_handler.py, tool_executor.py, schemas.py (the tool the model can call), whatsapp.py. If the tool stays in schemas.py the model can still call it.
2. Delete backend/agent/replenishment.py (the whole file).
3. Tests in the same change: delete the 6 replenishment tests. Keep the 4 webhook tests in the same file (signatures, replays) and move them. Without this CI breaks.
4. Database: add a new migration (numbered 009, not 010) that drops the replenishment table. Run it later, only after the new code is live and stable. The table holds customer data and cannot be undone. Until then the orphan table is harmless.
5. Signboards: landing page cards, FAQ, hero text, page title, the "replenishment assistant" line in prompts.py, README and docs.
Keep the "usual items" feature. It is a different thing.

B. Fast paths and word lists (S4), after the confirm button and clear-cart button exist
- fast_paths.py (whole file), address-change word check, address word check, variant check in preflight, reset and hesitation word checks.
- The 3 dead functions in guards.py (pizza and pasta lists). Only tests touch 2 of them, those tests go too.
- The 7 "claimed success" word patterns, after the code-written order message exists.
- The typed-yes word check (is_explicit_confirmation) and the drift_guard word list, ONLY after the button plus yes/no check exist. Today it is the only path that turns "yes" into an order.
- The planning mode (decides if the brain sees the cart): replace by "the brain sees the cart" (Q21), then delete.
- Do not add a temporary negation patch for "don't clear my cart". Fast-path deletion plus the Clear-cart button is the agreed root-cause fix. Until that slice is verified, do not claim the bug is already fixed.

C. Salvage path (S8)
- The 400 strip-and-retry in gemini.py, after the "save call and result together" history fix is in.

D. State wrapper (S3), one careful commit
- The fake dict wrapper, the two leftover dicts, copy-back, dump and restore, pass-through methods. Every place must read the session directly first. About 25 call sites.
- _pending_checkout, pending_variant_selection, ingredient_extras_text, pending_clarification. Check pending_clarification dependencies and preserve necessary clarification behaviour before removal.
- The "last spoke" time: move it into the new state, do not delete (powers the 30 minute approval reset).

E. Dead budget regex in budget.py (S7): deleted regex parsers; kept read_budget_cap (live).

F. Tools (S6): quick_add_items, update_cart, check_replenishment, once manage_basket handles cart line ids.

G. Product ranker (S5): catalog_ranker.py and the word rules in tools.py. ONLY after the ranker experiment passes (section 8). Do not delete before.

H. Search pacing (Q22): fixed 2.8 second sleep in batch_search_products (backend/agent/tools.py) deleted. Searches kept in groups of 3. Rely on Swiggy's 429 handling (the code already waits Retry-After and stops the remaining groups). The sleep was written to pass a test, not from a Swiggy limit. Swiggy publishes no numbers: https://mcp.swiggy.com/builders/docs/operate/rate-limits.md. The "70 per minute" figure in your application doc is not in any current official page, treat as unverified.

I. Repo files: "Grocer Audit.md" now. README and spec rewrites last (S12).

Do NOT delete (I was wrong earlier): pending_request_text, unresolved_items, budget_blocked_items.

No temporary patch: the existing fast-path deletion plan addresses "don't clear my cart". This decision is closed.


7. TEST PLAN

Real current state (commit 9d06dc3)
- CI went red at 9d06dc3: 48 failed, 66 passed (reproduced on a real database). 08edb59 was green.
- 9d06dc3 did not break 48 things. It broke 2 and unmuted the 81 end-to-end tests that CI was skipping. Green before meant only "33 of 114 tests ran".
- The 33 unit and money invariant tests all pass. Most green tests are real (they send signed WhatsApp-style messages into the app, real Postgres, fake only Gemini and Swiggy).
- Real numbers: 66 pass, 48 fail. README and JOURNAL claims ("94 passing", "114 100% green", "32/32 green") are false.

The 48 red tests
- 32 are stale: they expect the old "reply 1A 2A" questionnaire. Rewrite around Q8 ("clear match is added directly", "unclear match gets one question").
- 7 guard "never silently drop a customer's item". The code behind them was deleted. Rebuild with Q20, keep the tests.
- 2 are stale scripts hiding safety checks (no retry after an unsure write, fresh review after a price change). Re-script them.
- 2 are the isolation tests (model blind to the cart). Rewrite to check no accidental address switch and no cart wipe while adding items (Q21).
- 3 others: greeting, medicine (guard still works), one old variant test.
- The 2 real new bugs: (1) 9d06dc3 deleted the code that read "at most Rs 100" from the message, so the cap is saved only if the model calls set_budget (fix is Q19); (2) "Hi" gets "Which address should I use?" (fix is Q9).
- Also seen: "Add milk and bread under 80" gave a Rs 237 basket with a confirm button, and "pizza ingredients under Rs 1000" gave Rs 1,288. The cause was not found. It is found by the tests we write first.

Order
1. CI was already unmuted in 9d06dc3. Unmute local pytest.ini too, then record which tests fail and why. Do not claim this is another CI fix. Slice 1 explicitly does not run tests; test execution is a later, separate check.
2. Write the money tests first (before any deletion):
   - checkout without confirmation refused
   - wrong or changed cart refused (fingerprint at checkout time, no test today)
   - approval expiry at 15 minutes (zero tests today)
   - old button refused, stale button gives fresh summary
   - price change mid review forces a fresh review (fails today)
   - budget cap holds with fees (fails today)
   - no auto retry after a checkout error, check orders first
   - cart line id must exist in the live cart, two identical lines ask which
3. Rewrite stale tests and delete tests of removed features in the SAME commit as each removal.
4. Fix the 3 fake or weak tests: burst message concatenation (tests a copy of text), quick add in tool list (only checks a name), recipe planning (never checks the basket changed).
5. Rewrite the paced search test (test_long_list_checks_every_item_in_paced_batches in backend/tests/suites/recipe_and_budgets.py, around line 139 and assert at line 181) to check groups of 3 and that a 429 stops the rest. Not the 5.5 second number.
6. README and JOURNAL: put real numbers only.

Limits
- Tests against a pretend Swiggy can pass while the real one behaves differently. That is why the real-Swiggy experiment (search only) and the later 50-message test (never placing an order) stay.
- Pass marks are agreed, not open:
  Ranker: valid candidate ids in 30 of 30 searches, with no more than 3 of 30 picks judged worse than the ranker. Otherwise the ranker stays.
  Real 50-message test: zero money-rule breaks and at least 45 of 50 right-basket outcomes. For non-shopping messages, judge whether the correct unchanged basket is preserved. One money break means stop and fix, regardless of the basket score. Explicit confirmation means a valid button tap or a checked typed yes, bound to the exact cart and passing all code gates.
- These are small-sample judgement thresholds, not a standard or a guarantee. A poor basket score means inspect failures and fix the prompt or propose a different helper share, not lower the money bar.


8. OPEN FACTS AND EXPERIMENTS

Decisions closed after the first version
- No temporary patch for "don't clear my cart".
- Cut pending_clarification after checking dependencies in its slice.
- Ranker and 50-message pass marks are set in section 7.
- The 50-message run is scripted as described below.
- No hardcoded minimum order or free-delivery numbers.
- Landing page uses a live CI badge, not a test count.
- Keep the original relative order of build work items 5 to 8.
- S5 to S8 were explicitly reconfirmed: candidates with id validation, one basket tool with live cart line ids, remove dead budget.py but keep set_budget and gates, fix history at its source and delete the salvage retry.

1. Ranker experiment (Q15)
- scripts/ranker_experiment.py runs 30 real Swiggy searches. Search only, never add to cart or order.
- Compare the current ranker's pick with Flash-Lite's pick from the same candidates, by id only. Save candidate lists and both picks. Print VALID or INVALID and SAME or DIFFERENT.
- Review every pick by hand, including whether the candidate really fits the request. Pass only with 30 of 30 valid picks and at most 3 of 30 worse than the ranker. Otherwise the ranker stays.
- The experiment prompt was sent earlier. No pass is claimed in this document.
- Weak point: 30 searches is small and product names, packs and prices do not tell the whole story.

2. Scripted real 50-message test
- Antigravity runs the same 50-message script through the local simulator against the real Swiggy connection. Use only the test address.
- Never place an order and never tap Confirm. Keep order execution disabled so a typed reply cannot accidentally order either.
- Include English, Hinglish, recipes, budgets, "same as last time", unclear items, cart edits, address change, "cancel my order", random chat and a tiny cart.
- Save every reply and the cart after each message. Clear the cart between scenarios. Keep expected outcomes so reruns can be compared.
- Karan sends the saved output for review against section 7. Zero money breaks, at least 45 of 50 right-basket outcomes.
- Run at most once a day. The earlier estimate was about 150 model calls, but actual calls depend on tools, retries and helpers. Do not treat the estimate as measured usage.
- Weak points: this changes the real cart before clearing it; use a test address and no personal shopping cart. Scripted messages are neater than real customers. A no-order run does not prove successful live checkout; mocked money tests must cover that gate separately.

3. Model facts still to verify
- Rerun 3.7/3.8 timing only after checking current quota, with spaced requests so quota waits do not pollute the result. Slowness is unproven.
- Whether gemini-flash-lite-latest shares the 500/day pool with 3.5 Flash-Lite is unknown.
- Raw "same as last time" and "yes" replies from the all-models test were not inspected in the earlier review, only the summary. The all-models run was partly unfinished then.
- The recorded 20/day pool is shared by 3.5 Flash and 3.6 Flash. Do not count them as separate helper allowances. These are account observations from October 17, not permanent product limits.

4. Integration facts still to verify
- Whether search needs an address, what minimum-order message and delivery threshold the live cart supplies, cart lifetime, and order visibility delay.
- Real WhatsApp old-button behaviour and button limits before implementing the relevant UI.
- Whether anyone used the oauth phone path. Undo is agreed regardless; inspect dependencies rather than assume none exist.
- The support number recorded earlier in this document must be checked before shipping it to customers.

5. Confirmation wording corrected
- "No order without a tap" in the follow-up pass marks meant no order without explicit confirmation. S4 still allows the Confirm button or checked typed yes tied to the exact cart. The small yes/no check must return yes, and code must still validate the cart, address, budget and expiry. No new decision is needed.


9. BUILD ORDER (small commits)

Execution method
- Work on redesign, not main. Backup tag: backup-9d06dc3 at commit 9d06dc3.
- Each slice has a small checklist, named files, expected changes and a way to check them. Use a fresh Antigravity chat per prompt.
- Antigravity does not commit or push. It reports old and new lines, dependencies and anything unfinished. It must not claim completion from its own summary alone.
- Karan reads the report, then says "save" and "push" to redesign. The pushed commit is read against every checklist item: done, half done or missing.
- A slice passes only after that check. If it misses something, send a short repair prompt before the next slice.
- Run relevant tests and the frontend build at the slice's stated check stage. Do not override a prompt that says not to run them. Slice 1 is explicitly a no-test edit slice, not a claim that the suite is green.
- No submission until Karan says. No real checkout while money safety is unverified.

Issued slice sequence and status
0. Backup. Prompt sent at 11:42 PM. Check the working tree first; stop if it is dirty. Create the backup tag and redesign branch from 9d06dc3, then report the current commit and branch. No file edits or push. Completion not verified here.
1. Local test honesty plus oauth undo. Prompt sent at 11:42 PM. Edit only pytest.ini, backend/api/oauth.py and components/landing/ConnectInstamartModal.tsx. Remove only the local e2e deselection. Do not change conftest.py. Compare the two oauth files in 0fda2b8 and 9d06dc3, remove only the restored phone_number path and keep the ticket-only flow. Report dependent files instead of editing them. No tests, commit or push inside the prompt. CI itself was already unmuted at 9d06dc3. Completion not verified here.
2. Budget cap fix. Write the failing money checks and verify the real total including fees before claiming the fix works.
3. History root-cause fix. Preserve model parts, save calls and results together, trim whole turns. Delete the salvage retry only after the replacement is protected.
4. Restock removal, split into the five steps in section 6. Keep webhook safety tests; defer the destructive table migration until the replacement code is stable.
5. Remaining subsystems in small slices, followed by test rewrites, landing copy, tidy-only work and final docs. The exact prompts are issued after review of the preceding slice, not guessed in advance.

Original work checklist, retained for coverage
These are work-item numbers from the first document, NOT competing slice numbers. Some are now grouped into the issued slices above. The accepted relative order of work items 5 to 8 stays as listed, subject to safety dependencies. Do not redo completed work just because it appears here.
0. Backup at 9d06dc3.
1. Ticket-only oauth undo.
2. Delete Grocer Audit.md after checking links.
3. Honest test baseline. CI is already unmuted; local pytest needs the Slice 1 edit. Record red tests and causes.
4. Write money tests from section 7 before risky deletions.
5. Run the search-only ranker experiment and quota-clean model timing rerun. Keep the ranker if it fails the agreed marks.
6. Fix budget cap and the premature address question on "Hi".
7. S2: payment reconciliation timeout, only matching orders block; monitoring.
8. S1: direct Render webhook, remove proxy route and message-hash dedupe. Keep the approved OAuth redirect.
9. Model config, helper counter, rate limits, typing signal, one fallback constant and supported request settings.
10. History fix, then salvage deletion.
11. Cart-specific confirmation through button or checked typed yes, Clear-cart button, stale-button handling. Only then delete replaced word lists and fast paths.
12. Code-written order facts and safe checkout-error reconciliation. No automatic order retry.
13. One basket tool using fresh cart line ids. Remove superseded tools after it works.
14. CustomerState, short claim, separate agent loop, step cap 8. Remove wrappers only after callers are converted. Check pending_clarification dependencies.
15. Restock removal with webhook tests preserved. Table drop later.
16. Dead budget.py removal after money tests. Remove fixed search sleep and rewrite the pacing test around groups of 3 and 429 handling.
17. Ranker removal only after the experiment passes.
18. Rewrite stale tests and delete removed-feature tests in the corresponding behaviour commits, not as a later excuse to leave CI broken.
19. Landing honesty, no static test count, live CI badge.
20. Scripted real 50-message test, no confirms or orders, once a day, scored against the agreed marks.
21. Tidy-only review, then README, ARCHITECTURE, JOURNAL and old specs.
22. Freeze. Submission only when Karan says.

Cleanliness method
- Agreed direction: delete dead code, make tests honest, fix behaviour in slices, tidy structure, then docs.
- "Delete first" is not permission to rip out live safety paths before replacement tests, buttons or history fixes. Check uses first and follow section 6's prerequisites.
- Karan's goal is clean, maintainable and organised code. "Split by job" was not his standing rule; it is a proposed way to reach that goal, not a requirement to make more files.
- Prefer folders with clear areas, such as webhook and queue, agent loop, tools, Swiggy connection, state and safety checks. Keep code together when splitting would only add indirection.
- Files should have a clear purpose and plain names. No arbitrary line cap, giant catch-all files or tiny pass-through files just to look modular.
- Use the same name for the same thing. Remove duplicate paths after proving which one is live. Keep settings and model names in one place, secrets out of code, comments for reasons rather than obvious steps.
- Do not mix behaviour changes with structural cleanup. Use separate move-only commits for moves; any logic change gets its own reviewed change.
- For a move-only commit, compare tests before and after. The results must match, and the actual commit must show only moves and necessary import/path updates. Matching results alone do not prove unchanged behaviour.
- Once tests are green, inspect the whole folder tree and give each area a keep, move or delete decision. Rewrite docs from the final code, not the old plan.
- Stop when the agreed behaviour works, tests are honest and green, folders have clear purposes and docs match. Do not start an endless clean-everything pass.

Weak points
- A dependency scan can miss dynamic uses. Tests and commit review reduce that risk; git restores source code, not deleted customer data.
- Existing red tests limit confidence in tidy-only checks. Prefer postponing structural moves until the relevant tests are green.
- Slice review can only verify what is pushed and observable. A report alone is not completion evidence.
- The original work checklist and issued slice numbers serve different purposes. Use the latest reviewed prompt for execution, and the checklist for coverage.

END
