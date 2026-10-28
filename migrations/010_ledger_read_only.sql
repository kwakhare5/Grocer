-- Grocer v1.0 — Phase 6: restore read-only visibility of the migration ledger

GRANT SELECT ON grocer.schema_migrations TO grocer_app;
