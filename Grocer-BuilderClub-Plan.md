# Grocer x Swiggy Builder Club - The Plan

For Karan Wakhare, fourth-year student. Updated 2 October 2026.

You direct Antigravity/Codex; you do not need to write every line yourself. Ask it for small changes, before/after tests, and plain explanations. Keep the current project, not a full rewrite.

Builder Club requirements and current repo verdicts below use the verified 2 October audit of commit `556b4e91eeca478069a83372676f86be9eda1dcc`. Additional quality repair checks are separated from independently verified findings. This plan does not claim orders or applications were submitted.

## Part 1: What Swiggy Builder Club Is and Wants

### The program and submission expectations

It is a production-access program, not a competition. No submission deadline, scoring rubric, minimum test count, fixed video length, or completion certificate was found. Featuring, hiring, and production approval are not guaranteed. Students and solo developers can apply. Grocery restocking is explicitly welcomed; Instamart alone is a valid server choice.

Source: https://mcp.swiggy.com/builders/ and https://mcp.swiggy.com/builders/developers/ .

The official statements recorded in the audit are:

- "We welcome individual developers, indie hackers, and tinkerers."
- "Anything that makes commerce better for users."
- "smart grocery restock bots"
- "A concrete use case with real end users (not a sandbox demo)."
- "Alignment with Swiggy's consumer experience - agents that respect the user, confirm orders, and don't surprise them."
- "Technical readiness - you can complete OAuth, handle 401/429, retry safely."
- "Responsible traffic patterns - you estimate your QPS and agree to honour rate limits."
- "Security baseline - HTTPS redirect URIs, no PII storage beyond what you need."
- "Show us the full loop: a real use case, the agent workflow, and a working demo (video, deployed app, or GitHub repo with clear setup instructions)."
- "strong engineering thinking, product sense, and creativity"
- "Send demos, video walkthroughs, or GitHub repos to builders@swiggy.in."

Show the user, the complete shopping workflow, and what is actually tested. Mock commerce must be called mock commerce. A model test is not proof of a real Swiggy order.

### Application requirements and how to apply

Use the individual developer/team form: https://forms.gle/4vkeKyqm15Qb6fnJA .

The audited first section asks for every field below. These labels follow the audit inventory, not necessarily verbatim labels:

| Field | What to prepare | Required in inspected section? |
| --- | --- | --- |
| Recorded account Email | Check the signed-in Google account | Yes |
| Full Name | Karan Wakhare | Yes |
| Email | Your monitored contact email | Yes |
| Applicant type | Actual individual developer option | Yes |
| Team/Project Name | Grocer | Yes |
| GitHub/Portfolio URL | https://github.com/kwakhare5/Grocer | Yes |
| LinkedIn | Your actual profile URL | Yes |
| Project explanation | User problem, workflow, evidence, limits | Yes |
| MCP servers | Instamart only | Yes |
| Architecture | See Part 5 | Yes |
| Production Redirect URI(s) | Exact deployed callbacks; no localhost | Yes |
| Working Demo Video Link | Playable without an access request | Yes |
| Terms acknowledgement | Read and personally accept terms shown | Yes |
| Integration type | Actual WhatsApp assistant integration | No star seen |
| Expected request volume | Honest calls/day estimate | No star seen |

The form has a Next button. The audit did not fill it or inspect later pages. This is the complete verified first-section inventory, not proof no later fields exist. Check later pages before submitting.

The access page also asks for the following, even where not separate first-section fields:

- "Who you are - company details or individual developer profile"
- "What you're building - a brief description of your use case"
- "How it works - integration architecture overview"
- "Redirect URI(s) for authentication flows"
- "Static IP ranges or gateway IP(s)"
- "Security contact for your team"
- "Data handling and privacy declaration"
- "Environment and infrastructure setup details"
- "Acknowledgement of Swiggy MCP terms"
- "Security audit summary (Optional)"
- "SOC2 / ISO certification (if available)(Optional)"
- "Expected traffic and scaling plan (Optional)"
- "Primary technical contact - email that reaches an engineer."

The security audit, SOC2/ISO certificate, and traffic/scaling plan are optional on the access page. No certificate is required for a solo builder. Traffic estimates are still needed for onboarding/go-live. Do not invent IPs, approvals, or qualifications. Name yourself and a monitored email as the actual contact.

The site says: "Send demos, video walkthroughs, or GitHub repos to builders@swiggy.in." Email is a demo/review route, not production approval. This form has a required video field, so include the link there. Draft and review any email before sending it.

