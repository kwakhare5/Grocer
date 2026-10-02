DROP TABLE IF EXISTS grocer_internal.outbound_messages;
DO $$
BEGIN
    IF to_regclass('grocer_internal.outbound_messages_legacy') IS NOT NULL THEN
        ALTER TABLE grocer_internal.outbound_messages_legacy RENAME TO outbound_messages;
    END IF;
END $$;
DROP TABLE IF EXISTS grocer_internal.inbound_messages;
