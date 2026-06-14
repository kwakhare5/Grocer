# Unified Webhook Router for Sandbox and Twilio

We decided to implement a single unified webhook receiver (`POST /api/webhook/whatsapp`) that dynamically handles both local sandbox JSON requests and production Twilio Form requests.

## Context
We need to support two different frontend client channels:
1. **Twilio Webhook:** Twilio posts user replies as `application/x-www-form-urlencoded` Form parameters (`From`, `Body`) and expects a `text/xml` response (TwiML).
2. **Dashboard Chat Sandbox:** The frontend browser drawer posts user replies as `application/json` (`{"phone": str, "message": str}`) and expects a standard `application/json` response.

Instead of writing two parallel endpoints (which duplicates validation, db queries, agent execution, and state persistence logic), we want to leverage a single entry point.

## Decision
We will expose a unified endpoint `POST /api/webhook/whatsapp` in FastAPI. It will parse the incoming request content type:
- If the content type is form-encoded, it will parse the Twilio parameters, run the LangGraph agent, and return a `TwiML` XML response.
- If the content type is JSON, it will parse the JSON parameters, run the LangGraph agent, and return a JSON payload.

## Consequences
- Clean codebase: no duplication of core agent invocation logic.
- Easier E2E testing: any automated script or frontend sandbox tests the exact same webhook controller that handles real production traffic.