Sources: https://mcp.swiggy.com/builders/access/ , https://mcp.swiggy.com/builders/docs/operate/access.md , https://mcp.swiggy.com/builders/developers/ .

### Every allowed, restricted, and prohibited behavior

Source: https://mcp.swiggy.com/builders/access/ . Quotes below are recorded by the audit.

#### Allowed and encouraged

- "Building apps, agents, or tools that make ordering, discovery, or dining better for users"
- "AI-powered assistants and copilots that use MCP to automate commerce workflows"
- "Creative side projects, hackathon builds, and experimental prototypes"
- "Integrations that follow Swiggy's security and branding guidelines"
- "Sharing demos and walkthroughs with us"
- "Commercial partnerships where both sides win"

#### Not allowed

- "Reselling or sharing your MCP access with unapproved third parties"
- "Building aggregation layers that hide Swiggy's brand or confuse users"
- "Misrepresenting prices, availability, or delivery times"
- "Scraping or extracting data beyond what the APIs provide"
- "Using the APIs for competitive intelligence or benchmarking"
- "Bypassing rate limits, logging, or any platform safeguards"

#### Prohibited conduct: zero tolerance

- "Manipulating order flows, incentives, or ranking systems"
- "Dark patterns, deceptive UX, or misattributing where data comes from"
- "Generating fake traffic or abusing rate limits"
- "Harvesting data beyond your agreed scope"
- "Reverse engineering MCP internals"
- "Circumventing whitelisting or access controls"
- "Violating user privacy or security regulations"

#### Continuing rules

- **Stay in Scope:** "Use the APIs for what they're built for. Want to expand into new capabilities? Let's talk."
- **Respect the Brand:** "Follow Swiggy's attribution guidelines. Users should know when they're interacting with Swiggy services."
- "Transaction data from MCP stays governed by Swiggy's platform terms. Handle it responsibly."
- "We monitor API usage for quality and safety."


Partnership is optional. Stay within your approved scope, identify Swiggy as the source, and do not pass mock prices, stock, or delivery claims off as live. Local correctness testing is different from prohibited competitive-intelligence benchmarking.

### Data, compliance, and traffic requirements

Sources: https://mcp.swiggy.com/builders/docs/operate/data-and-compliance.md and https://mcp.swiggy.com/builders/docs/operate/rate-limits.md .

- "Do not persist user PII longer than needed ... current session"
- "Do not use Swiggy-originated data for analytics, advertising, or model training without explicit user consent and a DPA."
- "Log only what you need for debugging ... not full request/response bodies in plaintext."
- "Honour deletion requests"
- "Hash user identifiers at rest"
- If processing MCP responses outside India: "signed Data Processing Agreement ... before production", "SCCs or equivalent", "Minimize fields crossing the border"
- "Don't poll track_* faster than 10s"
- Active quotas: "70 requests / minute", write tools "30 requests / minute", burst "2× steady-state"
- "stop retrying immediately, apply backoff" on rate limit
- "One session per user, not one per request"
- "Initialize domains sequentially, not in parallel"
- "Stop all connection attempts immediately on receiving a block or rejection"
- "Notify us 7 days ahead of any major traffic event"

Quoted ellipses above are fragments preserved by the audit, not invented complete quotations. PII means personal information; DPA means data-processing agreement; SCCs are contractual cross-border protections.

Use 70 total calls/minute and 30 writes/minute as ceilings, not targets. Do not design around the 2x burst allowance. Count searches, tracking, and concurrent users. Confirm your allocated limit scope with Swiggy; until then use conservative shared limits. Payment-status code calling track_order is still tracking: at least 10 seconds between calls.

Honor Retry-After when supplied, stop on blocks, and bound safe-read retries. Never blindly repeat an uncertain checkout: check whether the order already exists first.

Declare what you store, why, where it goes, who can see it, when it is deleted, and how users request deletion. Include tokens, chats, addresses, receipts, and data sent to Google. Hashing customer IDs does not anonymize all this data. The audit identifies Render's region as Singapore; Google's processing region and required agreements are unverified. Do not claim India-only processing.

Google's free tier says content is used to improve its products. Test with synthetic data until real customer/Swiggy processing, consent, and agreements are resolved. Source: https://ai.google.dev/gemini-api/docs/pricing .

### Production checklist

These are go-live gates, not a reason to pretend the prototype already meets them. Source: https://mcp.swiggy.com/builders/docs/build/ship-to-production.md .

