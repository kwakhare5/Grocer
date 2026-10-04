# GROCER recovery plan — 2026-10-04

This is the current plan for the product goal in `GROCER_V2_MASTER_SPEC.md`: an English-first WhatsApp Instamart assistant that preserves a customer's intended basket, constraints, and consented replenishment habits. The spec is a goal, not proof that its proposed architecture or historic test claims are correct. This plan supersedes conflicting older plans and trackers. No paid order is authorized by this plan.

## Evidence and limits

- Render is live at `2eb23aa` in review checkout mode. After the database cutover on 2026-10-04, `/api/ready` returned HTTP 200 with no missing dependencies. This proves service readiness and a database ping, not shopping accuracy.
- The old Singapore Supabase project was deleted by the customer before its data could be migrated. Supabase says deleted projects and their backups cannot be recovered. The new Mumbai project `rxaqlqvhdoiduadikjeb` was empty; all ten existing schema scripts applied, producing nine `grocer_internal` tables. Render's `DATABASE_URL` now points to its Mumbai session pooler. No independent backup was found in the workspace; customer chat state, OAuth tokens, and replenishment history require a separate dump to restore.
- The current branch's signed-webhook → PostgreSQL → agent → outbox → recorded-Meta report has 37 passed, 0 failed, 0 skipped, exit 0. The model, commerce, and Meta boundaries are simulated. A separate six-case real-model probe uses synthetic commerce and exposed two failed shopping flows plus an unverified budget claim. These are workflow and diagnostic proof, not an overall AI accuracy, load, delivery, or full real-provider result.
- Six paced, read-only real MCP calls at Charholi succeeded before the database cutover: addresses, empty cart, and four searches. After the customer reconnected, GROCER made three more real read-only calls: `get_cart` returned an empty basket, `get_addresses` returned three addresses, and an agent-level “show my basket” turn returned the correct empty-basket state. No real cart write, complete real-model shopping journey, payment, or order was verified.
- Production still silently picks a first variant and can pass Swiggy-originated cart/address/tool data to external model providers. The branch now asks for exact SKU choices, makes one whole-cart write, and verifies read-back; its real Swiggy milk search returned six choices. Render's service API reports Singapore, which requires the DPA and transfer safeguards described in Swiggy's data rules before MCP responses are processed there. Replenishment is not proactively delivered. Meta HTTP acceptance is labeled sent without delivery-status reconciliation.

## Choices recorded 2026-10-04

- Swiggy access: the customer supplied an email saying the **Instamart Intelligence integration is live**, its redirect URI is whitelisted, and authenticated calls may begin. Treat that email as evidence of access; the pasted text does not establish a signed DPA, staging history, or permission to retain purchase-derived habit data. Do not reapply for access merely because the earlier audit lacked this email.
- Hosting: Keep the existing Vercel frontend, Render backend, and Supabase Free database. The customer chose Mumbai for the new database, supplied its credentials, and deleted the old project. Do not introduce another host. Record Render's processing region as an unresolved production data-handling check; a Mumbai database alone does not change where the backend runs.
- OAuth redirect: retain only the existing allowlisted `https://grocerr.vercel.app/`. The site can forward the callback to a new internal backend, but its function region and data route must be verified; do not request or assume a new Swiggy redirect.
- Product choice: one grouped exact-variant selection message for ambiguous basket items.
- Replenishment: start from consented confirmed GROCER orders; add Swiggy history only after its data-use gate is resolved.
- Payment: consider one low-cost real order at the final gate, with separate approval then; no present order authorization.
- Reminders: prepare a Meta template for approval; no proactive send until approved.
- AI evaluation: use both anonymized human messages supplied by the customer and independent blind cases.

## Current infrastructure boundary

The current stack is Vercel, Render Singapore, and Supabase Mumbai. Keep the Swiggy allowlisted redirect at `https://grocerr.vercel.app/`. The deleted Supabase project cannot serve as a rollback target. Take an independent database dump after new customer state is created. Free hosting does not guarantee continuous availability. Render currently offers no India region, so the existing backend cannot satisfy Swiggy's outside-India processing rule without the specified agreement and safeguards. The new shopping path stays off main/Render until resolved.

