-- Grocer — Phase 6: least-privilege app role and dead columns

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grocer_app') THEN
        CREATE ROLE grocer_app NOLOGIN;
    END IF;
END
$$;

DO $$
BEGIN
    EXECUTE format('GRANT grocer_app TO %I', current_user);
END
$$;

GRANT USAGE ON SCHEMA grocer TO grocer_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA grocer TO grocer_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA grocer
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO grocer_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA grocer
    GRANT USAGE, SELECT ON SEQUENCES TO grocer_app;

-- Parked feature: never read, only ever set to NULL.
ALTER TABLE grocer.sessions DROP COLUMN IF EXISTS one_time_destination_id;

-- Never written outside tests; customer identity lives on users.id and oauth_tokens.
ALTER TABLE grocer.users DROP COLUMN IF EXISTS swiggy_customer_id;
