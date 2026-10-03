ALTER TABLE grocer_internal.checkout_attempts
    ADD COLUMN IF NOT EXISTS next_payment_check_at timestamptz;
ALTER TABLE grocer_internal.checkout_attempts
    ADD COLUMN IF NOT EXISTS payment_deadline_at timestamptz;

CREATE INDEX IF NOT EXISTS checkout_attempts_payment_due_idx
    ON grocer_internal.checkout_attempts (next_payment_check_at)
    WHERE status = 'PAYMENT_PENDING';

ALTER TABLE grocer_internal.outbound_messages
    ADD COLUMN IF NOT EXISTS payment_attempt_id text
        REFERENCES grocer_internal.checkout_attempts (id);

CREATE UNIQUE INDEX IF NOT EXISTS outbound_messages_payment_attempt_idx
    ON grocer_internal.outbound_messages (payment_attempt_id)
    WHERE payment_attempt_id IS NOT NULL;

ALTER TABLE grocer_internal.outbound_messages
    ALTER COLUMN inbound_id DROP NOT NULL;
