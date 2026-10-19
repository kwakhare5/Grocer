-- Migration 011: Composite and performance indexes for message queues and checkout reconciliation

-- 1. Inbound messages: fast lookup by (customer_id, status) and stale lease recovery (status, claimed_at)
CREATE INDEX IF NOT EXISTS inbound_messages_customer_status_id_idx
    ON grocer_internal.inbound_messages (customer_id, status, id);

CREATE INDEX IF NOT EXISTS inbound_messages_stale_processing_idx
    ON grocer_internal.inbound_messages (claimed_at)
    WHERE status = 'PROCESSING';

-- 2. Outbound messages: fast FIFO dispatch (status, id) and stale sending recovery
CREATE INDEX IF NOT EXISTS outbound_messages_customer_status_id_idx
    ON grocer_internal.outbound_messages (customer_id, status, id);

CREATE INDEX IF NOT EXISTS outbound_messages_stale_sending_idx
    ON grocer_internal.outbound_messages (sending_started_at)
    WHERE status = 'SENDING';

-- 3. Checkout attempts: fast customer active checkout lookup
CREATE INDEX IF NOT EXISTS checkout_attempts_customer_status_idx
    ON grocer_internal.checkout_attempts (customer_id, status, created_at DESC);

-- 4. Connect tickets: fast pending customer ticket lookup
CREATE INDEX IF NOT EXISTS connect_tickets_customer_status_idx
    ON grocer_internal.connect_tickets (customer_id, status);
