-- Durable task, inbox, and outbox state for GROCER's modular commerce backend.
-- Apply through the deployment migration runner, never from a webhook request.
-- Keep these tables out of Supabase's exposed API schema: only the backend's
-- direct PostgreSQL connection may read or write customer conversation data.

CREATE SCHEMA IF NOT EXISTS grocer_internal;

REVOKE ALL ON SCHEMA grocer_internal FROM PUBLIC;
REVOKE ALL ON SCHEMA grocer_internal FROM anon;
REVOKE ALL ON SCHEMA grocer_internal FROM authenticated;

CREATE TABLE IF NOT EXISTS grocer_internal.shopping_tasks (
    task_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    state TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS shopping_tasks_customer_updated_idx
    ON grocer_internal.shopping_tasks (customer_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS grocer_internal.inbound_events (
    provider TEXT NOT NULL,
    message_id TEXT NOT NULL,
    task_id TEXT NULL REFERENCES grocer_internal.shopping_tasks(task_id),
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (provider, message_id)
);

CREATE INDEX IF NOT EXISTS inbound_events_task_received_idx
    ON grocer_internal.inbound_events (task_id, received_at);

CREATE TABLE IF NOT EXISTS grocer_internal.outbound_messages (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES grocer_internal.shopping_tasks(task_id),
    source_message_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'SENT', 'FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ NULL,
    last_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS outbound_messages_pending_idx
    ON grocer_internal.outbound_messages (created_at)
    WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS grocer_internal.oauth_tokens (
    customer_id TEXT PRIMARY KEY,
    ciphertext BYTEA NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS oauth_tokens_expiry_idx
    ON grocer_internal.oauth_tokens (expires_at);

CREATE TABLE IF NOT EXISTS grocer_internal.oauth_pending_flows (
    state_hash BYTEA PRIMARY KEY,
    ciphertext BYTEA NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS oauth_pending_flows_expiry_idx
    ON grocer_internal.oauth_pending_flows (expires_at);

REVOKE ALL ON ALL TABLES IN SCHEMA grocer_internal FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA grocer_internal FROM anon;
REVOKE ALL ON ALL TABLES IN SCHEMA grocer_internal FROM authenticated;
