CREATE TABLE IF NOT EXISTS grocer_internal.checkout_attempts (
    id text PRIMARY KEY,
    customer_id text NOT NULL,
    cart_id text NOT NULL,
    address_id text NOT NULL,
    cart_fingerprint text NOT NULL,
    approved_total numeric(12, 2) NOT NULL CHECK (approved_total > 0),
    currency text NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    status text NOT NULL CHECK (status IN
        ('IN_FLIGHT', 'UNKNOWN', 'PAYMENT_PENDING', 'PARTIAL', 'FAILED',
         'REVIEW_COMPLETE', 'PLACED', 'PAYMENT_FAILED')),
    provider_order_id text,
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS checkout_attempts_unresolved_customer_idx
    ON grocer_internal.checkout_attempts (customer_id)
    WHERE status IN ('IN_FLIGHT', 'UNKNOWN', 'PAYMENT_PENDING', 'PARTIAL');
