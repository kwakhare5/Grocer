# Official platform findings — GROCER submission

Research date: 2026-09-15. Scope: an English-only, WhatsApp-first consumer agent for Swiggy Instamart that asks when information is missing and never claims an unknown checkout succeeded.

## Verified platform facts

### Swiggy Instamart

- The intended grocery journey is address → search/reorder → cart → live cart review → checkout → tracking. A cart must be reviewed before checkout; address serviceability and the ₹99 minimum are documented failure cases. [Order groceries end-to-end](https://mcp.swiggy.com/builders/docs/build/recipes/order-groceries/)
- `checkout` is mutating, requires a user-selected address and payment method, and Swiggy explicitly requires a live cart summary, address, payment method, and clear user confirmation before the call. Multi-store carts may produce partial results and must be reported per order. [Checkout reference](https://mcp.swiggy.com/builders/docs/reference/instamart/checkout/)
- Checkout is not safe to blindly retry after a network/5xx failure. The documented sequence is wait briefly, call `get_orders`, treat a found order as success, and retry only when no order exists. [Ship to production](https://mcp.swiggy.com/builders/docs/build/ship-to-production/)
- Current failures use a human-readable `error.message`; stable symbolic error codes are explicitly documented as planned, not current. Domain failures such as out-of-stock or a stale cart should be surfaced rather than retried. [Error codes](https://mcp.swiggy.com/builders/docs/reference/errors/)
- UPI payment can remain pending. Poll only at the returned cadence; do not call `confirm_order` after terminal payment failure, and do not call it again when the response already says `confirmed=true`. [Payment-status reference](https://mcp.swiggy.com/builders/docs/reference/instamart/check_payment_status/)
- Consumer OAuth is OAuth 2.1 with PKCE. Access tokens are per user, last five days, must be stored securely rather than in plaintext, and a 401 requires reauthorization rather than reuse of the same token. [Delegated auth](https://mcp.swiggy.com/builders/docs/start/enterprise/delegated-auth/)

### WhatsApp Cloud API and policy

- Meta documents outbound message status events including `sent`, `delivered`, `read`, `failed`, and `deleted`. A successful send request is therefore not proof of delivery; retain the provider message ID and process status webhooks. [Official Meta webhook payload reference](https://www.postman.com/meta/whatsapp-business-platform/folder/tduohwq/webhook-payload-reference)
- Meta's published Cloud API resources require a business portfolio, WhatsApp Business Account, business phone number, and the applicable messaging/management permissions. Secrets belong in managed configuration, not source code. [Cloud API overview](https://developers.facebook.com/docs/whatsapp/cloud-api/overview)
- Under WhatsApp's policy, free-form customer-service messaging is limited to the customer-service window following a user message; later re-engagement requires an approved template. The policy also requires opt-in, honoring stop/block requests, an accessible support path, and a privacy policy. [WhatsApp Business Messaging Policy](https://business.whatsapp.com/policy/preview?lang=en)
- Interactive controls are useful only as bounded choices: the Meta-hosted Cloud API SDK documents reply buttons (up to three) and list messages with opaque option IDs suitable for server-side routing. The SDK is archived, so its exact request schema must be rechecked against current Meta docs before any API change. [Interactive-message reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/interactive/)

## Recommendations for GROCER (not platform facts)

1. Treat free English text as an *untrusted proposed command*. Validate it against the active session and live Swiggy state before every mutation. Use opaque server-issued button/list IDs for address, option, payment, and confirmation choices.
2. Default to clarification, never silent substitution: when a product, brand, pack size, address, budget, payment method, or order outcome is uncertain, explain what happened in plain English and present the next safe choice.
3. Make the final confirmation message a fixed structure: **Items**, **live total**, **delivery address**, **payment method**, then **“Reply Confirm to place this order.”** A change to any of those values invalidates that confirmation.
4. Separate two facts in every message: (a) what GROCER knows from Swiggy and (b) what it needs the user to decide. Never show raw HTTP/MCP errors, invent an ETA, or say an order was placed until Swiggy has returned a verified success/order ID. On ambiguous checkout, say it is being checked and query order history before any retry.
5. The landing page and WhatsApp profile should accurately say that GROCER is an independent assistant using Swiggy Instamart integration; do not imply it is Swiggy unless that branding is authorized. Publish privacy, support, opt-in, stop, and re-connect guidance.
6. For the submission, show evidence rather than a "bulletproof" claim: test transcripts for normal ordering, ambiguity, out-of-stock, stale cart, payment pending/failure, OAuth expiry, failed message delivery, and unknown checkout recovery. No commerce agent can honestly guarantee zero external-provider failures.
