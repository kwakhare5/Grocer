ALTER TABLE grocer_internal.outbound_messages
    ALTER COLUMN inbound_id SET NOT NULL;
DROP INDEX IF EXISTS grocer_internal.outbound_messages_payment_attempt_idx;
ALTER TABLE grocer_internal.outbound_messages
    DROP COLUMN IF EXISTS payment_attempt_id;
DROP INDEX IF EXISTS grocer_internal.checkout_attempts_payment_due_idx;
ALTER TABLE grocer_internal.checkout_attempts
    DROP COLUMN IF EXISTS next_payment_check_at;
ALTER TABLE grocer_internal.checkout_attempts
    DROP COLUMN IF EXISTS payment_deadline_at;
