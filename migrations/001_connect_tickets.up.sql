CREATE SCHEMA IF NOT EXISTS grocer_internal;

CREATE TABLE IF NOT EXISTS grocer_internal.connect_tickets (
    ticket_hash bytea PRIMARY KEY,
    customer_id text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS connect_tickets_expires_idx
    ON grocer_internal.connect_tickets (expires_at);
