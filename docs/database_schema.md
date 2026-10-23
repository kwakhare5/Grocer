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

4. **Server-Side Gated Checkout Audit & Hold Tracking**:
   `grocer_internal.checkout_attempts` provides a durable, non-idempotent audit trail for every checkout execution, tracking in-flight reservations and preventing duplicate checkouts.

5. **Automated Payment Followups**:
   `grocer_internal.payment_followups` tracks asynchronous payment status for dynamic UPI checkouts with smart polling limits.

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

### 4. `inbound_messages` (Inbound Webhook Queue)
Durable inbound queue staging customer WhatsApp messages with SHA-256 deduplication and sequential claim leasing.

```sql
CREATE TABLE grocer_internal.inbound_messages (
    id text PRIMARY KEY,
    customer_id text NOT NULL,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    claimed_by text,
    processed_at timestamptz
);

CREATE INDEX inbound_messages_unprocessed_idx
    ON grocer_internal.inbound_messages (received_at)
    WHERE processed_at IS NULL;
```

### 5. `outbound_messages` (Staged Delivery Queue)
Staged outbound responses awaiting transmission to Meta Graph API, supporting rate limiting and network retries.

```sql
CREATE TABLE grocer_internal.outbound_messages (
    id text PRIMARY KEY,
    customer_id text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'PENDING',
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    last_error text,
    sending_started_at timestamptz
);

CREATE INDEX outbound_messages_pending_idx
    ON grocer_internal.outbound_messages (created_at)
    WHERE status = 'PENDING';
```

### 6. `checkout_attempts` (Physical Gated Checkout Audit Trail & Hold Lock)
Durable reservation for non-idempotent Swiggy checkout execution. Locks in-flight checkout attempts to block accidental double-charging.

```sql
CREATE TABLE grocer_internal.checkout_attempts (
    id text PRIMARY KEY,
    customer_id text NOT NULL,
    cart_id text NOT NULL,
    address_id text NOT NULL,
    cart_fingerprint text NOT NULL,
    approved_total numeric(10,2) NOT NULL,
    status text NOT NULL DEFAULT 'IN_FLIGHT',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX checkout_attempts_customer_status_idx
    ON grocer_internal.checkout_attempts (customer_id, status);
```

### 7. `task_state` (Encrypted Multi-Turn Session State)
Fernet-encrypted multi-turn session state preserving customer preferences, budget limits, active cart fingerprint, and conversation state across turns.

```sql
CREATE TABLE grocer_internal.task_state (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX task_state_expiry_idx
    ON grocer_internal.task_state (updated_at);
```

### 8. `payment_followups` (Dynamic UPI Payment Reconciliation)
Tracks pending UPI payments, QR status, and polling intervals for live checkout followups.

```sql
CREATE TABLE grocer_internal.payment_followups (
    id text PRIMARY KEY,
    customer_id text NOT NULL,
    order_id text NOT NULL,
    paas_id text,
    status text NOT NULL DEFAULT 'PENDING',
    created_at timestamptz NOT NULL DEFAULT now(),
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

> **Note on `replenishment` table**: The experimental cadence replenishment table (`grocer_internal.replenishment`) was permanently dropped in migration `010_drop_replenishment.up.sql` to simplify architecture around instant on-demand WhatsApp grocery replenishment (`your_go_to_items`).

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
| `009_replenishment.up.sql` | Initial replenishment storage (deprecated) |
| `010_drop_replenishment.up.sql` | Permanently drops deprecated replenishment table |
| `011_queue_indexes.up.sql` | Adds FIFO performance indexes on inbound & outbound queues |

---

## Connection Setup

- **Production**: Configured via the `DATABASE_URL` environment variable pointing to Supabase PostgreSQL pooler.
- **Local Development**: In-memory mock adapter and stores are used when `DATABASE_URL` is omitted.
- **CI / Integration Tests**: Provisions a throwaway PostgreSQL container to test real migration scripts and database transactions.
