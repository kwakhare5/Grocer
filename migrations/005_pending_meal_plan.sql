-- ==============================================================================
-- Grocer v1.0 — Phase 7: Stored recipe plan awaiting a tap (ADR 0009)
-- ==============================================================================

-- The exact priced plan shown in chat lives here until it is confirmed, a new
-- plan replaces it, or 30 minutes pass. Cleared by DPDP scrub and delete-my-data.
alter table if exists grocer.sessions
    add column if not exists pending_plan jsonb,
    add column if not exists pending_plan_expires_at timestamptz;
