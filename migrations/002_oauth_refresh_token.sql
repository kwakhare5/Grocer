-- ==============================================================================
-- Grocer v1.0 — Gate 1: Refresh Token Vault, Customer Name & Delivery Coordinates
-- ==============================================================================

-- 1. Durable refresh token (AES-256-GCM, rotated on every /auth/token refresh)
alter table if exists grocer.oauth_tokens
    add column if not exists refresh_token bytea,
    add column if not exists refresh_nonce bytea;

-- 2. Customer display name (captured during onboarding for create_address userName)
alter table if exists grocer.users
    add column if not exists display_name text;

-- 3. Delivery pin coordinates (for track_order lat/lng) and onboarding state machine
alter table if exists grocer.sessions
    add column if not exists delivery_latitude double precision,
    add column if not exists delivery_longitude double precision,
    add column if not exists onboarding_state text,
    add column if not exists onboarding_context jsonb;