1. "staging has been green for ≥ 48 hours and production access has been confirmed by builders@swiggy.in"
2. "every URL your OAuth flow might redirect to is allowlisted (exact-match)"
3. "v1 scopes ... are requested uniformly"
4. "auth failures (401 / JSON-RPC -32001) and upstream timeouts each have an explicit branch"
5. "retry logic per this page is in place"
6. "order-placement paths do check-then-retry, not blind retry"
7. "no order is placed without user-visible confirmation of items + total"
8. "you've benchmarked your expected QPS and confirmed you're under the ceiling"
9. "session id logged on every call; metrics exported"
10. "alerting set up on the _meta.swiggy.deprecation field"
11. "Swiggy has an email + Slack channel to reach your on-call for S0/S1"
12. "data retention, deletion, and consent flows align"
13. "if you have a voice surface, your prompts are shaped"
14. "internal runbook for 'what do we do when Swiggy returns X'"
15. "traffic ramps 1% → 10% → 50% → 100% over at least 24 hours"

The audit preserves the scope requirement only as a quoted fragment, without the three exact scope names. Ask Swiggy to confirm them; Grocer defaults to mcp:tools. It also notes a 30-second retry time budget. That is not permission for blind order retries. QPS means calls per second; a runbook is a failure-handling guide; S0/S1 are serious incident levels. Voice conditions apply only if you actually ship voice. Keep current claims text-only.

### Documented contradictions: follow the stricter/specific rule

- Rate guide says limits are enforced now; production checklist says not enforced in v1.0. Follow the active dedicated guide: 70 total/30 write calls per minute and tracking at least 10 seconds apart.
- Developer FAQ says production APIs/no sandbox; onboarding describes staging and 48 hours green. Do not assume safe sandbox orders. Enforce charge-blocked review mode and ask Swiggy what staging means for your access. Still meet the 48-hour gate before a production claim.
- Traffic/scaling is optional on the access page, but onboarding/go-live needs volume/QPS. Prepare realistic orders/day, calls/day, peak rate, and measurements anyway.
- Homepage says review typically takes a couple of weeks; enterprise guidance says 4+ weeks. Neither is a guaranteed solo-builder deadline.

Sources: the access, developer, rate-limit, and production pages linked above, plus https://mcp.swiggy.com/builders/ .

### Short word guide

MCP is the connection Grocer uses to call Swiggy's tools. OAuth is the customer login/permission flow. A token is a private credential, not something to show in a demo. A redirect URI is the exact return URL after login. HTTP 401 means access needs reconnecting; 429 means too many calls. A mock is fake test data, not a real order. RAM is temporary memory; Postgres is persistent database storage.

## Part 2: Where Grocer Stands Today

### The good, with limits

Real architecture separates conversation engine, model provider, commerce adapter, and WhatsApp channel. The audit independently ran `pytest backend/tests`: **51 passed** in 1.72 seconds. Frontend/backend health returned HTTP 200; backend reported `commerce_adapter=swiggy_mcp`, `database=not_checked`. This proves a reachable Swiggy-configured backend, not a completed customer order or working database.

Login/reconnect handling, receipts, and human controls show useful work. The use case fits directly. But the audit run used replayed model responses and mock commerce. The saved live-Gemini test also uses mock commerce. No real orders, customer authentication, or form submission were verified.

Repo: https://github.com/kwakhare5/Grocer .

### Per-requirement verdicts, condensed

Fulfilled means supported at the audit's stated level. Partial means incomplete or unsafe. Missing means not found in the inspected material. Unverified means the audit could not establish it, not that it never happened. For prohibitions, fulfilled means no prohibited behavior found in inspected code, not proof about all external conduct.

#### Program/demo

| Requirement | Verdict |
| --- | --- |
| "We welcome individual developers, indie hackers, and tinkerers." | FULFILLED |
| "Anything that makes commerce better for users." | FULFILLED |
| "smart grocery restock bots" | FULFILLED |
| "A concrete use case with real end users (not a sandbox demo)." | PARTIAL |
| "Alignment with Swiggy's consumer experience - agents that respect the user, confirm orders, and don't surprise them." | PARTIAL |
| "Technical readiness - you can complete OAuth, handle 401/429, retry safely." | PARTIAL |
| "Responsible traffic patterns - you estimate your QPS and agree to honour rate limits." | PARTIAL |
| "Security baseline - HTTPS redirect URIs, no PII storage beyond what you need." | PARTIAL |
| "Show us the full loop: a real use case, the agent workflow, and a working demo (video, deployed app, or GitHub repo with clear setup instructions)." | PARTIAL |
| "strong engineering thinking, product sense, and creativity" | PARTIAL |
| "Send demos, video walkthroughs, or GitHub repos to builders@swiggy.in." | UNVERIFIED |

#### Application

