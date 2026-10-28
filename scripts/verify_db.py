"""Grocer — Database Verification Helper."""
import asyncio
import sys
from pathlib import Path

# Ensure root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import close_db_pool, get_db_pool

EXPECTED_TABLES = {
    "address_coords",
    "approvals",
    "checkouts",
    "inbound_messages",
    "oauth_states",
    "oauth_tokens",
    "schema_migrations",
    "sessions",
    "users",
}

REQUIRED_COLUMNS = {
    "users": {"wa_id", "display_name", "updated_at"},
    "oauth_tokens": {"encrypted_token", "nonce", "expires_at", "refresh_token", "refresh_nonce"},
    "oauth_states": {"state", "verifier", "wa_id", "expires_at"},
    "inbound_messages": {"wa_message_id", "raw_payload", "status"},
    "sessions": {"active_address_id", "budget_cap_paise", "history", "onboarding_state", "onboarding_context"},
    "approvals": {"status", "fingerprint", "to_pay_paise", "address_id", "snapshot", "expires_at"},
    "checkouts": {"swiggy_order_id", "swiggy_order_ids", "notified_milestones", "status", "paas_id"},
    "address_coords": {"address_id", "user_id", "latitude", "longitude"},
}

REQUIRED_INDEXES = {
    "idx_inbound_messages_user_created",
    "idx_approvals_user_created",
    "one_inflight_checkout",
    "users_wa_id_key",
    "inbound_messages_wa_message_id_key",
}


async def verify() -> None:
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            tables = await conn.fetch(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'grocer' ORDER BY table_name;
                """
            )
            names = {row["table_name"] for row in tables}
            print(f"grocer tables ({len(names)}): {sorted(names)}")
            missing = EXPECTED_TABLES - names
            assert not missing, f"Missing tables: {sorted(missing)}"

            for table, required in REQUIRED_COLUMNS.items():
                rows = await conn.fetch(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'grocer' AND table_name = $1;
                    """,
                    table,
                )
                actual = {row["column_name"] for row in rows}
                missing_columns = required - actual
                assert not missing_columns, f"Missing columns in {table}: {sorted(missing_columns)}"

            indexes = await conn.fetch(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'grocer';"
            )
            actual_indexes = {row["indexname"] for row in indexes}
            missing_indexes = REQUIRED_INDEXES - actual_indexes
            assert not missing_indexes, f"Missing indexes: {sorted(missing_indexes)}"

            has_test_db = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = 'grocer_test';"
            )
            has_app_role = await conn.fetchval(
                "SELECT 1 FROM pg_roles WHERE rolname = 'grocer_app';"
            )
            assert has_app_role, "Missing least-privilege role: grocer_app"
            current_role = await conn.fetchval("SELECT current_user;")
            can_create_in_grocer = await conn.fetchval(
                "SELECT has_schema_privilege('grocer_app', 'grocer', 'CREATE');"
            )
            can_write_ledger = await conn.fetchval(
                "SELECT has_table_privilege('grocer_app', 'grocer.schema_migrations', 'INSERT');"
            )
            assert current_role == "grocer_app", (
                f"App queries run as {current_role}, expected grocer_app"
            )
            assert not can_create_in_grocer, "grocer_app must not have CREATE on grocer"
            assert not can_write_ledger, "grocer_app must not write schema_migrations"
            print(f"grocer_test database: {'present' if has_test_db else 'MISSING'}")
            print(
                "Database schema verification PASSED "
                f"({len(names)} tables, columns, indexes, grocer_app role)."
            )
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(verify())
