CREATE SCHEMA IF NOT EXISTS grocer_internal;

CREATE TABLE IF NOT EXISTS grocer_internal.inbound_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id text NOT NULL UNIQUE,
    customer_id text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'NEEDS_REVIEW')),
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
);

CREATE INDEX IF NOT EXISTS inbound_messages_pending_idx
    ON grocer_internal.inbound_messages (id) WHERE status = 'PENDING';

-- Existing GROCER deployments use outbound_messages(task_id, source_message_id, ...).
-- Preserve that table and its rows; the durable worker needs a different contract.
DO $$
BEGIN
    IF to_regclass('grocer_internal.outbound_messages') IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'grocer_internal' AND table_name = 'outbound_messages'
              AND column_name = 'task_id'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'grocer_internal' AND table_name = 'outbound_messages'
              AND column_name = 'inbound_id'
        ) THEN
            IF to_regclass('grocer_internal.outbound_messages_legacy') IS NOT NULL THEN
                RAISE EXCEPTION 'Legacy outbound backup table already exists; inspect it before migration';
            END IF;
            ALTER TABLE grocer_internal.outbound_messages RENAME TO outbound_messages_legacy;
        ELSIF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'grocer_internal' AND table_name = 'outbound_messages'
              AND column_name = 'inbound_id'
        ) THEN
            RAISE EXCEPTION 'Unknown outbound_messages schema; migration stopped';
        END IF;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS grocer_internal.outbound_messages (
    id bigint GENERATED ALWAYS AS IDENTITY,
    inbound_id bigint NOT NULL REFERENCES grocer_internal.inbound_messages (id),
    customer_id text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED', 'SENDING', 'SENT', 'UNKNOWN')),
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    CONSTRAINT outbound_messages_v2_pkey PRIMARY KEY (id),
    CONSTRAINT outbound_messages_v2_inbound_unique UNIQUE (inbound_id)
);

CREATE INDEX IF NOT EXISTS outbound_messages_queued_idx
    ON grocer_internal.outbound_messages (id) WHERE status = 'QUEUED';
