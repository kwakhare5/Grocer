# PreFill — Historical Context & ADRs

This document summarizes the core architectural decisions and product specifications that shaped PreFill (formerly Instamart Intelligence).

## Architectural Decision Records (ADRs)

1. **LangGraph Postgres Checkpointer:**
   We utilize LangGraph's `PostgresSaver` to persist multi-turn conversational state natively inside our PostgreSQL/TimescaleDB database. This unifies state across all agents (Restock, Recipe) and allows us to seamlessly pause and resume graphs while waiting for asynchronous WhatsApp webhooks.

2. **Unified Webhook Router:**
   A single FastApi endpoint (`POST /api/webhook/whatsapp`) dynamically parses both `application/x-www-form-urlencoded` (from Twilio in production) and `application/json` (from the local Dashboard Sandbox). This prevents logic duplication and simplifies E2E testing.

3. **Multi-tier LLM Fallbacks & Local Determinism:**
   To guarantee a zero-cost API footprint and maximum reliability, the agent attempts to parse intents using local deterministic logic (regex, RapidFuzz string matching) first. If an LLM is required, it routes through a fallback chain (Anthropic -> Groq -> NVIDIA NIM), remaining entirely free for local development.

## Core Feature Specifications

1. **Conversational Resilience:**
   - **No Truncation:** Low-stock items are never sliced (e.g., `names[:3]`). Every item is explicitly listed.
   - **Fuzzy Catalog Matching:** "tomato" successfully maps to "Tomatoes (500g)" via bidirectional token matching (powered by RapidFuzz), bypassing rigid exact-match constraints.
   - **Done-Stage Safety:** If a user replies to an already-completed checkout thread, the graph intercepts the message instantly and returns a friendly reminder instead of crashing or duplicating orders.

2. **UI/UX Simplification (Anti-Jargon):**
   - Developer terminology is hidden from the end user.
   - *T-1d* becomes "Out tomorrow!".
   - *CONF: 87%* becomes "High accuracy prediction".
   - Primary accents use the signature orange `#ff5a00`, ensuring the dashboard feels like a premium, consumer-facing product rather than an engineering debug tool.
