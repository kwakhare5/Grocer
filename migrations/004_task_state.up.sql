CREATE TABLE IF NOT EXISTS grocer_internal.task_state (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS task_state_expiry_idx
    ON grocer_internal.task_state (updated_at);
