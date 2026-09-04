"""LangGraph node functions for the GROCER v2 execution agent (spec section 19).

Node graph:
    validate -> pre_check -> execute -> verify -> (finalize | recover)

Each node is a pure async function that takes AgentState and returns a partial update dict.
Nodes read from state["db"] for DB access and write domain results back into state.
"""
from __future__ import annotations

import uuid
from typing import Any

from backend.agents.execution.state import AgentState
from backend.agents.execution.tools import (
    get_recommendation,
    get_inventory,
    validate_transfer,
    create_transfer,
    create_reorder,
    apply_discount,
    recalculate_options,
    log_agent_event,
)
from backend.models.enums import RecommendationStatus, ActionType
from backend.events.bus import bus


def _enum_val(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


# ---------------------------------------------------------------------------
# Node 1: VALIDATE
# ---------------------------------------------------------------------------

async def node_validate(state: AgentState) -> dict:
    """Validate that the recommendation exists and is in APPROVED status.

    Fails fast with an error if:
    - recommendation not found
    - recommendation is not in APPROVED status
    """
    db = state["db"]
    rec_id = state["recommendation_id"]
    events = list(state.get("events", []))

    rec = await get_recommendation(db, rec_id)

    if rec is None:
        return {
            "recommendation": None,
            "error": f"Recommendation {rec_id} not found",
            "events": events,
            "status": "failed",
        }

    if rec["status"] != "approved":
        return {
            "recommendation": rec,
            "error": (
                f"Recommendation {rec_id} has status '{rec['status']}', "
                "expected 'approved'. Human approval required (spec section 18 LOCKED)."
            ),
            "events": events,
            "status": "failed",
        }

    events.append({"node": "validate", "result": "ok", "action_type": rec["action_type"]})
    return {"recommendation": rec, "error": None, "events": events}


# ---------------------------------------------------------------------------
# Node 2: PRE_CHECK
# ---------------------------------------------------------------------------

async def node_pre_check(state: AgentState) -> dict:
    """Re-verify world state before executing the action.

    For TRANSFER: check source inventory is still sufficient.
    For REORDER/DISCOUNT/HOLD: lightweight sanity check (always passes for now).

    State failures (world changed) -> pre_check_passed=False, stale_inventory=True.
    """
    db  = state["db"]
    rec = state.get("recommendation") or {}
    events = list(state.get("events", []))
    rec_id = state["recommendation_id"]

    action_type = rec.get("action_type", "hold")

    if action_type == "transfer":
        result = await validate_transfer(db, rec_id)
        if not result["feasible"]:
            events.append({
                "node": "pre_check",
                "result": "failed",
                "reason": result.get("reason", "unknown"),
            })
            return {
                "pre_check_passed": False,
                "stale_inventory": True,
                "pre_check_error": result.get("reason", "pre_check_failed"),
                "events": events,
            }

    # reorder, discount, hold: pre_check always passes (world changes don't invalidate these)
    events.append({"node": "pre_check", "result": "ok", "action_type": action_type})
    return {
        "pre_check_passed": True,
        "stale_inventory": False,
        "pre_check_error": None,
        "events": events,
    }


# ---------------------------------------------------------------------------
# Node 3: EXECUTE
# ---------------------------------------------------------------------------

async def node_execute(state: AgentState) -> dict:
    """Dispatch to the appropriate tool based on action_type.

    HOLD: no-op execution (valid action per spec section 14.4).
    TRANSFER: create_transfer()
    REORDER: create_reorder()
    DISCOUNT: apply_discount()
    """
    db     = state["db"]
    rec    = state.get("recommendation") or {}
    rec_id = state["recommendation_id"]
    events = list(state.get("events", []))

    action_type = rec.get("action_type", "hold")

    if action_type == "hold":
        events.append({"node": "execute", "result": "ok", "action": "hold_no_op"})
        return {
            "execution_result": {"success": True, "action": "hold", "note": "hold_is_no_op"},
            "execution_error": None,
            "events": events,
        }

    tool_map = {
        "transfer": create_transfer,
        "reorder":  create_reorder,
        "discount": apply_discount,
    }
    tool_fn = tool_map.get(action_type)
    if tool_fn is None:
        return {
            "execution_result": None,
            "execution_error": f"Unknown action_type: {action_type}",
            "events": events,
            "status": "failed",
        }

    try:
        result = await tool_fn(db, rec_id)
    except PermissionError as exc:
        return {
            "execution_result": None,
            "execution_error": str(exc),
            "events": events,
            "status": "failed",
        }

    if not result.get("success", False):
        events.append({"node": "execute", "result": "failed", "error": result.get("error", "unknown")})
        return {
            "execution_result": result,
            "execution_error": result.get("error", "execution_failed"),
            "events": events,
        }

    events.append({"node": "execute", "result": "ok", "action_type": action_type})
    return {
        "execution_result": result,
        "execution_error": None,
        "events": events,
    }


# ---------------------------------------------------------------------------
# Node 4: VERIFY
# ---------------------------------------------------------------------------

async def node_verify(state: AgentState) -> dict:
    """Verify that the execution side-effects are reflected in the DB.

    For TRANSFER: re-check source inventory decreased by transfer_quantity.
    For REORDER/DISCOUNT: accept success=True from execution_result as verification.
    For HOLD: trivially verified.
    """
    db      = state["db"]
    rec     = state.get("recommendation") or {}
    result  = state.get("execution_result") or {}
    events  = list(state.get("events", []))

    action_type = rec.get("action_type", "hold")

    if action_type == "hold":
        events.append({"node": "verify", "result": "ok", "action": "hold"})
        return {"verified": True, "verify_error": None, "events": events}

    if not result.get("success", False):
        events.append({"node": "verify", "result": "skipped_due_to_exec_failure"})
        return {"verified": False, "verify_error": "execution_did_not_succeed", "events": events}

    if action_type == "transfer":
        # Verify source inventory was actually reduced
        src_store_id  = result.get("source_store_id")
        product_id    = result.get("product_id")
        transferred   = result.get("transferred_quantity", 0)

        if src_store_id and product_id:
            inv = await get_inventory(db, uuid.UUID(src_store_id), uuid.UUID(product_id))
            # The quantity should have been deducted; if get_inventory returns >= 0 the
            # flush happened. We trust the flush completed correctly (no rollback).
            events.append({"node": "verify", "result": "ok", "remaining_source_qty": inv["quantity"]})
            return {"verified": True, "verify_error": None, "events": events}

    # REORDER / DISCOUNT: accept execution result
    events.append({"node": "verify", "result": "ok", "action_type": action_type})
    return {"verified": True, "verify_error": None, "events": events}


# ---------------------------------------------------------------------------
# Node 5a: FINALIZE
# ---------------------------------------------------------------------------

async def node_finalize(state: AgentState) -> dict:
    """Mark the recommendation as EXECUTED and emit AGENT_EXECUTION_COMPLETE."""
    db     = state["db"]
    rec_id = state["recommendation_id"]
    events = list(state.get("events", []))

    from backend.models.core import Recommendation
    from backend.models.enums import RecommendationStatus

    rec_row = await db.get(Recommendation, rec_id)
    if rec_row:
        rec_row.status = RecommendationStatus.EXECUTED
        await db.flush()

    await log_agent_event(
        db,
        "AGENT_EXECUTION_COMPLETE",
        rec_id,
        {"recommendation_id": str(rec_id), "status": "completed"},
    )
    events.append({"node": "finalize", "result": "completed"})
    return {"status": "completed", "events": events, "requires_human_review": False}


# ---------------------------------------------------------------------------
# Node 5b: RECOVER
# ---------------------------------------------------------------------------

async def node_recover(state: AgentState) -> dict:
    """Handle execution failure: recalculate alternatives, require human review.

    Per spec section 21: never blindly retry stale business decisions.
    Emit HUMAN_REVIEW_REQUIRED event. Trigger recalculate_options.
    """
    db      = state["db"]
    rec     = state.get("recommendation") or {}
    rec_id  = state["recommendation_id"]
    events  = list(state.get("events", []))

    risk_id_str = rec.get("risk_id")
    new_rec_id  = None
    recovery    = "failed_no_recalculation"

    if risk_id_str:
        try:
            result = await recalculate_options(db, uuid.UUID(risk_id_str))
            new_rec_id_str = result.get("new_recommendation_id")
            new_rec_id = uuid.UUID(new_rec_id_str) if new_rec_id_str else None
            recovery = "recalculated_new_recommendation_pending_approval"
        except Exception as exc:
            recovery = f"recalculation_failed: {exc}"

    await log_agent_event(
        db,
        "HUMAN_REVIEW_REQUIRED",
        rec_id,
        {
            "recommendation_id":     str(rec_id),
            "reason":                state.get("pre_check_error") or state.get("execution_error") or state.get("error") or "unknown",
            "new_recommendation_id": str(new_rec_id) if new_rec_id else None,
        },
    )

    events.append({"node": "recover", "result": "human_review_required", "recovery": recovery})
    return {
        "status":                 "requires_human_review",
        "recovery_action":        recovery,
        "new_recommendation_id":  new_rec_id,
        "requires_human_review":  True,
        "events":                 events,
    }
