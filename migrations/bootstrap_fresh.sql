-- Fresh installations only. Existing OAuth tables must be inspected and backed up
-- before any schema changes; do not drop them during rollback.
CREATE SCHEMA IF NOT EXISTS grocer_internal;

CREATE TABLE IF NOT EXISTS grocer_internal.oauth_tokens (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    expires_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grocer_internal.oauth_pending_flows (
    state_hash bytea PRIMARY KEY,
    ciphertext bytea NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS oauth_tokens_expires_idx
    ON grocer_internal.oauth_tokens (expires_at);
CREATE INDEX IF NOT EXISTS oauth_pending_flows_expires_idx
    ON grocer_internal.oauth_pending_flows (expires_at);