| Requirement | Verdict |
| --- | --- |
| "Who you are - company details or individual developer profile" | PARTIAL |
| "What you're building - a brief description of your use case" | FULFILLED |
| "How it works - integration architecture overview" | FULFILLED |
| "Redirect URI(s) for authentication flows" | PARTIAL |
| "Static IP ranges or gateway IP(s)" | MISSING |
| "Security contact for your team" | MISSING |
| "Data handling and privacy declaration" | MISSING |
| "Environment and infrastructure setup details" | FULFILLED |
| "Acknowledgement of Swiggy MCP terms" | UNVERIFIED |
| "Security audit summary (Optional)" | MISSING |
| "SOC2 / ISO certification (if available)(Optional)" | MISSING |
| "Expected traffic and scaling plan (Optional)" | MISSING |
| Form: "GitHub or Portfolio URL" and "LinkedIn" | PARTIAL |
| Form: "Working Demo Video Link" | UNVERIFIED |
| "Please ensure the link is viewable without requesting access." | UNVERIFIED |
| "Servers you'll call" | FULFILLED |
| "Primary technical contact - email that reaches an engineer." | MISSING |

#### Production

| Requirement | Verdict |
| --- | --- |
| "staging has been green for ≥ 48 hours and production access has been confirmed by builders@swiggy.in" | UNVERIFIED |
| "every URL your OAuth flow might redirect to is allowlisted (exact-match)" | UNVERIFIED |
| "v1 scopes ... are requested uniformly" | PARTIAL |
| "auth failures (401 / JSON-RPC -32001) and upstream timeouts each have an explicit branch" | FULFILLED |
| "retry logic per this page is in place" | PARTIAL |
| "order-placement paths do check-then-retry, not blind retry" | PARTIAL |
| "no order is placed without user-visible confirmation of items + total" | PARTIAL |
| "you've benchmarked your expected QPS and confirmed you're under the ceiling" | MISSING |
| "session id logged on every call; metrics exported" | MISSING |
| "alerting set up on the _meta.swiggy.deprecation field" | MISSING |
| "Swiggy has an email + Slack channel to reach your on-call for S0/S1" | UNVERIFIED |
| "data retention, deletion, and consent flows align" | PARTIAL |
| "if you have a voice surface, your prompts are shaped" | FULFILLED for declared text-only scope |
| "internal runbook for 'what do we do when Swiggy returns X'" | PARTIAL |
| "traffic ramps 1% → 10% → 50% → 100% over at least 24 hours" | MISSING |

#### Ground rules

| Requirement | Verdict |
| --- | --- |
| "Building apps, agents, or tools that make ordering, discovery, or dining better for users" | FULFILLED |
| "AI-powered assistants and copilots that use MCP to automate commerce workflows" | FULFILLED |
| "Creative side projects, hackathon builds, and experimental prototypes" | FULFILLED |
| "Integrations that follow Swiggy's security and branding guidelines" | PARTIAL |
| "Sharing demos and walkthroughs with us" | UNVERIFIED |
| "Commercial partnerships where both sides win" | UNVERIFIED |
| "Reselling or sharing your MCP access with unapproved third parties" | PARTIAL |
| "Building aggregation layers that hide Swiggy's brand or confuse users" | FULFILLED |
| "Misrepresenting prices, availability, or delivery times" | PARTIAL |
| "Scraping or extracting data beyond what the APIs provide" | FULFILLED |
| "Using the APIs for competitive intelligence or benchmarking" | FULFILLED |
| "Bypassing rate limits, logging, or any platform safeguards" | PARTIAL |
| "Manipulating order flows, incentives, or ranking systems" | FULFILLED |
| "Dark patterns, deceptive UX, or misattributing where data comes from" | PARTIAL |
| "Generating fake traffic or abusing rate limits" | PARTIAL |
| "Harvesting data beyond your agreed scope" | UNVERIFIED |
| "Reverse engineering MCP internals" | FULFILLED |
| "Circumventing whitelisting or access controls" | UNVERIFIED |
| "Violating user privacy or security regulations" | PARTIAL |
| "Stay in Scope" | PARTIAL |
| "Respect the Brand" | FULFILLED at attribution level |
| "Transaction data from MCP stays governed by Swiggy's platform terms. Handle it responsibly." | PARTIAL |
| "We monitor API usage for quality and safety." | UNVERIFIED |

#### Data/traffic

