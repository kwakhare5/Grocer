-- ==============================================================================
-- Grocer v1.0 — Gate 1.1: Multi-Store Order IDs & Address Coordinates
-- ==============================================================================

-- 1. Multi-store checkouts return one order per dark store.
alter table if exists grocer.checkouts
    add column if not exists swiggy_order_ids jsonb not null default '[]';

-- 2. Coordinates captured at address creation, used for track_order (lat/lng required).
create table if not exists grocer.address_coords (
    address_id text primary key,
    user_id uuid not null references grocer.users(id) on delete cascade,
    latitude double precision not null,
    longitude double precision not null,
    created_at timestamptz not null default now()
);
