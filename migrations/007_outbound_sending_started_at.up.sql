ALTER TABLE grocer_internal.outbound_messages
    ADD COLUMN IF NOT EXISTS sending_started_at timestamptz;

UPDATE grocer_internal.outbound_messages
SET sending_started_at = created_at
WHERE status = 'SENDING' AND sending_started_at IS NULL;

CREATE INDEX IF NOT EXISTS outbound_messages_stale_sending_idx
    ON grocer_internal.outbound_messages (sending_started_at)
    WHERE status = 'SENDING';
