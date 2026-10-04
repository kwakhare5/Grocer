# Region evaluation — deferred 2026-10-04

GROCER will keep the existing Render backend while work returns to shopping reliability, real MCP checks, and full-path E2E. Production still runs Render in Singapore and the new Supabase project in Mumbai. No backend region or live route was changed.

## Verified facts

- Render offers no India region and cannot change an existing service's region.
- Swiggy says MCP responses processed outside India require a signed DPA and cross-border safeguards before production. Render Singapore meets that condition. An India backend alone would not settle where an external AI provider processes Swiggy data.
- A protected Vercel branch preview ran both Next.js and a Python FastAPI route in Mumbai (`bom1`). A nested FastAPI path under a file-based Python function returned 404. A separate Vercel backend preview project was created without credentials, never deployed successfully, and removed. The experimental routes and settings were removed from the recovery branch.
- Vercel's Hobby tier is limited to personal, non-commercial use, so it is not a confirmed free production answer for paid customer shopping.

## Revisit only after core reliability work

Before calling the existing Render path production-compliant, establish the Swiggy DPA and transfer safeguards, or choose an India execution path that also addresses model processing. Preserve the existing whitelisted `https://grocerr.vercel.app/` redirect. Do not delete or move Render until a replacement passes the full WhatsApp and real MCP paths.

Sources: [Swiggy data handling](https://mcp.swiggy.com/builders/docs/operate/data-and-compliance/), [Render regions](https://render.com/docs/regions), [Vercel regions](https://vercel.com/docs/regions), [Vercel Python](https://vercel.com/docs/functions/runtimes/python), [Vercel Hobby terms](https://vercel.com/docs/limits/fair-use-guidelines).
