CREATE TABLE IF NOT EXISTS grocer_internal.privacy_deletions (
    customer_id text PRIMARY KEY,
    requested_at timestamptz NOT NULL DEFAULT now()
);
