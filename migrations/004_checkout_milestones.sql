-- ==============================================================================
-- Grocer — Gate 2.1: Per-Order Delivery Milestone Latch
-- ==============================================================================

-- One key per order and milestone ("<orderId>:<milestone>"). Split orders have
-- several order ids in one checkout row, and each must notify exactly once.
alter table if exists grocer.checkouts
    add column if not exists notified_milestones jsonb not null default '[]';
