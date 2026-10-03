CREATE TABLE IF NOT EXISTS grocer_internal.replenishment (
    customer_id text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    consented_at timestamptz NOT NULL DEFAULT now(),
    paused boolean NOT NULL DEFAULT false,
    next_sync_at timestamptz DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE grocer_internal.replenishment
    ADD COLUMN IF NOT EXISTS next_sync_at timestamptz DEFAULT now();

ALTER TABLE grocer_internal.replenishment
    ADD COLUMN IF NOT EXISTS paused boolean NOT NULL DEFAULT false;
