# Grocer Database Architecture & Schema Reference

This document details the PostgreSQL database schema used by Grocer in production (hosted on Supabase) and in automated integration tests.

---

## Why Grocer Requires PostgreSQL

Grocer is a conversational grocery assistant for WhatsApp with deterministic intent verification, bounded recovery, and Swiggy Instamart integration. Webhooks and payment gateways operate under strict real-time and delivery-guarantee constraints that cannot be safely managed in server memory:

1. **Webhook Idempotency & Replay Prevention**:
   Meta's WhatsApp Cloud API expects an HTTP 200 response within 3 seconds. When AI reasoning or catalog queries take several seconds, Meta retries the delivery. Grocer stages incoming messages in `grocer_internal.inbound_messages` and uses PostgreSQL row-level locking (`claimed_at`) with `SKIP LOCKED` to ensure each customer message is processed exactly once in order.

2. **Zero-Knowledge Token Vault Across Restarts**:
   Customer OAuth access tokens and PKCE state for Swiggy Instamart are encrypted with Fernet (AES-128-CBC with HMAC-SHA256) and stored in `grocer_internal.oauth_tokens` and `grocer_internal.oauth_pending_flows`. Server restarts or deployments on Render do not log users out.

3. **Multi-Turn Cart & Constraint State**:
   `grocer_internal.task_state` records the encrypted customer session (active cart fingerprint, pending variant choices, budget limits, unresolved items) with a 30-day retention window. If a customer sends an update hours later, their cart and constraints remain intact.

4. **Household Replenishment Cadence**:
   `grocer_internal.replenishment` stores encrypted purchase intervals and customer consent preferences for proactive grocery restock suggestions.

5. **Server-Side Gated Checkout Audit**:
   `grocer_internal.checkout_attempts` provides a durable, non-idempotent audit trail for every checkout execution, tracking order state and automated payment reconciliation.

---

## Database Schema (`grocer_internal`)

All Grocer tables live inside the isolated `grocer_internal` schema to prevent namespace collisions.

### 1. `oauth_tokens` (Encrypted Token Vault)
Stores customer Swiggy OAuth access tokens encrypted at rest.

```sql
CREATE TABLE grocer_internal.oauth_tokens (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    expires_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX oauth_tokens_expires_idx
    ON grocer_internal.oauth_tokens (expires_at);
```

### 2. `oauth_pending_flows` (OAuth PKCE State Handshake)
Single-use ephemeral store for in-flight OAuth 2.1 PKCE authorization handshakes.

```sql
CREATE TABLE grocer_internal.oauth_pending_flows (
    state_hash bytea PRIMARY KEY,
    ciphertext bytea NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX oauth_pending_flows_expires_idx
    ON grocer_internal.oauth_pending_flows (expires_at);
```

### 3. `connect_tickets` (Verified WhatsApp Sender Tickets)
Single-use time-bounded connection tickets issued to verified WhatsApp senders for account linking.

```sql
CREATE TABLE grocer_internal.connect_tickets (
    ticket_hash bytea PRIMARY KEY,
    customer_id text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX connect_tickets_expires_idx
    ON grocer_internal.connect_tickets (expires_at);
```

### 4. `inbound_messages` (Webhook Ingestion Queue)
Records all incoming WhatsApp webhooks with status tracking and row-level locking.

```sql
CREATE TABLE grocer_internal.inbound_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id text NOT NULL UNIQUE,
    customer_id text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'NEEDS_REVIEW')),
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    claimed_at timestamptz
);

CREATE INDEX inbound_messages_pending_idx
    ON grocer_internal.inbound_messages (id) WHERE status = 'PENDING';
CREATE INDEX inbound_messages_stale_processing_idx
    ON grocer_internal.inbound_messages (claimed_at) WHERE status = 'PROCESSING';
```

### 5. `outbound_messages` (Staged Delivery Queue)
Staged responses delivered to WhatsApp with bounded delivery tracking and automated payment followups.

