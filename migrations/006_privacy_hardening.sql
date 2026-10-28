-- ==============================================================================
-- Grocer v1.0 — Phase 6: Privacy hardening and data guards
-- ==============================================================================

-- 1. updated_at must move on every update, not only when code remembers.
create or replace function grocer.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

do $$
declare
    target text;
begin
    foreach target in array array['users', 'oauth_tokens', 'checkouts'] loop
        if not exists (
            select 1 from pg_trigger
            where tgname = target || '_touch_updated_at'
              and tgrelid = format('grocer.%I', target)::regclass
        ) then
            execute format(
                'create trigger %I before update on grocer.%I '
                'for each row execute function grocer.touch_updated_at();',
                target || '_touch_updated_at',
                target
            );
        end if;
    end loop;
end;
$$;

-- 2. Money and caps can never go negative. NOT VALID keeps old rows untouched
-- while new writes are checked.
alter table grocer.sessions
    drop constraint if exists sessions_budget_cap_positive;
alter table grocer.sessions
    add constraint sessions_budget_cap_positive check (budget_cap_paise > 0) not valid;

alter table grocer.approvals
    drop constraint if exists approvals_to_pay_non_negative;
alter table grocer.approvals
    add constraint approvals_to_pay_non_negative check (to_pay_paise >= 0) not valid;
