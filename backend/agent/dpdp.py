"""Grocer v1.0 — DPDP Compliance & 24-Hour Data Minimization (Layer 4).

Enforces:
1. 24-Hour Scrubber: Purges raw inbound WhatsApp payloads, receipt snapshots,
   and dialogue history older than 24 hours.
2. 90-Day Retention: Retains minimal financial audit records while pruning stale messages.
3. Radical Privacy Purge: Explicit 'delete my data' customer command instantly
   wipes OAuth tokens, session history, and anonymizes customer profiles.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("grocer.dpdp")


async def run_24h_dpdp_scrubber(conn_or_pool: Any) -> dict[str, int]:
    """Scrub sensitive customer data older than 24 hours per DPDP compliance.

    1. Nulls out raw_payload in grocer.inbound_messages older than 24h.
    2. Nulls out snapshot in grocer.approvals older than 24h.
    3. Prunes dialogue history from grocer.sessions inactive for >24h.
    4. Purges inbound messages older than 90 days.
    """
    # 1. Scrub inbound message payloads > 24 hours old
    scrubbed_inbound = await conn_or_pool.execute(
        """
        UPDATE grocer.inbound_messages
        SET raw_payload = NULL
        WHERE raw_payload IS NOT NULL
          AND created_at < now() - interval '24 hours';
        """
    )
    inbound_count = int(scrubbed_inbound.split()[-1]) if "UPDATE" in scrubbed_inbound else 0

    # 2. Scrub approval receipt snapshots > 24 hours old
    scrubbed_approvals = await conn_or_pool.execute(
        """
        UPDATE grocer.approvals
        SET snapshot = '{}'::jsonb
        WHERE snapshot != '{}'::jsonb
          AND created_at < now() - interval '24 hours';
        """
    )
    approvals_count = int(scrubbed_approvals.split()[-1]) if "UPDATE" in scrubbed_approvals else 0

    # 3. Prune dialogue history, active address, plan and location from inactive
    # sessions older than 24 hours
    pruned_sessions = await conn_or_pool.execute(
        """
        UPDATE grocer.sessions
        SET history = '[]'::jsonb,
            active_address_id = NULL,
            one_time_destination_id = NULL,
            pending_plan = NULL,
            pending_plan_expires_at = NULL,
            onboarding_state = NULL,
            onboarding_context = NULL,
            delivery_latitude = NULL,
            delivery_longitude = NULL
        WHERE (history != '[]'::jsonb OR active_address_id IS NOT NULL OR one_time_destination_id IS NOT NULL
               OR pending_plan IS NOT NULL OR onboarding_state IS NOT NULL
               OR onboarding_context IS NOT NULL OR delivery_latitude IS NOT NULL
               OR delivery_longitude IS NOT NULL)
          AND last_active_at < now() - interval '24 hours';
        """
    )
    sessions_count = int(pruned_sessions.split()[-1]) if "UPDATE" in pruned_sessions else 0

    # 3b. Geocode cache older than 24 hours is no longer needed for tracking.
    pruned_coords = await conn_or_pool.execute(
        """
        DELETE FROM grocer.address_coords
        WHERE created_at < now() - interval '24 hours';
        """
    )
    coords_count = int(pruned_coords.split()[-1]) if "DELETE" in pruned_coords else 0

    # 4. Scrub customer delivery addresses from 24h approvals and checkouts (DPDP Section 2.10)
    scrubbed_approval_addrs = await conn_or_pool.execute(
        """
        UPDATE grocer.approvals
        SET address_id = 'REDACTED'
        WHERE address_id != 'REDACTED'
          AND created_at < now() - interval '24 hours';
        """
    )
    approval_addrs_count = int(scrubbed_approval_addrs.split()[-1]) if "UPDATE" in scrubbed_approval_addrs else 0

    scrubbed_checkout_addrs = await conn_or_pool.execute(
        """
        UPDATE grocer.checkouts
        SET address_id = 'REDACTED'
        WHERE address_id != 'REDACTED'
          AND created_at < now() - interval '24 hours';
        """
    )
    checkout_addrs_count = int(scrubbed_checkout_addrs.split()[-1]) if "UPDATE" in scrubbed_checkout_addrs else 0

    # 5. Delete old messages beyond 90-day retention
    deleted_old = await conn_or_pool.execute(
        """
        DELETE FROM grocer.inbound_messages
        WHERE created_at < now() - interval '90 days';
        """
    )
    deleted_count = int(deleted_old.split()[-1]) if "DELETE" in deleted_old else 0

    logger.info(
        "DPDP 24h scrubber complete: inbound=%d, approvals=%d, sessions=%d, coords=%d, approval_addrs=%d, checkout_addrs=%d, old_msgs=%d",
        inbound_count,
        approvals_count,
        sessions_count,
        coords_count,
        approval_addrs_count,
        checkout_addrs_count,
        deleted_count,
    )

    return {
        "inbound_scrubbed": inbound_count,
        "approvals_scrubbed": approvals_count,
        "sessions_pruned": sessions_count,
        "coords_pruned": coords_count,
        "approval_addrs_scrubbed": approval_addrs_count,
        "checkout_addrs_scrubbed": checkout_addrs_count,
        "messages_purged_90d": deleted_count,
    }


async def handle_delete_my_data(
    conn_or_pool: Any,
    user_id: str,
) -> dict[str, Any]:
    """Execute immediate 'delete my data' wipe of personal data and Swiggy tokens."""
    # 1. Permanently delete encrypted Swiggy OAuth token
    await conn_or_pool.execute(
        "DELETE FROM grocer.oauth_tokens WHERE user_id = $1;",
        user_id,
    )

    # 2. Delete raw inbound payloads and cached geocodes for this customer
    await conn_or_pool.execute(
        "DELETE FROM grocer.inbound_messages WHERE user_id = $1;",
        user_id,
    )
    await conn_or_pool.execute(
        "DELETE FROM grocer.address_coords WHERE user_id = $1;",
        user_id,
    )

    # 3. Reset customer session, plan and location
    await conn_or_pool.execute(
        """
        UPDATE grocer.sessions
        SET active_address_id = NULL,
            one_time_destination_id = NULL,
            history = '[]'::jsonb,
            pending_plan = NULL,
            pending_plan_expires_at = NULL,
            onboarding_state = NULL,
            onboarding_context = NULL,
            delivery_latitude = NULL,
            delivery_longitude = NULL,
            budget_cap_paise = 100000,
            last_active_at = now()
        WHERE user_id = $1;
        """,
        user_id,
    )

    # 4. Anonymize approval receipt snapshots and redact delivery addresses
    await conn_or_pool.execute(
        "UPDATE grocer.approvals SET snapshot = '{}'::jsonb, address_id = 'REDACTED' WHERE user_id = $1;",
        user_id,
    )
    await conn_or_pool.execute(
        "UPDATE grocer.checkouts SET address_id = 'REDACTED' WHERE user_id = $1;",
        user_id,
    )

    # 5. Remove every personal identifier from the user row. Financial audit
    # rows keep an anonymous user id; messaging again registers a fresh user.
    await conn_or_pool.execute(
        """
        UPDATE grocer.users
        SET wa_id = 'deleted-' || id::text,
            display_name = NULL,
            swiggy_customer_id = NULL,
            updated_at = now()
        WHERE id = $1;
        """,
        user_id,
    )

    logger.info("DPDP 'delete my data' executed for user %s", user_id)

    return {
        "status": "data_deleted",
        "user_id": user_id,
        "message": (
            "Your personal data and Swiggy connection have been permanently deleted from our system. "
            "If you'd like to order groceries in the future, simply send a message and reconnect your account."
        ),
    }