| Requirement | Verdict |
| --- | --- |
| "Do not persist user PII longer than needed ... current session" | PARTIAL |
| "Do not use Swiggy-originated data for analytics, advertising, or model training without explicit user consent and a DPA." | UNVERIFIED |
| "Log only what you need for debugging ... not full request/response bodies in plaintext." | PARTIAL |
| "Honour deletion requests" | PARTIAL |
| "Hash user identifiers at rest" | FULFILLED for primary customer mapping |
| If processing MCP responses outside India: "signed Data Processing Agreement ... before production", "SCCs or equivalent", "Minimize fields crossing the border" | UNVERIFIED |
| "Don't poll track_* faster than 10s" | MISSING |
| Active quotas: "70 requests / minute", write tools "30 requests / minute", burst "2× steady-state" | UNVERIFIED |
| "stop retrying immediately, apply backoff" on rate limit | MISSING |
| "One session per user, not one per request" | PARTIAL |
| "Initialize domains sequentially, not in parallel" | FULFILLED for single-server scope |
| "Stop all connection attempts immediately on receiving a block or rejection" | UNVERIFIED |
| "Notify us 7 days ahead of any major traffic event" | UNVERIFIED |

## Part 3: The Gaps, Ranked

### Security and submission safety first

1. **Plaintext tokens and customer-token reuse.** Even the supposedly encrypted save path writes plaintext tokens to disk. Customer lookup can reuse the configured owner's token. Fix before other users try Grocer.
2. **Budget only in the prompt.** Code does not enforce the cap against the full payable total. An AI instruction is not a spending limit.
3. **Review mode does not stop charges.** `CHECKOUT_MODE=review` exists but checkout does not consume it. Do not rely on the setting for demo safety.
4. **Five-second tracking violates the ten-second rule.** Change actual Swiggy calls, including payment tracking, not just comments.
5. **Test-count honesty.** The verified current README already says 51, not 273. Keep the actual count and remove any old 273 claim elsewhere. Fix setup too: `requirements.txt` is at repo root, not `backend/requirements.txt`.
6. **Broken video path.** The audited https://grocerr.vercel.app/demo.mp4 returned 404. Upload the new video to a playable link with no access request.

### Agent quality

These are additional repair checks. Ask the coding tool to reproduce each active-code issue before changing it. The audit independently supports unsafe confirmation and replay/mock-test limits, but does not independently prove every quality issue below.

7. **Amnesia on model errors.** The fallback chain wipes history, losing requests and earlier choices.
8. **Only four user turns in RAM.** Shopping needs more continuity; free-tier restarts wipe it. Persist around 20 turns and explicit task state, with expiry/deletion.
9. **Only six products visible.** Missing category, quantity limits, similar items, and paging make choices incomplete.
10. **Conflicting prompt pile.** Hardcoded lists do not give a repeatable shopping procedure, self-check, or budget method.
11. **Confirmation bug.** Plain "yes" is not accepted on the problematic server path, while "don't confirm" can match consent. The audit verifies the broad confirm regex and lack of one-use basket-bound approval.
12. **Silent exit after eight steps.** Limits are useful, but unfinished work needs an explanation and next step.
13. **Errors hide the failed item.** Generic failures make the agent guess what to retry.
14. **Receipts cut at 1,024 characters.** Interactive-message limits can hide what the user is approving.
15. **Speed without a quality bar.** A fast wrong basket is worse than a slower correct one.
16. **Scripted tests do not measure judgment.** Keep useful code tests, but add live-model evaluations of new requests, constraints, substitutions, and corrections.

Other production gaps remain: privacy/processing agreements, safe address changes, persistent duplicate protection, rate handling, metrics, deprecation alerts, contacts, and rollout evidence. A-H is the first repair pass, not the whole production checklist.

## Part 4: The Fix Plan

### Order and stop rules

A is the cheapest quality improvement. B-D fix major causes of poor choices. E-G are safety requirements, not optional polish. H checks whether the agent improved.

Work in a charge-disabled environment with synthetic data. **If real users are active, stop chargeable/customer testing and do E, F, and G immediately, then resume A-H.** Do not postpone known token/checkout defects because A is easy.

For each letter, ask for changed files, a failing-before/passing-after test, and a plain explanation. Old tests still passing is not enough.

### A. Use the stronger Flash model

**Change:** Set `GEMINI_MODEL=gemini-3.8-flash` with the same Google API key/provider. Remove Lite fallback models. Pin one model per conversation. If unavailable, preserve the session and ask the user to retry, rather than switch mid-task.

Set explicit supported thinking to high initially. Current Google docs use `thinking_level` with low/medium/high for 3.8 Flash. Use the exact field supported by the installed SDK, not an invented numeric budget. Compare high with medium after H exists.

