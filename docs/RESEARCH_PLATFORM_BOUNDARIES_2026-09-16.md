# Platform boundary research for GROCER

Research date: 2026-09-16
Scope: distinguish transport/integration failures from conversation-state failures in the English-only WhatsApp Instamart agent.

## Executive conclusion

The platform path is a request/response chain, not an AI loop performed by WhatsApp or Vercel. Meta delivers webhook events to the configured HTTPS endpoint; the application parses and executes the user request; the application calls Swiggy MCP; the application verifies the result and sends a separate outbound WhatsApp message. The difficult behavior in the reported transcript (old products retained, `ltr` misread, and “cancel other just have…” misread) is therefore application-level interpretation/state/cart reconciliation, unless delivery logs prove otherwise.

## Meta WhatsApp Cloud API

- Incoming events are HTTPS POST webhook notifications. The payload identifies a WhatsApp Business Account and includes `messaging_product`, `metadata.phone_number_id`, and message/status-specific data. The WABA must be subscribed to the app to receive events. [Meta WhatsApp Cloud API webhook payload reference (Meta's official Postman collection)](https://www.postman.com/meta/whatsapp-business-platform/folder/tduohwq/webhook-payload-reference)
- Webhook verification is a separate GET handshake: the endpoint must validate the verification token and return `hub.challenge`; POST authenticity is checked with `x-hub-signature-256` and the app secret. [Meta WhatsApp Node.js SDK webhook reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/)
- A successful webhook response acknowledges receipt; message delivery status is separately reported by webhook events (`sent`, `delivered`, `read`, `failed`). This means an HTTP 200 from the inbound webhook does not prove that the final outbound reply was delivered to the user. [Meta webhook payload reference](https://www.postman.com/meta/whatsapp-business-platform/folder/tduohwq/webhook-payload-reference)
- Outbound replies are API calls to the Graph API messages endpoint for the business phone-number ID, authenticated with a bearer token. [Meta WhatsApp Cloud API official collection](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
- Interactive messages are structured WhatsApp messages. They are appropriate for bounded decisions such as address, payment, confirmation, and recovery options; free text remains necessary for open-ended grocery requests. [Meta interactive-message reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/interactive/)

**Diagnostic implication:** If the user receives a reply, Meta → webhook → backend → outbound API is already functioning for that turn. A wrong product, wrong quantity, stale cart, or wrong interpretation is not caused by Vercel transport. To diagnose delivery separately, correlate message IDs and delivery-status webhooks; do not infer delivery from a successful backend response.

## Vercel / Next.js route boundary

- In Next.js App Router, a file under `app/api/.../route.ts` is deployed as a Vercel Function and handles the standard `Request` object. Each incoming request is a function invocation; the instance may be reused, but in-memory state is not a durable database. [Vercel Functions API reference](https://vercel.com/docs/functions/functions-api-reference)
- Vercel Functions can call external APIs, but runtime, timeout, region, and environment-variable configuration are part of the deployment contract. [Vercel Functions documentation](https://vercel.com/docs/functions)

**Diagnostic implication:** Vercel is a transport/proxy boundary. It should validate the webhook, forward a bounded request to the Python service, return a fast acknowledgement where required, and avoid owning cart/session state. A Vercel route cannot make the agent “understand language”; that behavior belongs to the backend conversation layer. Durable sessions must live in a real persistent store before multi-instance production use.

## Swiggy MCP / Instamart

- Instamart is exposed as a streamable HTTP MCP server at `POST https://mcp.swiggy.com/im`; the reference lists the discover, cart, checkout, payment, order, and support tools. [Swiggy Instamart reference](https://mcp.swiggy.com/builders/docs/reference/instamart/)
- External callers use OAuth 2.1 with PKCE. Access is user-scoped; the documented access-token lifetime is five days, and a 401 means the caller must re-authorize. The documented v1 token flow does not provide refresh-token issuance. [Swiggy authentication](https://mcp.swiggy.com/builders/docs/start/authenticate/)
- Tool responses use a common envelope: success responses contain `success: true` and `data`; failures contain `success: false` and an `error.message`. The current error catalogue uses human-readable messages rather than relying on invented application error codes. [Swiggy error reference](https://mcp.swiggy.com/builders/docs/reference/errors/)
- Swiggy’s checkout guidance requires a live cart summary, selected address, selected payment method, and clear user confirmation before invoking the mutating checkout operation. A network/5xx result must not be blindly retried; the documented safe procedure is to check order history first and retry only when no order exists. [Swiggy checkout reference](https://mcp.swiggy.com/builders/docs/reference/instamart/checkout/) and [Swiggy production guidance](https://mcp.swiggy.com/builders/docs/build/ship-to-production/)
- Swiggy documents payment-pending states and requires polling according to the returned status/cadence; `confirm_order` must not be called after terminal failure or redundantly after a confirmed result. [Swiggy payment-status reference](https://mcp.swiggy.com/builders/docs/reference/instamart/check_payment_status/)
- Swiggy’s `report_error` tool is intended to produce a support report with the failed tool and relevant IDs such as `cartId`, `orderId`, `addressId`, and payment identifiers. [Swiggy report_error reference](https://mcp.swiggy.com/builders/docs/reference/instamart/report_error/)

**Diagnostic implication:** Swiggy can return a valid, successful cart response that is nevertheless wrong for the user’s request if the application sent the wrong search term, quantity, cart ID, or preserved an existing cart. The backend must compare returned cart state to the structured intent; provider success alone is not intent success. A 401/403/5xx/provider error is an integration/auth/reliability event and must be translated to a user action, not exposed as a raw error.

## Boundary-by-boundary test matrix

| Boundary | What proves it works | What it cannot prove |
|---|---|---|
| WhatsApp → Vercel | Meta verification succeeds; real inbound POST is accepted and logged by message ID | That parsing or ordering is correct |
| Vercel → Python | Correlation ID reaches backend and bounded response returns | That the session is durable or the intent is correct |
| Python conversation layer | Golden human transcripts produce the intended structured command | That Swiggy has the requested SKU/cart state |
| Python → Swiggy MCP | Authenticated tool call returns expected schema; 401/5xx/error paths are handled | That a provider-success cart matches user intent |
| Swiggy → Python verification | Cart/order/address/payment state is re-read and compared to hard constraints | That WhatsApp delivered the final reply |
| Python → WhatsApp | Graph API returns message ID and status webhooks are observed | That a user understands an ambiguous message without UX testing |

## What this research does and does not establish

These sources establish the platform contracts and the correct places to instrument. They do **not** prove that GROCER currently has valid production Meta credentials, a subscribed WABA, durable session storage, authenticated Swiggy credentials, or a successful real checkout. Those must be demonstrated by environment-safe live tests and traceable message/order IDs. No platform documentation supports a claim of zero failures; production quality comes from explicit state, verification, bounded recovery, idempotency, and evidence-based testing.
