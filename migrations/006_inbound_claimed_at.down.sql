DROP INDEX IF EXISTS grocer_internal.inbound_messages_stale_processing_idx;
ALTER TABLE grocer_internal.inbound_messages DROP COLUMN IF EXISTS claimed_at;