The model-name edit is one line. Fallback/thinking changes are additional work. Google lists a free tier; check availability/quota on the existing key and do not enable paid billing. Free-tier content is used to improve Google's products: resolve compliance before real customer/Swiggy data is used.

**Why:** Stronger reasoning is the quickest shopping-quality experiment. It cannot fix unsafe code or missing data.

**Verify:** Run a synthetic request through the live model, record actual model/config without private content, confirm no Lite fallback, and compare identical cases before/after for correctness and latency.

Sources: https://ai.google.dev/gemini-api/docs/models , https://ai.google.dev/gemini-api/docs/thinking , https://ai.google.dev/gemini-api/docs/pricing .

### B. Stop losing the conversation

**Change:** Remove history deletion on errors. Pin the model. Store normal user/assistant turns as plain text. Keep required provider tool/signature state separately intact during the active loop: plain-text storage must not strip Google's required thought/signature blocks from stateless calls.

Persist sessions in the existing Postgres setup, checking readiness first. Keep around 20 recent turns plus task state. Set expiry/deletion, protect stored content, and minimize personal data. At the eight-step limit, return an honest unfinished result and next step.

**Why:** Kills forgetting after errors, restarts, and long tasks, plus silent exits.

**Verify:** Give a request and preference, force a model error, continue, then restart and continue. Constraints must survive. Test two-customer isolation, expiry/deletion, and forced step-limit response.

Provider-state source: https://ai.google.dev/gemini-api/docs/thinking .

### C. Give the agent enough search data

**Change:** Return actual category, pack size/unit, price, stock, max quantity, and similar-item data where supplied. Add a page parameter to look beyond six results without fetching every page by default. Do not invent missing fields.

Return structured errors: failed item ID/name, operation, cause, retry safety, and safe next step. Distinguish not found, stock gap, quantity too high, expired login, and rate limit. No secrets in errors.

**Why:** Kills blind selection and vague failures; enables sensible substitutions and item-specific recovery.

**Verify:** Test the correct product on page two, a quantity limit, and one failed item in a basket. Page only when useful, name the failure, and preserve successful items.

### D. Give the agent a method and enforce budget in code

**Change:** Replace the rule pile with this procedure:

1. Parse items, quantities, budget, diet, and preferences. Ask only about missing details that materially affect the basket.
2. Search each item; use category, pack size, stock, limits, and another page when needed.
3. Pick requested products first, then only permitted alternatives. Never silently break diet/brand rules.
4. Check quantities, substitutions, diet, and estimated budget before cart changes.
5. Build/update cart and read actual items, fees, and payable total from the provider.
6. Enforce stored budget in code. Over-cap or unknown all-in total blocks chargeable checkout. Offer a smaller basket or ask for a new limit.
7. Explain unavailable items/substitutions; show full basket, total, and address for review.
8. Self-check that every item is accounted for, diet/quantity/cap rules hold, and no order occurs without valid approval.

Store budget, diet, brands, quantities, and substitution permission in session fields. The prompt reads them, but is not the only enforcement. Recheck fees/price drift before any chargeable action. The model cannot approve its own budget increase. Unknown dietary attributes require a question, not a guess.

Add four worked examples:

- "Milk and eggs under Rs 300 including fees." Over cap means ask/reduce with permission, never checkout.
- "No dairy. Buy breakfast." Choose verified suitable products or ask about unknown ingredients.
- "Only this brand; skip if unavailable." Skip rather than replace.
- "Make that two packs, keeping my earlier budget." Preserve cap and recheck total.

**Why:** Kills inconsistent shopping, forgotten constraints, silent substitutions, and prompt-only spending control.

**Verify:** Test fees crossing cap, price drift, unknown totals, diet conflicts, unavailable named brands, and quantity corrections. Checkout assertions must show over-cap/unknown-total orders never reach the provider.

### E. Repair consent, review mode, and receipts

**Change:** Accept yes/ok only for one active shown basket. Reject "don't confirm", "do not order", "not now", and other negations before positive matching. Bind expiring one-use approval to exact items, quantities, all-in total, and address. Any change invalidates it.

Consume `CHECKOUT_MODE=review` at every chargeable order/payment-creation path, including direct tool calls. Block in code, not just UI/prompt.

Send full receipts as text, split into labeled parts if normal text limits require it. Drop nothing. Send buttons in a short follow-up so the 1,024-character interactive limit cannot cut receipts.

Stop safely if address/cart migration fails. Do not show a new address as successful while retaining the old-address basket. Reconcile uncertain checkout before retrying; prevent duplicates across restarts/workers.

**Why:** Kills accidental/stale consent, surprise demo charges, hidden receipt lines, wrong-address orders, and duplicates.

