# Real Swiggy MCP verification — 2026-10-03

## Scope and proof

- Production GitHub/Render/Vercel revision: `1551507`; Render `/api/ready` returned `ready` and `checkout_mode=review`. GitHub Quality workflow passed.
- Customer-originated WhatsApp `show my basket` returned “Your basket is empty. What groceries would you like to add?” after deployment. This verifies the reported address-prompt bug no longer appears for that exact request.
- GROCER's production OAuth vault and `SwiggyMCPAdapter` completed one paced, read-only Charholi session: `get_addresses` (3 saved addresses), `get_cart` (empty, ₹0), and four `search_products` queries. Exit code 0. Sanitized result: `artifacts/real_mcp_charholi_readonly.json`.
- Search counts: milk 18 products; pizza base 6; Bournvita 12; tissues 20. The six sampled pizza-base variants were unavailable. The Bournvita response included Horlicks products. Counts and prices are time- and address-specific, not guaranteed future stock.
- No live cart update, clear, checkout, order, or payment call was made in this session.

## Confirmed gaps

1. **Variant selection:** The current `quick_add_items` path takes the first matching available search result when no pack size is specified. Swiggy's current `search_products` reference says to show variants and ask the customer which specific variant to add. A grouped variant review should replace silent first-result selection before real cart writes. GROCER must still account for every requested item and show unavailable or similar products separately.
2. **Rate limiting:** The current MCP HTTP client handles HTTP 429 as a generic commerce error. Swiggy's rate-limit contract says to stop immediately, respect `Retry-After`, and avoid repeated auth/session attempts. This needs an explicit error branch and a bounded end-to-end failure check.
3. **Credential health:** Vault loading reports one stored Swiggy credential could not be decrypted safely. The current test customer's OAuth credential worked. The other record needs private provenance review; do not merge identities or expose tokens.
4. **Real model turn:** Automatic approval review rejected the attempted model-driven live test before it ran because it would send saved-address and tool data to Groq without specific authorization. No workaround was attempted. The user must explicitly authorize that data flow before model-driven testing with live customer data.
5. **Cart and replenishment:** Real cart mutation/reversal, provider bill and payment-option verification, consented history sync, reminder template delivery, and human-adversarial multi-turn behavior are unproven. Paid checkout remains disabled and unauthorized.

## Next bounded sequence

1. Obtain explicit approval for sending this customer's saved-address, catalog, and cart data to the configured Groq model for testing. Keep the provider fixed to Groq for the run and record only sanitized evidence.
2. Replace silent variant selection with an explicit grouped customer choice. Verify the candidate list reflects real Charholi stock, pack sizes, and requested brands.
3. Run a small number of real agent turns (simple, multi-item, scoped budget, corrections, unavailable item, provider error), counting every MCP call. Stop on 429, auth failure, or unexpected cart state.
4. After the customer chooses a specific live variant, verify one real add → get_cart → clear → get_cart cycle. Do not place an order.
5. Reconcile the remaining safety and recovery flows, clean old unit-test code only after its material behavior is covered by full-path E2E, then release and reverify the changed revision.

Swiggy references: [search_products](https://mcp.swiggy.com/builders/docs/reference/instamart/search_products.md), [update_cart](https://mcp.swiggy.com/builders/docs/reference/instamart/update_cart.md), [rate limits](https://mcp.swiggy.com/builders/docs/operate/rate-limits.md).
