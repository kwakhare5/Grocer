ALTER TABLE grocer_internal.inbound_messages
    ADD COLUMN IF NOT EXISTS claimed_at timestamptz;

-- Existing interrupted turns have no claim timestamp. Treat their intake time as
-- the earliest possible claim time, so the recovery worker can surface them.
UPDATE grocer_internal.inbound_messages
SET claimed_at = received_at
WHERE status = 'PROCESSING' AND claimed_at IS NULL;

CREATE INDEX IF NOT EXISTS inbound_messages_stale_processing_idx
    ON grocer_internal.inbound_messages (claimed_at)
    WHERE status = 'PROCESSING';
