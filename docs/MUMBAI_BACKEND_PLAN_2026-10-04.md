# GROCER Mumbai backend plan — 2026-10-04

## Decision

Move Swiggy token, MCP, agent, WhatsApp queue, and OAuth processing from Render Singapore to a Mumbai (`bom1`) Vercel backend project under the existing account. Keep the existing Next.js project and allowlisted `https://grocerr.vercel.app/` OAuth redirect, plus the Mumbai Supabase project. Do not buy a service or switch production during the feasibility test. Render cannot be moved to India; the alternative is a signed Swiggy DPA and transfer safeguards for Singapore processing.

## Why a straight deploy will fail

- Render currently runs three infinite polling loops for WhatsApp, replenishment, and payment. Vercel Functions are bounded requests, and Hobby Cron can run only daily.
- The Next.js webhook and OAuth routes currently forward to Render. Moving only the database or frontend function region would still send Swiggy data to Singapore.
- The existing Next.js project can host a Python file-based function, but its nested FastAPI routes returned 404 in a live preview. Vercel Services could combine both frameworks in one project, but that feature is private beta. Test a separate FastAPI project on the same Vercel account instead.
- Vercel's free Hobby tier is restricted to personal non-commercial use. The preview can establish technical feasibility, but paid customer checkout cannot be declared production-compliant on Hobby.
- Supabase Mumbai offers `pg_cron` and `pg_net`, but neither extension is enabled in this project. Enabling them requires a reviewed migration.

## Tracer steps

1. **Preview feasibility:** Verify Next.js and a no-data Python probe in `bom1` on the existing Vercel branch preview, then deploy a separate FastAPI backend preview in the same Vercel account. Check routing, bundle size, Python dependencies, and Hobby execution limit before moving any customer data. Send no Swiggy credentials or customer data to the preview.

   First probe: a standard-library Python function at `/api/region_preview` returned only `VERCEL_REGION`. The protected branch preview built, and an authenticated CLI call returned `{"region":"bom1"}`; the homepage returned HTTP 200. The simulator returns 404 by design outside local development. After setting the project-wide region, Vercel inspect showed the existing Next.js functions in `bom1` and the Python probe still returned `bom1`. The same probe converted to FastAPI and returned HTTP 200 with `{"region":"bom1"}`. A nested `/api/region_preview/nested` route fell through to Next.js 404, so the existing project cannot host the current multi-route FastAPI backend through that file path. No production deployment changed.
2. **Durable one-shot worker:** Extract one bounded queue-drain pass from the infinite Render worker. A signed, private worker route processes a limited batch; PostgreSQL claims, deduplication, leases, outbox, and restart recovery stay authoritative. Keep checkout in review mode.
3. **Wake and recovery:** After durable webhook intake, request an immediate private drain from a Mumbai function. Use Supabase `pg_cron`/`pg_net` to retry stranded work at a short interval and to run due replenishment scans. Verify the extension quota and secure the endpoint before enabling the cron job. Never depend on process-resident `BackgroundTasks` for delivery.
4. **Route cutover:** Point the existing Next.js WhatsApp and OAuth forwarding routes to the separate Mumbai backend while preserving the public allowlisted URI. Keep the simulator local and private. Remove Render from the Swiggy data path only after the same signed webhook and OAuth flows pass on a preview URL.
5. **Proof:** Run E2E with signature, real PostgreSQL state, queue retry, duplicate delivery, process restart, model timeout, 429, provider drift, and unknown Meta delivery. Verify `bom1` from actual request metadata. Run paced read-only real MCP through the new path; real cart mutation needs an exact customer-selected variant. No paid order.
6. **Release and cleanup:** Switch production traffic only after a green preview, region evidence, documented rollback, and the Swiggy go-live gates. Retire Render-specific loops/config and provably unused files in tested slices. Keep the database backup and current production revision until rollback is safe.

## Current evidence

- Local branch `codex/full-whatsapp-recovery` passes 37 signed-webhook/PostgreSQL E2E cases and one bounded real Swiggy product search returned six choices.
- The live Render service API reports `singapore`; Supabase database is Mumbai. Render does not list an India region. Vercel lists `bom1` and supports Python FastAPI functions; Hobby Cron is daily. Supabase lists Mumbai regional invocations and pg_cron/pg_net. The existing Vercel preview proved Next.js and a single Python FastAPI route in `bom1`, but a nested FastAPI route returned 404. A separate backend project and the free-tier commercial terms remain release gates.
- A six-case real-model/synthetic-commerce probe found two failed shopping requests and an unverified budget claim. One Hinglish matching defect was reproduced and corrected locally; the broader AI redesign remains open.

## Release gate

Keep GitHub main and Render at `2eb23aa` until this plan's Mumbai preview and full-path evidence are reviewed. Do not claim 10/10, real WhatsApp delivery, real cart mutation, or payment completion from local simulation.

Sources: [Swiggy data handling](https://mcp.swiggy.com/builders/docs/operate/data-and-compliance/), [Render regions](https://render.com/docs/regions), [Vercel regions](https://vercel.com/docs/regions), [Vercel Python](https://vercel.com/docs/functions/runtimes/python), [Vercel Services](https://vercel.com/docs/services), [Vercel Hobby terms](https://vercel.com/docs/limits/fair-use-guidelines), [Vercel Cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing), [Supabase Cron](https://supabase.com/docs/guides/cron).
