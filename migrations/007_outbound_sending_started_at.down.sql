DROP INDEX IF EXISTS grocer_internal.outbound_messages_stale_sending_idx;
ALTER TABLE grocer_internal.outbound_messages DROP COLUMN IF EXISTS sending_started_at;