**Verify:** Test yes/ok, negations, no pending basket, expired/reused approval, and changed items/price/address. A provider spy in review mode must see zero chargeable calls. Check every line of a long receipt. Simulate address failure, checkout timeout, and restart.

### F. Make tokens private and customer-specific

**Change:** Remove plaintext disk writes on every token path, including supposedly encrypted/durable saves. Use properly encrypted storage and controlled keys. Secure-storage failure must fail closed, not create an unsafe fallback.

One customer uses only their own token. Remove owner fallback and customer-to-owner copying. Safely remove insecure old copies and arrange revocation/rotation if needed. Never print secrets. Deletion/revocation must remove relevant token/session data.

**Why:** Kills credential leaks and shopping through someone else's account. Encrypted Postgres does not fix a plaintext second copy.

**Verify:** Exercise all paths with dummy secrets and check files/logs contain none. Simulate storage failure: no plaintext fallback. Two customers must see only their own accounts. Missing token triggers reconnecting, never owner reuse.

### G. Respect tracking and rate limits

**Change:** At least ten seconds between actual tracking calls, including payment tracking. Keep total/write calls under 70/30 per minute, accounting for concurrency/workers and confirmed quota scope. Handle 429/Retry-After; stop on blocks/rejections. Bound safe-read waits, honor retry-time budget, and never blind-retry checkout.

**Why:** Kills five-second violations and excessive tool traffic.

**Verify:** Fake-clock tracking intervals, concurrent users, 429 with/without Retry-After, and blocks. Confirm waits/stops and no repeated checkout.

### H. Build a 25-30 case live-model quality test

**Change:** Create about 28 realistic requests with expected outcomes. Run the real model with synthetic controlled product data and charge-disabled/mock commerce. Separately validate authorized live Swiggy only after safety/access are resolved.

Cover simple/multi-item baskets, quantities, fees/caps, price drift, diets/unknown ingredients, brands, permitted/forbidden substitutions, stock gaps, paging, quantity limits, partial failures, corrections, errors/restarts, yes/ok/negations, stale/reused consent, long receipts, step limits, expired login, rate limits, uncertain checkout, and address failure.

Record request, fixed test data, expected result, forbidden action, actual result, model/config, and pass/fail reason. Repeat important cases because live answers vary.

**Why:** Kills treating scripted replay or speed as intelligence.

**Verify:** Proposed internal bar, not a Swiggy rule: all safety cases pass; at least 90% ordinary-case success across repeated runs; failures visible and explainable. No accidental checkout, cap breach, cross-customer access, or forbidden substitution. Keep existing code tests and compare before/after on identical cases.

## Part 5: Submission Checklist

### Fix and prove A-H first

- [ ] A: 3.8 Flash; explicit supported thinking; no Lite fallback.
- [ ] B: error/restart memory; pinned model; protected sessions and deletion.
- [ ] C: useful real product data, paging, item-specific errors.
- [ ] D: procedure, stored constraints, all-in budget gate in code.
- [ ] E: basket-bound one-use consent, genuine review block, full receipts, safe address changes.
- [ ] F: no plaintext token path or owner/customer reuse.
- [ ] G: ten-second tracking minimum and tested rate handling.
- [ ] H: live-model evaluation results, including failures.

A-D is the minimum quality improvement pass. It does not make E-G optional for real users or charges. If work remains when submitting for review, disclose it and show a genuinely charge-blocked demo. Do not claim production readiness.

### Upload and test the video

- [ ] Upload the new video to YouTube, Loom, or Drive with link viewing enabled.
- [ ] Open signed out/private browsing and play it; no access request.
- [ ] Show request, choices, substitutions, full total, consent/review, and failure recovery.
- [ ] Label live model versus live/mock commerce honestly.
- [ ] Hide secrets, private phone numbers, addresses, and payment details.
- [ ] Replace/remove the broken `/demo.mp4` link.
- [ ] Correct test counts, root requirements path, and unsupported safety/voice/live claims.

### Fill every verified first-section form field

- [ ] Recorded Google account email checked.
- [ ] Full Name: Karan Wakhare.
- [ ] Monitored contact email.
- [ ] Applicant type: actual individual-developer option.
- [ ] Team/Project Name: Grocer.
- [ ] GitHub/Portfolio: https://github.com/kwakhare5/Grocer .
- [ ] Actual LinkedIn URL.
- [ ] Project explanation.
- [ ] MCP servers: Instamart only.
- [ ] Architecture description.
- [ ] Exact deployed production redirect URL(s); no localhost.
- [ ] Playable no-access video link.
- [ ] Terms read and personally acknowledged.
- [ ] Actual integration type.
- [ ] Honest expected request volume.
- [ ] Later pages after Next checked before submission.

