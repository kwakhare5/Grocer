# Use Postgres Checkpointer for LangGraph State Persistence

We decided to use LangGraph's native `PostgresSaver` checkpointer to persist conversation state for the restock agent across multi-turn WhatsApp interactions.

## Context
The restocking flow involves a multi-turn conversation over WhatsApp (Alert ➔ User Reply ➔ Cart Build ➔ User Confirm ➔ Order Placed). Since WhatsApp notifications are processed via stateless HTTP webhook requests (via Twilio), the agent graph must suspend execution while waiting for the user's asynchronous reply and resume it when the reply arrives. 

Initially, we considered custom DB serialization mapping (storing states in the `RestockAlert` columns). However, custom serialization is error-prone, hard to scale for complex conversational trees, and duplicates the state-tracking features already provided by LangGraph.

## Decision
We will use LangGraph's native `PostgresSaver` as a checkpointer. Graph state will be automatically serialized to a Postgres-backed checkpoint store and keyed on `thread_id` (derived from the household's phone number). 

This allows us to:
1. Standardize state persistence across all conversational agents (e.g. recipe agent, price agent).
2. Clean up webhook routers by removing manual state reconstruction logic.
3. Automatically resume state graphs at the exact node waiting for input (`parse_reply`).

## Consequences
- Requires a dedicated database table (`checkpoints` and related tables managed by `PostgresSaver`) inside our existing TimescaleDB/PostgreSQL instance.
- Webhook endpoints must initialize the `PostgresSaver` and retrieve/resume execution using a unified `thread_id`.
