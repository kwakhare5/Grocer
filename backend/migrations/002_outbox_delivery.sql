BEGIN;

DELETE FROM grocer_internal.outbound_messages older
USING grocer_internal.outbound_messages newer
WHERE older.task_id = newer.task_id
  AND older.source_message_id = newer.source_message_id
  AND older.id < newer.id;

CREATE UNIQUE INDEX IF NOT EXISTS outbound_messages_source_unique_idx
    ON grocer_internal.outbound_messages (task_id, source_message_id);

COMMIT;
