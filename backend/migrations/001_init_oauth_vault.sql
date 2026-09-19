-- GROCER Encrypted Token & Flow Storage for PostgreSQL
CREATE SCHEMA IF NOT EXISTS grocer_internal;

REVOKE ALL ON SCHEMA grocer_internal FROM PUBLIC;
REVOKE ALL ON SCHEMA grocer_internal FROM anon;
REVOKE ALL ON SCHEMA grocer_internal FROM authenticated;

-- Encrypted Swiggy customer OAuth tokens
CREATE TABLE IF NOT EXISTS grocer_internal.oauth_tokens (
    customer_id TEXT PRIMARY KEY,
    ciphertext BYTEA NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS oauth_tokens_expiry_idx
    ON grocer_internal.oauth_tokens (expires_at);

-- Encrypted PKCE OAuth flow state
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