Prepare the access-page extras too: real IP/gateway details, security/technical contacts, privacy declaration, infrastructure notes, audit findings, and realistic traffic/rollout estimates. Do not invent certificates or approvals. Confirm scopes, staging, processing agreements, and unclear limits with Swiggy.

### What to write in architecture

Describe the actual path:

1. WhatsApp sends grocery requests to the backend.
2. Conversation engine reads task state and calls Gemini.
3. Instamart MCP provides search/cart/order tools.
4. Backend uses the customer's own token and controls budget/approval.
5. User reviews items, quantities, substitutions, all-in total, and address.
6. Postgres stores required protected token/session state with expiry/deletion.
7. Vercel serves frontend; Render runs backend. Declare actual regions/outside services.
8. Explain reconnecting, rate waits, uncertain-order checks, and remaining gaps.

Edit this draft to match what is actually fixed and tested:

> Grocer is a WhatsApp grocery assistant that turns a natural-language shopping request into a reviewable Instamart basket. The backend separates conversation handling, Gemini calls, Swiggy MCP, and WhatsApp delivery. It uses each customer's own authentication. The user reviews items, quantities, substitutions, full total, and address before ordering. The frontend is on Vercel and the backend is on Render with Postgres. The application describes tested controls, storage, traffic limits, and remaining gaps. This is a focused prototype seeking developer review and access, not a claim of completed production readiness.

If review mode is used, state that it blocks chargeable orders. Never describe budget enforcement, deletion, or durable sessions as shipped if unfinished. Replace general "tested controls" with specific evidence.

### Honest framing

Say: "I am a fourth-year student building Grocer. It is a working prototype for WhatsApp grocery shopping. Here is the demo, repo, tested scope, and what I am improving before production."

You can explain that you direct AI coding tools. Understand the product and show evidence. Do not pretend every line was independently hand-written or claim outside certification.

Avoid "fully production-ready", unproved "deterministic budget safety", "273 passing tests", mock-backed "verified live orders", and unsupported real-user claims.

Apply at https://forms.gle/4vkeKyqm15Qb6fnJA . The email route is builders@swiggy.in; review any message before sending. Neither submission route itself grants production approval.

### One-page paste-in summary for Antigravity

> Work on Grocer in small tested changes. Inspect active code and reproduce each bug first. Keep the architecture. Use synthetic data and block charges. Never print real secrets. If real users are active, do E/F/G first.
>
> **A:** Set `GEMINI_MODEL=gemini-3.8-flash` with existing key. Remove Lite fallback, pin model per conversation, set supported thinking high. No paid billing. Resolve free-tier data-use compliance before real customer/Swiggy content.
>
> **B:** Stop history deletion on errors. Persist around 20 plain-text turns plus task state in protected Postgres with expiry/deletion/isolation. Preserve required provider signatures separately. Explain step-limit exits. Test errors/restarts.
>
> **C:** Pass real category, pack size, price, stock, max quantity, similar items, and page support where available. Return item-specific cause/next step. Test paging, limits, partial failures.
>
> **D:** Prompt procedure: parse → search → choose → check diet/budget → cart → actual total → explain/review → self-check. Add four examples. Store constraints. Code blocks over-cap/unknown totals. Test fees, drift, corrections, substitutions.
>
> **E:** Yes/ok only for active shown basket; reject negations. Expiring one-use approval binds items/total/address and invalidates on changes. Review mode blocks every chargeable path. Full text receipts, short separate buttons. Safe address/uncertain checkout handling; durable duplicate prevention.
>
> **F:** Remove every plaintext token write/fallback. Secure-storage failure fails closed. One customer, own token; no owner reuse/copying. Test dummy secrets/isolation. Safely clean exposed copies and arrange rotation if needed.
>
> **G:** Tracking at least ten seconds apart. Respect 70 total/30 write calls per minute and concurrency. Honor 429/Retry-After; stop on blocks. No blind checkout retries. Fake-clock tests.
>
> **H:** Add 25-30 cases: live model, synthetic fixtures, charge-disabled commerce. Keep replay tests. All safety cases pass; target 90% ordinary success across repeats. Show failures/config/latency.
>
> After each letter show changed files, failing-before/passing-after tests, and remaining gaps. Correct docs: audited count 51, root requirements, honest live/mock labels, no unproved production/voice claims. Upload playable no-access video and prepare form/privacy/traffic notes. A-D improves quality; E-G cannot be skipped for users/charges. Production claims need Swiggy checklist and approval.
