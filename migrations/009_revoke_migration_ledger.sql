-- Grocer — Phase 6: the app role may read, never write, the migration ledger

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON grocer.schema_migrations FROM grocer_app;
GRANT SELECT ON grocer.schema_migrations TO grocer_app;
