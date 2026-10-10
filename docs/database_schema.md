# Grocer Database Architecture & Schema Reference

This document details the PostgreSQL database schema used by Grocer in production (hosted on Supabase) and in automated integration tests.

---

## Why Grocer Requires PostgreSQL

Grocer is a high-reliability conversational commerce agent for WhatsApp. WhatsApp webhooks and payment gateways operate under strict real-time and delivery-guarantee constraints that cannot be safely managed in server memory:

1. **Webhook Idempotency & Replay Prevention**:
   Meta's WhatsApp Cloud API expects an HTTP 200 response within 3 seconds. When AI reasoning or catalog queries take several seconds, Meta retries the delivery. Grocer stages incoming messages in `grocer_internal.inbound_messages` and uses PostgreSQL advisory row-level locking (`inbound_claimed_at`) to ensure each customer message is processed exactly once.

2. **Durable Token Vault Across Restarts**:
   Customer OAuth access tokens for Swiggy Instamart are encrypted with AES-256 and stored in `grocer_internal.connect_tickets`. Server restarts or blue-green deployments on Render do not log users out.

3. **Multi-Turn Cart & Constraint State**:
   `grocer_internal.task_state` records the active cart fingerprint, pending variant choices (`1A`, `2B`), and budget limits (`₹800`) across turns. If a customer sends an update minutes or hours later, their cart and constraints remain intact.

4. **Household Replenishment Cadence**:
   `grocer_internal.replenishment` stores historical purchase intervals and customer consent preferences for proactive grocery restock suggestions.

---

## Database Schema (`grocer_internal`)

All Grocer tables live inside the isolated `grocer_internal` schema to prevent namespace collisions.

### 1. `inbound_messages` (Webhook Ingestion Queue)
Records all incoming WhatsApp webhooks with cryptographic HMAC signatures.

```sql
CREATE TABLE grocer_internal.inbound_messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,      -- Meta WAMID (idempotency key)
    sender_id VARCHAR(64) NOT NULL,               -- Customer WhatsApp phone number
    customer_id VARCHAR(64) NOT NULL,             -- Deterministic hashed customer UUID
    channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp',
    raw_payload JSONB NOT NULL,                   -- Complete signed webhook payload
    signature VARCHAR(255) NOT NULL,              -- X-Hub-Signature-256 header
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',-- PENDING, PROCESSING, COMPLETED, FAILED
    claimed_at TIMESTAMPTZ,                       -- Lock timestamp preventing parallel processing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2. `outbound_messages` (Staged Delivery Queue)
Staged responses delivered to WhatsApp with 3-attempt bounded retries.

```sql
CREATE TABLE grocer_internal.outbound_messages (
    id SERIAL PRIMARY KEY,
    inbound_id INT REFERENCES grocer_internal.inbound_messages(id),
    customer_id VARCHAR(64) NOT NULL,
    recipient_id VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,
    interactive_actions JSONB,                    -- Button/list choices (e.g. variant selection)
    conversation_state VARCHAR(64) NOT NULL,     -- READY, NEEDS_DECISION, AWAITING_PAYMENT
    delivered BOOLEAN NOT NULL DEFAULT FALSE,
    sending_started_at TIMESTAMPTZ,              -- Lock timestamp for outbound delivery attempt
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3. `connect_tickets` (Encrypted Token Vault)
Stores customer Swiggy OAuth tokens encrypted via Fernet (AES-256-CBC).

```sql
CREATE TABLE grocer_internal.connect_tickets (
    ticket_id VARCHAR(128) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    sender_id VARCHAR(64) NOT NULL,
    encrypted_token TEXT NOT NULL,                -- AES-256 encrypted access token
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4. `checkout_attempts` (Server-Side Gated Checkout Audit)
Audits every order creation attempt, price snapshot, and generated payment link.

```sql
CREATE TABLE grocer_internal.checkout_attempts (
    attempt_id VARCHAR(128) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    cart_snapshot JSONB NOT NULL,                 -- Verified item list and prices at checkout time
    amount_inr NUMERIC(10, 2) NOT NULL,          -- Final payable amount
    payment_link TEXT,                           -- Dynamic UPI payment link
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',-- PENDING, CONFIRMED, EXPIRED, CANCELLED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5. `task_state` (Conversational State & Memory)
Durable state store backing multi-turn intent preservation across restarts.

```sql
CREATE TABLE grocer_internal.task_state (
    customer_id VARCHAR(64) PRIMARY KEY,
    address_id VARCHAR(128),                      -- Active delivery address ID
    pending_request_text TEXT,                    -- Active recipe or list being planned
    pending_variant_selection JSONB,              -- Active 1A/2A product choice state
    budget_inr NUMERIC(10, 2),                   -- Enforced rupee budget ceiling
    cart_fingerprint VARCHAR(128),               -- SHA256 hash of active Swiggy cart
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 6. `replenishment` (Household Cadence & Restock Memory)
Stores purchase intervals and consented replenishment schedules.

```sql
CREATE TABLE grocer_internal.replenishment (
    customer_id VARCHAR(64) PRIMARY KEY,
    opted_in BOOLEAN NOT NULL DEFAULT FALSE,      -- Explicit customer consent flag
    cadence_habits JSONB NOT NULL DEFAULT '{}',   -- Item ordering frequencies (e.g. milk: 2 days)
    last_restock_check TIMESTAMPTZ,               -- Last replenishment evaluation timestamp
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Migration History

Migrations are located in `migrations/` and run sequentially during setup:

| File | Purpose |
|---|---|
| `bootstrap_fresh.sql` | Creates schema `grocer_internal` and core database extensions |
| `001_connect_tickets.up.sql` | Adds customer token vault and ticket storage |
| `002_messages.up.sql` | Adds `inbound_messages` and `outbound_messages` tables |
| `003_checkout_attempts.up.sql` | Adds gated checkout audit trail |
| `004_task_state.up.sql` | Adds durable multi-turn task state persistence |
| `005_privacy_deletions.up.sql` | Adds data purge audit log for `delete my data` |
| `006_inbound_claimed_at.up.sql` | Adds row locking for inbound message intake |
| `007_outbound_sending_started_at.up.sql` | Adds delivery lock for staged outbound queue |
| `008_payment_followups.up.sql` | Adds automated payment reconciliation tracking |
| `009_replenishment.up.sql` | Adds consented cadence and replenishment storage |

---

## Connection Setup

- **Production**: Configured via the `DATABASE_URL` environment variable pointing to Supabase PostgreSQL pooler.
- **Local Development**: Not required for web simulator or UI development (in-memory simulator mode).
- **CI / Integration Tests**: Automatically provisions a throwaway PostgreSQL 16 container in GitHub Actions on port 55432.
