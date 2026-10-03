# Review-only rollout and recovery

This is an operator checklist, not evidence that the steps have run. Keep `CHECKOUT_MODE=review` and `LIVE_CHECKOUT_ENABLED=false`. No chargeable order is authorized by this runbook.

## 1. Inspect and back up PostgreSQL

Use the deployed database's approved backup/snapshot mechanism before any migration. Record the current deployment SHA and schema definition privately. On a read-only connection, inspect the existing tables and columns:

```sql
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'grocer_internal'
ORDER BY table_name, ordinal_position;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'grocer_internal'
ORDER BY table_name;
```

The existing `oauth_tokens` table must have `customer_id`, `ciphertext`, `expires_at`, and `updated_at`; `oauth_pending_flows` must have `state_hash`, `ciphertext`, `expires_at`, and `created_at`. Check types and primary keys against `migrations/bootstrap_fresh.sql`. If they differ, stop and prepare a data-preserving migration for that actual schema. Never run `bootstrap_fresh.sql` as a repair against unknown existing tables.

## 2. Apply migrations in order

For a genuinely empty database, run `migrations/bootstrap_fresh.sql` first. Apply `001` through `009` in numeric order in a transaction. On an existing database, inspect the schema and apply only missing migrations in numeric order. Use your normal secure connection method and do not put passwords in command history. The files create connect tickets, inbox/outbox, checkout attempts, task snapshots, privacy deletion requests, recovery timestamps, payment follow-ups, and consented replenishment state.

Verify all nine required tables exist before starting the backend:

```sql
SELECT name, to_regclass('grocer_internal.' || name) AS relation
FROM unnest(ARRAY[
  'oauth_tokens', 'oauth_pending_flows', 'connect_tickets',
  'inbound_messages', 'outbound_messages', 'checkout_attempts',
  'task_state', 'privacy_deletions', 'replenishment'
]) AS name;
```

All `relation` values must be non-null. Also verify `inbound_messages.claimed_at`, `outbound_messages.sending_started_at` and `payment_attempt_id`, `checkout_attempts.next_payment_check_at` and `payment_deadline_at`, and `replenishment.next_sync_at` and `paused`. Table presence alone does not validate all columns or data; run the read-only flow below after startup. Down migrations **drop stored data**. Use the pre-migration backup to restore a populated database; do not run the down files in production as a casual rollback.

## 3. Handle old identities and secrets

Old last-ten-digit customer IDs cannot safely be mapped from their hash alone. Build a verified old-to-new mapping from trusted historical evidence outside the app, check it for collisions, migrate only one-to-one records in a reviewed database transaction, and require everyone else to reconnect through WhatsApp. Do not merge ambiguous records or use the owner token for another customer. A previously committed `bootstrap.vault` file was removed from the working tree; inspect its provenance privately and rotate affected credentials if it held a real token. Do not print or commit its contents.

Set `DATABASE_URL`, a stable Fernet `DATA_ENCRYPTION_KEY`, Meta ingress and delivery secrets, model credentials, Swiggy OAuth client configuration, and the public WhatsApp number in deployment secrets. Do not rotate the encryption key without a decrypt/re-encrypt migration. Confirm `/api/ready` returns HTTP 200 and the expected deployment revision. `/api/health` proves only that the process is alive.

## 4. Verify the review flow without charges

With two distinct verified India WhatsApp numbers and separate Swiggy accounts, check that each connection ticket is single-use and ten-minute bound, each customer sees only their own cart, and `CHECKOUT_MODE=review` makes zero Swiggy checkout calls. Exercise duplicate signed webhook delivery, two messages sent rapidly with a correction, restart after intake, >4,096-character receipt splitting, multiple addresses, changed total, reduced quantity, external cart edit, deletion, and an expired OAuth token. Inspect inbox/outbox status after each case. These steps require the configured real services; the local automated suite has not completed them.

## 5. Triage uncertain work

Inspect `inbound_messages` with `PROCESSING`/`NEEDS_REVIEW`, `outbound_messages` with `SENDING`/`UNKNOWN`, and checkout attempts with `IN_FLIGHT`/`UNKNOWN`/`PAYMENT_PENDING`/`PARTIAL`. Confirm the actual Swiggy/Meta outcome before changing a status or sending a message. Do not replay a shopping action or message merely because the process timed out. Record the provider evidence, customer impact, and final status in the incident record. The current code has bounded payment-status reconciliation, but live checkout remains blocked until its real provider behavior is verified.

## 6. Live-checkout gate

Keep live checkout disabled until PostgreSQL migration and rollback are tested, a complete requested-item ledger and dietary verification are enforced, full payable amount uses exact minor units, payment/order reconciliation survives restart, and two-account real-service review flows pass. Any chargeable smoke order needs separate explicit authorization for that order.
