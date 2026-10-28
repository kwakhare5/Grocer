-- Grocer — Phase 6: durable PKCE authorization state

CREATE TABLE IF NOT EXISTS grocer.oauth_states (
    state text PRIMARY KEY,
    verifier text NOT NULL,
    wa_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oauth_states_expires
    ON grocer.oauth_states (expires_at);
