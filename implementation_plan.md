# GROCER Mumbai backend plan — 2026-10-04

## Decision

Move Swiggy token, MCP, agent, WhatsApp queue, and OAuth processing from Render Singapore to a Mumbai (`bom1`) function in the existing Vercel project. Keep the current allowlisted `https://grocerr.vercel.app/` OAuth redirect and the Mumbai Supabase project. Do not buy a service or switch production during the feasibility test. Render cannot be moved to India; the alternative is a signed Swiggy DPA and transfer safeguards for Singapore processing.

## Why a straight deploy will fail

- Render currently runs three infinite polling loops for WhatsApp, replenishment, and payment. Vercel Functions are bounded requests, and Hobby Cron can run only daily.
- The Next.js webhook and OAuth routes currently forward to Render. Moving only the database or frontend function region would still send Swiggy data to Singapore.
- The existing Vercel project may not have the private-beta Services feature. Test a normal Python FastAPI function in a branch preview first; do not design around beta access.
- Supabase Mumbai offers `pg_cron` and `pg_net`, but neither extension is enabled in this project. Enabling them requires a reviewed migration.

## Tracer steps

1. **Preview feasibility:** Add a health-only FastAPI function in the existing Vercel project, pin it to `bom1`, and verify its runtime region, bundle size, Python dependencies, and Hobby execution limit in a preview deployment. Send no Swiggy credentials or customer data.
2. **Durable one-shot worker:** Extract one bounded queue-drain pass from the infinite Render worker. A signed, private worker route processes a limited batch; PostgreSQL claims, deduplication, leases, outbox, and restart recovery stay authoritative. Keep checkout in review mode.
3. **Wake and recovery:** After durable webhook intake, request an immediate private drain from a Mumbai function. Use Supabase `pg_cron`/`pg_net` to retry stranded work at a short interval and to run due replenishment scans. Verify the extension quota and secure the endpoint before enabling the cron job. Never depend on process-resident `BackgroundTasks` for delivery.
4. **Route cutover:** Move WhatsApp, OAuth, simulator, and health calls to the Mumbai backend while preserving the public allowlisted URI. Remove Render from the Swiggy data path only after the same signed webhook and OAuth flows pass on a preview URL.
5. **Proof:** Run E2E with signature, real PostgreSQL state, queue retry, duplicate delivery, process restart, model timeout, 429, provider drift, and unknown Meta delivery. Verify `bom1` from actual request metadata. Run paced read-only real MCP through the new path; real cart mutation needs an exact customer-selected variant. No paid order.
6. **Release and cleanup:** Switch production traffic only after a green preview, region evidence, documented rollback, and the Swiggy go-live gates. Retire Render-specific loops/config and provably unused files in tested slices. Keep the database backup and current production revision until rollback is safe.

## Current evidence

- Local branch `codex/full-whatsapp-recovery` passes 37 signed-webhook/PostgreSQL E2E cases and one bounded real Swiggy product search returned six choices.
- The live Render service API reports `singapore`; Supabase database is Mumbai. Render does not list an India region. Vercel lists `bom1` and supports Python FastAPI functions; Hobby Cron is daily. Supabase lists Mumbai regional invocations and pg_cron/pg_net. None of this proves GROCER's existing Vercel project can run the complete backend within free limits.
- A six-case real-model/synthetic-commerce probe found two failed shopping requests and an unverified budget claim. One Hinglish matching defect was reproduced and corrected locally; the broader AI redesign remains open.

## Release gate

Keep GitHub main and Render at `2eb23aa` until this plan's Mumbai preview and full-path evidence are reviewed. Do not claim 10/10, real WhatsApp delivery, real cart mutation, or payment completion from local simulation.

Sources: [Swiggy data handling](https://mcp.swiggy.com/builders/docs/operate/data-and-compliance/), [Render regions](https://render.com/docs/regions), [Vercel regions](https://vercel.com/docs/regions), [Vercel Python](https://vercel.com/docs/functions/runtimes/python), [Vercel Cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing), [Supabase Cron](https://supabase.com/docs/guides/cron).