Sources: [Supabase project deletion](https://supabase.com/docs/guides/platform/delete-project), [Supabase regions](https://supabase.com/docs/guides/platform/regions), [Render regions](https://render.com/docs/regions), [Swiggy data and compliance](https://mcp.swiggy.com/builders/docs/operate/data-and-compliance/).

## Success definition

“100% error-proof” and a literal 10/10 cannot be proven by finite tests. We will call a category release-ready only when its contract, adversarial E2E, real-provider canary, monitoring, and recovery gates pass. Publish measured denominators and failures, not a single fabricated accuracy percentage.

Hard invariants, required to pass **every** release test: zero cross-customer data/action, zero unapproved orders, zero silent substitutions or omitted requested items, zero false cart/payment/order success claims, zero unreviewed budget/fee violation, and zero Swiggy payload in an unapproved external model request. A failed or ambiguous provider write must stop and reconcile before another write.

Human-quality measures: first-turn intent accuracy, complete-task success, wrong-item rate, clarification count, recovery success, p50/p95 response time, MCP calls per task, queue age, and unconfirmed outbound count. Set product thresholds after a blinded baseline and report confidence/coverage. Passing scripted cases alone is never a 10/10 AI score.

## Stage 0 — freeze facts and protect live customers

1. Record exact deployed revisions, schema versions, configuration regions, and enabled features without copying secrets into artifacts. Keep checkout review-only and do not expand live traffic.
2. Map every Swiggy-originated field through database, logs, model requests, and WhatsApp replies. Capture external model requests in a local E2E to prove forbidden fields are absent.
3. Inventory credentials previously shared in chat and plan controlled rotation. The database encryption key requires versioned re-encryption with a rollback path; do not simply replace it and orphan ciphertext.
4. Reconcile stale claims in `task.md`, `.agents/AGENTS.md`, master spec, and release documents to actual test/deployment evidence.

**Exit:** one accurate evidence ledger; no false “verified” statements; privacy and operational decisions below resolved before live model/MCP shopping tests.

## Stage 1 — lawful, minimal AI boundary

1. Confirm Swiggy production access and whether a signed DPA/cross-border arrangement exists. Its current rules require a signed DPA and transfer safeguards if GROCER processes MCP responses outside India. Allowlisted OAuth redirect alone is insufficient production approval.
2. Preferred design without that arrangement: process and store Swiggy tokens/responses in an India-hosted backend/database; pass the model only the customer's own message plus static task vocabulary. Keep addresses, product data, carts, order history, and tool responses out of Groq/OpenRouter/Gemini. Do not use a logging/analytics path that re-exports them.
3. Replace model-controlled commerce calls with a validated **intent proposal**: requested products or recipe, quantities, hard/soft constraints, scoped budgets, edits, and references. Existing task state remains the one durable owner. Application code resolves the proposal against live Swiggy data and asks when grounding is ambiguous.
4. Preserve recipe reasoning from the customer's words, but never allow model output to authorize checkout, invent a price, select a provider SKU silently, or assert a provider outcome. Remove raw tool-result history and duplicate post-hoc text guards only after equivalent E2E behavior passes.
5. For replenishment, retain consented derived purchase signals only under a verified lawful basis. Swiggy `get_orders` exposes recent history (15 days); it is not a long-term history service.

**Exit:** E2E capture proves the external model sees no Swiggy-originated fields; two-customer isolation and deletion pass; region/contract evidence is recorded. No indirect retry of the previously rejected real-model data export.

## Stage 2 — one truthful shopping path

1. On each relevant turn, read the current provider cart before planning a mutation. Resolve a real selected address for searches; an address-free `get_cart` must remain possible. Ask for address when shopping stock depends on it.
2. Keep a durable requested-item ledger: exact match, awaiting variant, unavailable, reduced, proposed substitute, budget-blocked, explicitly removed. The customer's latest explicit instruction wins. Do not silently treat a similar brand as the requested one.
3. Search using actual names, brands, pack sizes, stock, max quantity, and similar-product flags. Preserve the available variants. Present a **grouped, concise choice** for ambiguous items; Swiggy's current search reference requires the customer to choose the specific variant before adding. Do not repeat the entire address/variant question on retry.
4. Build a proposal before writing: quantities, exact provider IDs, item prices, selected address, and budget scope. For “pizza ingredients under ₹1,000 plus bread/Bournvita/tissues/pencil,” cap ingredients only and show extras separately. Preserve user-listed priority; show excluded items and ask what to change.
5. Refresh cart, stock, and prices at write time. `update_cart` replaces the entire cart, so merge the reviewed proposal with existing provider items and issue one bounded whole-cart update. Read back the cart and payable total. Treat dropped/reduced items, fee drift, external edits, timeout, and rollback uncertainty as explicit review states, never success.
6. Save the proposal and its stable choice IDs across model outage, auth expiry, 429, restart, and “try again.” Validate model quantities/types before any tool work; report errors in plain language with the cart's verified state.
7. For symptom-framed requests, suggest customer-selectable groceries only. Do not diagnose, recommend medicines, or add anything before the customer chooses.

**Exit:** no first-result auto-pick; no per-item budget write loop; all requested items accounted for; each cart claim matches provider read-back; bounded call count and stop-on-429 behavior pass.

## Stage 3 — payment, delivery, and replenishment

1. Show only payment methods returned for the live cart. Use UPI app or QR only when offered; never ask for the customer's UPI ID. Bind confirmation to exact customer, address, cart fingerprint, provider payable total, payment choice, task version, and expiry. Review mode makes zero checkout calls.
2. For a later authorized live release, persist the attempt before checkout; after an ambiguous outcome, check provider orders/payment status before any retry. Distinguish order created, payment pending, paid, failed, partial/multi-store, and fulfilled. Never declare an order placed from model text.
3. Replenishment: explicit opt-in; learn from confirmed GROCER orders and eligible consented Swiggy history; require enough observations for a useful estimate; support stock corrections, pause, frequency, quiet time, and deletion. Queue a suggestion, never an automatic order. Send proactively only with an approved Meta template.
4. Process Meta delivery-status callbacks so API acceptance is not confused with customer delivery. Reconcile unknown and partial multi-part sends. Alert on old inbox/outbox work and unknown outcomes; make health monitoring fail when the service is unhealthy.

**Exit:** payment/replenishment/transport states survive restart and report provider or Meta truth. A chargeable canary requires separate explicit authorization.

## Stage 4 — rigorous E2E and bounded real verification

1. Before each code slice, write failure modes and a red signed-webhook → isolated PostgreSQL → real agent/state → outbox → recorded-Meta E2E. Mock only true external boundaries and clocks. No unit tests as release proof. Keep JUnit/report and exit code.
2. Build a blinded, human-style transcript bank, not prompt examples copied from implementation. Cover easy/medium/hard: typos, Hinglish/English phrasing, ambiguous packs, long recipes, scoped budgets, edits mid-task, interruptions, symptom-framed grocery suggestions, old button clicks, external cart changes, out-of-stock, substitutions, no address, two customers, auth expiry, 429, 5xx, timeout, duplicate webhook, restart, and delivery failure. Include explicit expected item ledger and customer reply for each case.
3. Run concurrency, burst, restart, and long-conversation tests against isolated PostgreSQL with deterministic external faults. Report latency, retries, calls, error rate, and exact assertions. Use production Supabase only for controlled read-only verification or approved migrations, never for fault injection.
4. After Stage 1 is satisfied, run a small paced real-model + real-MCP acceptance set through GROCER at Charholi. Count and cap calls, stop on 429/auth/unknown write, and never place an order. After the customer chooses an exact live variant, verify one reversible add → get-cart → clear → get-cart cycle. Compare each provider observation with the requested-item ledger.
5. Verify the exact deployed revision through the real WhatsApp number with a short no-charge journey, including corrections and recovery. The local simulator remains a full-path test surface; it cannot replace this final transport check.

**Exit:** all safety invariants pass in the full-path suite, human-quality metrics are published with sample sizes, the bounded real canary matches provider state, and the deployment has no unresolved critical defect.

## Stage 5 — simplify and release

1. Inventory old agent branches, duplicated guards, stale mock/simulator routes, obsolete unit files, dependencies, and documents. Mark each as active, migration/rollback, test-only, or provably unused. Migrate material old assertions into E2E before deletion; remove one tested slice at a time. Keep security and recovery code even when it adds lines.
2. Run lint, build, Python compile, and the full E2E command with exit code 0. Review actual diff and deployment configuration. Apply migrations with backup/rollback and verify production schema. Rotate credentials through controlled deployment.
3. Complete Swiggy's go-live checklist: confirmed production access, at least 48 hours green staging, OAuth redirects, rate-limit budget, session observability, support/runbook, data handling, and staged rollout. Launch at low traffic, measure failures, and stop/reroll when gates fail.
4. Keep paid checkout and proactive reminders gated until their separate real-world approval/template and final canaries pass.

**Exit:** deployed SHA, evidence report, current documentation, operational alerts, and rollback procedure all agree. No “100%/10 out of 10” claim is made without stating the measured scope.

## Decisions needed before dependent work

1. From the supplied Swiggy live-access email, ask only unresolved account-specific questions through an authorized sender: whether the existing integration has a signed DPA, whether consented purchase-derived habit retention is permitted, and whether any staging/go-live evidence remains required. The exact redirect URI stays unchanged.
2. The customer confirmed there is no independent dump of the deleted Supabase database, so prior GROCER state cannot be restored. The customer reconnected Swiggy through the existing WhatsApp OAuth link; the token is active in Mumbai and the two read-only MCP checks passed.
3. Retain the existing Vercel, Render, and Mumbai Supabase setup. Do not seek a new host or redirect URI without a concrete need and the customer's instruction.
4. For the reversible real-cart canary, show current Charholi variants and obtain the customer's exact selection immediately before the test.
5. At the final payment gate, obtain a fresh, separate authorization for a specific low-cost real order.
6. Obtain Meta template approval before sending proactive reminders.

Official sources: [Swiggy search_products](https://mcp.swiggy.com/builders/docs/reference/instamart/search_products.md), [update_cart](https://mcp.swiggy.com/builders/docs/reference/instamart/update_cart.md), [get_payment_options](https://mcp.swiggy.com/builders/docs/reference/instamart/get_payment_options.md), [get_orders](https://mcp.swiggy.com/builders/docs/reference/instamart/get_orders.md), [data and compliance](https://mcp.swiggy.com/builders/docs/operate/data-and-compliance.md), [ship to production](https://mcp.swiggy.com/builders/docs/build/ship-to-production.md), [rate limits](https://mcp.swiggy.com/builders/docs/operate/rate-limits.md). The current aggregate source is [Swiggy Builders Club full documentation](https://mcp.swiggy.com/builders/llms-full.txt).
