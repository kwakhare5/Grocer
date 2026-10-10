"""Diagnostic endpoint for inspecting Render state safely."""
from __future__ import annotations

import hmac
import json
import os
import re
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.channels.whatsapp import default_whatsapp_adapter
from backend.config import settings
from backend.integrations.commerce.token_vault import default_token_vault

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/agent-status")
async def get_agent_status(
    request: Request,
    token: Optional[str] = Query(
        None,
        description="Deprecated: Use Authorization Bearer header or X-Admin-Token header instead",
        deprecated=True,
    ),
    phone: Optional[str] = Query(None, description="Optional customer phone number"),
    customer_id: Optional[str] = Query(None, description="Optional customer ID"),
) -> JSONResponse:
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(status_code=500, detail="Server authorization secret is not configured")

    provided_token = (
        request.headers.get("X-Admin-Token", "").strip()
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or (token or "").strip()
    )
    if not hmac.compare_digest(provided_token, settings.WHATSAPP_APP_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")

    engine = getattr(request.app.state, "agent_engine", None)
    pool = getattr(request.app.state, "database_pool", None)
    revision = os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("VERCEL_GIT_COMMIT_SHA")

    payload: dict[str, Any] = {
        "status": "ok",
        "revision": revision[:12] if revision else None,
        "ai_provider": settings.AI_PROVIDER,
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_fallback_model": settings.GEMINI_FALLBACK_MODEL,
        "last_llm_error": getattr(engine, "last_llm_error", None) if engine else None,
        "last_turn_latency_ms": getattr(engine, "last_turn_latency_ms", None) if engine else None,
        "checkout_mode": settings.CHECKOUT_MODE,
    }

    # Resolve customer if provided
    resolved_customer_id = customer_id
    if not resolved_customer_id and phone:
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            digits = f"91{digits}"
        resolved_customer_id = default_whatsapp_adapter.map_sender_to_customer_id(digits)

    if resolved_customer_id:
        cust_info: dict[str, Any] = {
            "customer_id": resolved_customer_id,
        }
        try:
            token_entry = default_token_vault.get_entry(resolved_customer_id)
            cust_info["has_swiggy_token"] = bool(token_entry and not token_entry.is_expired)
            if token_entry:
                cust_info["token_expires_in_sec"] = max(0, int(token_entry.expires_at - time.time()))

            if engine:
                session = engine.get_session(resolved_customer_id)
                cust_info["address_id"] = engine._customer_address.get(resolved_customer_id)
                cust_info["address_label"] = engine._customer_address_label.get(resolved_customer_id)
                cust_info["order_address_confirmed"] = engine._order_address_confirmed.get(resolved_customer_id, False)
                cust_info["awaiting_address_choice"] = bool(engine._awaiting_address_choice.get(resolved_customer_id))
                cust_info["pending_request_text"] = session.pending_request_text
                cust_info["pending_variant_selection"] = bool(session.pending_variant_selection)
                cust_info["history_turns"] = len(engine.get_history(resolved_customer_id))

                if pool and engine.state_store is not None:
                    persisted = await engine.state_store.load(resolved_customer_id)
                    cust_info["has_persisted_state"] = persisted is not None
                    if persisted:
                        cust_info["persisted_address_id"] = persisted.get("address_id")
                        cust_info["persisted_pending_request"] = persisted.get("pending_request_text")

                if pool:
                    try:
                        rows = await pool.fetch(
                            """SELECT id, status, payload, created_at
                               FROM grocer_internal.outbound_messages
                               WHERE customer_id = $1
                               ORDER BY id DESC LIMIT 5""",
                            resolved_customer_id,
                        )
                        cust_info["recent_outbound"] = [
                            {
                                "id": r["id"],
                                "status": r["status"],
                                "payload": json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
                            }
                            for r in rows
                        ]
                    except Exception as exc_out:
                        cust_info["outbound_error"] = str(exc_out)
        except Exception as exc:
            cust_info["diagnostic_error"] = str(exc)

        payload["customer"] = cust_info

    return JSONResponse(status_code=200, content=payload)