```sql
CREATE TABLE grocer_internal.outbound_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    inbound_id bigint REFERENCES grocer_internal.inbound_messages (id),
    customer_id text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED', 'SENDING', 'SENT', 'UNKNOWN')),
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    sending_started_at timestamptz,
    payment_attempt_id text REFERENCES grocer_internal.checkout_attempts (id),
    CONSTRAINT outbound_messages_v2_inbound_unique UNIQUE (inbound_id)
);

CREATE INDEX outbound_messages_queued_idx
    ON grocer_internal.outbound_messages (id) WHERE status = 'QUEUED';
CREATE INDEX outbound_messages_stale_sending_idx
    ON grocer_internal.outbound_messages (sending_started_at) WHERE status = 'SENDING';
CREATE UNIQUE INDEX outbound_messages_payment_attempt_idx
    ON grocer_internal.outbound_messages (payment_attempt_id) WHERE payment_attempt_id IS NOT NULL;
```

### 6. `checkout_attempts` (Server-Side Gated Checkout Audit)
Audits every order creation attempt, price snapshot, payment checks, and outcome reconciliation.

```sql
CREATE TABLE grocer_internal.checkout_attempts (
    id text PRIMARY KEY,
    customer_id text NOT NULL,
    cart_id text NOT NULL,
    address_id text NOT NULL,
    cart_fingerprint text NOT NULL,
    approved_total numeric(12, 2) NOT NULL CHECK (approved_total > 0),
    currency text NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    status text NOT NULL CHECK (status IN
        ('IN_FLIGHT', 'UNKNOWN', 'PAYMENT_PENDING', 'PARTIAL', 'FAILED',
         'REVIEW_COMPLETE', 'PLACED', 'PAYMENT_FAILED')),
    provider_order_id text,
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    next_payment_check_at timestamptz,
    payment_deadline_at timestamptz
);

CREATE UNIQUE INDEX checkout_attempts_unresolved_customer_idx
    ON grocer_internal.checkout_attempts (customer_id)
    WHERE status IN ('IN_FLIGHT', 'UNKNOWN', 'PAYMENT_PENDING', 'PARTIAL');
CREATE INDEX checkout_attempts_payment_due_idx
    ON grocer_internal.checkout_attempts (next_payment_check_at)
    WHERE status = 'PAYMENT_PENDING';
```

### 7. `task_state` (Encrypted Conversational Session State)
Durable encrypted state store backing multi-turn cart and constraint memory across restarts (30-day retention).

```sql
CREATE TABLE grocer_internal.task_state (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX task_state_expiry_idx
    ON grocer_internal.task_state (updated_at);
```

### 8. `replenishment` (Encrypted Household Cadence & Restock Memory)
Stores encrypted purchase intervals, consented reminder schedules, and pause states.

```sql
CREATE TABLE grocer_internal.replenishment (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    consented_at timestamptz NOT NULL DEFAULT now(),
    paused boolean NOT NULL DEFAULT false,
    next_sync_at timestamptz DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

### 9. `privacy_deletions` (Data Purge Audit Log)
Immutable log of completed data deletion requests ("delete my data") ensuring immediate stop of all background processing.

```sql
CREATE TABLE grocer_internal.privacy_deletions (
    customer_id text PRIMARY KEY,
    requested_at timestamptz NOT NULL DEFAULT now()
);
```

---

## Migration History

Migrations are located in `migrations/` and run sequentially during setup:

| File | Purpose |
|---|---|
| `bootstrap_fresh.sql` | Creates schema `grocer_internal`, `oauth_tokens`, and `oauth_pending_flows` |
| `001_connect_tickets.up.sql` | Adds customer account connection tickets |
| `002_messages.up.sql` | Adds `inbound_messages` and `outbound_messages` tables |
| `003_checkout_attempts.up.sql` | Adds gated checkout audit trail |
| `004_task_state.up.sql` | Adds encrypted multi-turn task state persistence |
| `005_privacy_deletions.up.sql` | Adds data purge audit log for `delete my data` |
| `006_inbound_claimed_at.up.sql` | Adds row locking for inbound message intake |
| `007_outbound_sending_started_at.up.sql` | Adds delivery lock for staged outbound queue |
| `008_payment_followups.up.sql` | Adds automated payment reconciliation tracking |
| `009_replenishment.up.sql` | Adds consented cadence and replenishment storage |

---

## Connection Setup

- **Production**: Configured via the `DATABASE_URL` environment variable pointing to Supabase PostgreSQL pooler.
- **Local Development**: In-memory mock adapter and stores are used when `DATABASE_URL` is omitted.
- **CI / Integration Tests**: Provisions a throwaway PostgreSQL container to test real migration scripts and database transactions.
