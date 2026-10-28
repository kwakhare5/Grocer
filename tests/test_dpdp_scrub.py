"""Grocer v1.0 — 24-hour DPDP scrub with backdated rows (real Postgres)."""

from __future__ import annotations

import json
import uuid

import pytest

from backend.agent.dpdp import run_24h_dpdp_scrubber
from backend.database import get_db_pool


@pytest.mark.db
@pytest.mark.asyncio
async def test_scrub_clears_only_backdated_sessions_and_coords():
    pool = await get_db_pool()
    old_user = await pool.fetchval(
        "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
        f"9197{uuid.uuid4().hex[:8]}",
    )
    fresh_user = await pool.fetchval(
        "INSERT INTO grocer.users (wa_id) VALUES ($1) RETURNING id;",
        f"9196{uuid.uuid4().hex[:8]}",
    )
    expired_state = f"state_{uuid.uuid4().hex}"
    try:
        await pool.execute(
            """
            INSERT INTO grocer.sessions (
                user_id, active_address_id, history, onboarding_state,
                onboarding_context, delivery_latitude, delivery_longitude, last_active_at
            ) VALUES ($1, 'addr_old', $2::jsonb, 'awaiting_pin', $3::jsonb, 12.9, 77.5, now() - interval '25 hours');
            """,
            old_user,
            json.dumps([{"role": "user", "text": "old"}]),
            json.dumps({"city": "Bengaluru"}),
        )
        await pool.execute(
            """
            INSERT INTO grocer.address_coords (user_id, address_id, latitude, longitude, created_at)
            VALUES ($1, 'addr_old', 12.9, 77.5, now() - interval '25 hours');
            """,
            old_user,
        )
        await pool.execute(
            """
            INSERT INTO grocer.sessions (user_id, history, last_active_at)
            VALUES ($1, $2::jsonb, now());
            """,
            fresh_user,
            json.dumps([{"role": "user", "text": "fresh"}]),
        )
        await pool.execute(
            """
            INSERT INTO grocer.address_coords (user_id, address_id, latitude, longitude)
            VALUES ($1, 'addr_fresh', 12.9, 77.5);
            """,
            fresh_user,
        )
        await pool.execute(
            """
            INSERT INTO grocer.oauth_states (state, verifier, wa_id, expires_at)
            VALUES ($1, 'verifier', '919876543210', now() - interval '1 minute');
            """,
            expired_state,
        )

        counts = await run_24h_dpdp_scrubber(pool)

        old_session = await pool.fetchrow(
            """
            SELECT history, active_address_id, onboarding_state, onboarding_context,
                   delivery_latitude, delivery_longitude
            FROM grocer.sessions WHERE user_id = $1;
            """,
            old_user,
        )
        assert json.loads(old_session["history"]) == []
        assert old_session["active_address_id"] is None
        assert old_session["onboarding_state"] is None
        assert old_session["onboarding_context"] is None
        assert old_session["delivery_latitude"] is None
        assert old_session["delivery_longitude"] is None

        fresh_session = await pool.fetchrow(
            "SELECT history FROM grocer.sessions WHERE user_id = $1;", fresh_user
        )
        assert json.loads(fresh_session["history"]) == [{"role": "user", "text": "fresh"}]

        old_coord = await pool.fetchval(
            "SELECT count(*) FROM grocer.address_coords WHERE user_id = $1;", old_user
        )
        fresh_coord = await pool.fetchval(
            "SELECT count(*) FROM grocer.address_coords WHERE user_id = $1;", fresh_user
        )
        assert old_coord == 0
        assert fresh_coord == 1
        assert counts["sessions_pruned"] >= 1
        assert counts["coords_pruned"] >= 1
        assert counts["oauth_states_pruned"] >= 1
        assert (
            await pool.fetchval(
                "SELECT count(*) FROM grocer.oauth_states WHERE state = $1;",
                expired_state,
            )
            == 0
        )
    finally:
        await pool.execute(
            "DELETE FROM grocer.oauth_states WHERE state = $1;", expired_state
        )
        await pool.execute("DELETE FROM grocer.address_coords WHERE user_id = $1;", old_user)
        await pool.execute("DELETE FROM grocer.address_coords WHERE user_id = $1;", fresh_user)
        await pool.execute("DELETE FROM grocer.sessions WHERE user_id = $1;", old_user)
        await pool.execute("DELETE FROM grocer.sessions WHERE user_id = $1;", fresh_user)
        await pool.execute("DELETE FROM grocer.users WHERE id = $1;", old_user)
        await pool.execute("DELETE FROM grocer.users WHERE id = $1;", fresh_user)
