"""Bounded ReAct turn coordination, tool dispatch execution, and checkout outcome handling."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.agent.catalog_ranker import _matches_item_name
from backend.agent.checkout_outcome import process_checkout_outcome
from backend.agent.guards import (
    reconcile_explicit_items,
    reconcile_explicit_removals,
)
from backend.agent.product_policy import is_symptom_suggestion_request
from backend.agent.react_loop import (
    build_recipe_repair_prompt,
    is_invalid_item_plan,
    merge_redundant_function_calls,
    validate_cart_edit_calls,
)
from backend.agent.tool_scheduler import execute_tool_calls
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.react_coordinator")


@dataclass
class ReactLoopResult:
    early_response: Optional[NormalizedOutgoingResponse] = None
    final_text: str = ""
    actions: list[InteractiveAction] = field(default_factory=list)
    conv_state: str = "READY"
    last_cart_receipt: Optional[str] = None
    last_cart_total: Optional[float] = None
    out_order_id: Optional[str] = None
    out_order_total: Optional[float] = None
    out_bridge_url: Optional[str] = None
    address_changed: bool = False
    suggestion_only: bool = False
    suggested_items: list[str] = field(default_factory=list)
    restricted_items: list[str] = field(default_factory=list)
    search_failed_items: list[str] = field(default_factory=list)
    budget_blocked_items: list[str] = field(default_factory=list)
    unavailable_items: list[str] = field(default_factory=list)
    reduced_items: list[str] = field(default_factory=list)
    guarded_change_message: Optional[str] = None
    pending_request_needs_retry: bool = False
    step_limit_reached: bool = False
    checkout_executed: bool = False
    user_confirmed: bool = False
    incoming_text: str = ""
    addr_lbl: Optional[str] = None


async def execute_react_turn_loop(
    engine: Any,
    message: NormalizedIncomingMessage,
    customer_id: str,
    *,
    incoming_text: str,
    planning_request_text: str,
    user_confirmed: bool,
    current_cart: Optional[CommerceCart],
    address_id: Optional[str],
) -> ReactLoopResult:
    """Execute the bounded ReAct iteration loop with LLM calls, tool execution, and guardrails."""
    history = engine.get_history(customer_id)
    session = engine.get_session(customer_id)

    # Append user message
    history.append({
        "role": "user",
        "parts": [{"text": incoming_text}],
        "recorded_at": time.time(),
    })

    max_iterations = 3
    final_text = ""
    actions: list[InteractiveAction] = []
    checkout_executed = False
    checkout_result: dict[str, Any] | None = None
    last_cart_receipt: str | None = None
    last_cart_total: float | None = None
    addr_lbl = engine._customer_address_label.get(customer_id)
    address_changed = False
    step_limit_reached = False
    pending_request_needs_retry = False
    suggestion_only = is_symptom_suggestion_request(incoming_text)
    suggested_items: list[str] = []
    restricted_items: list[str] = []
    search_failed_items: list[str] = []
    budget_blocked_items: list[str] = []
    unavailable_items: list[str] = []
    reduced_items: list[str] = []
    guarded_change_message: str | None = None

    legacy_operation = bool(re.search(
        r"\b(?:remove|delete|increase|decrease|reduce|change|switch|replace|swap|update|edit|drop|take\s+out|"
        r"clear|cancel|checkout|confirm|pay|payment|track|usuals?|regulars?|address)\b"
        r"|\b(?:make|set)\s+(?:the\s+)?(?:first|second|third|1st|2nd|3rd|it|that|\w+)\s+(?:to\s+)?(?:\d+|zero|one|two|three|four|five)\b",
        planning_request_text,
        re.IGNORECASE,
    ))
    if not legacy_operation and current_cart and current_cart.items:
        for ci in current_cart.items:
            if _matches_item_name(planning_request_text, ci.name):
                legacy_operation = True
                break
    planning_turn = not user_confirmed and not legacy_operation

    for step_idx in range(1, max_iterations + 1):
        response_data = await engine._call_llm(
            ([{"role": "user", "parts": [{"text": planning_request_text}]}] if planning_turn else history),
            address_id=address_id,
            address_label=addr_lbl,
            cart=current_cart,
            planning_only=planning_turn,
            fast_fail_on_rate_limit=bool(last_cart_receipt or checkout_executed),
        )
        if not response_data:
            if last_cart_receipt or checkout_executed:
                final_text = ""
            elif session.pending_request_text:
                pending_request_needs_retry = True
                final_text = (
                    f"I saved your request: {session.pending_request_text}. "
                    "I couldn't finish building the basket right now. "
                    "Reply *try again* and I'll check the basket before continuing."
                )
            else:
                final_text = "I'm having a brief connection hiccup. Please try again in a moment."
            break

        candidates = response_data.get("candidates", [])
        if not candidates:
            if last_cart_receipt or checkout_executed:
                final_text = ""
            else:
                final_text = "I couldn't process that request right now. Please tell me what you'd like to do."
            break

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if planning_turn and any(call.get("name") == "quick_add_items" for call in function_calls):
            if is_invalid_item_plan(function_calls):
                repair_text = build_recipe_repair_prompt(planning_request_text)
                repaired = await engine._call_llm(
                    [{"role": "user", "parts": [{"text": repair_text}]}],
                    planning_only=True,
                )
                repaired_candidates = repaired.get("candidates", []) if repaired else []
                parts = (
                    repaired_candidates[0].get("content", {}).get("parts", [])
                    if repaired_candidates
                    else []
                )
                function_calls = [p["functionCall"] for p in parts if "functionCall" in p]
                if not any(call.get("name") == "quick_add_items" for call in function_calls) or is_invalid_item_plan(function_calls):
                    session.pending_request_text = planning_request_text
                    return ReactLoopResult(
                        early_response=NormalizedOutgoingResponse(
                            recipient_id=message.sender_id,
                            channel=message.channel,
                            text="I couldn't read every item and quantity safely. I saved your request. Reply *try again* and I'll check it from the start.",
                            conversation_state="NEEDS_DECISION",
                        )
                    )

        if not function_calls:
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            response_text = "\n".join(t.strip() for t in text_parts if t.strip())
            if response_text:
                final_text = response_text
                history.append({
                    "role": "model",
                    "parts": parts,
                    "recorded_at": time.time(),
                })
                break
            if planning_turn:
                session.pending_request_text = planning_request_text
                pending_request_needs_retry = True
                final_text = "I haven't checked Swiggy products yet. Reply *try again* and I'll look up your request."
                break
            final_text = "I couldn't process that request right now. Please tell me what you'd like to do."
            break

        function_calls, parts, _ = merge_redundant_function_calls(function_calls, address_id or "", parts)
        if len(function_calls) > 1 and any(call.get("name") == "quick_add_items" for call in function_calls):
            session.pending_request_text = session.pending_request_text or incoming_text
            return ReactLoopResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I couldn't safely check all those products together. I kept your request. Please tell me which items to check first; no items were added.",
                    conversation_state="NEEDS_DECISION",
                )
            )

        if planning_turn and any(
            call.get("name") not in {
                "quick_add_items", "manage_basket", "get_cart", "search_products",
                "select_delivery_address", "get_saved_addresses", "get_go_to_items", "check_replenishment",
            }
            for call in function_calls
        ):
            session.pending_request_text = planning_request_text
            if any(call.get("name") == "update_cart" for call in function_calls):
                msg = "Please choose an exact product and pack before I add it. I kept your request; nothing was added."
            else:
                msg = "I couldn't plan that grocery request safely; nothing changed. Please tell me what you'd like to do."
            return ReactLoopResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text=msg,
                    conversation_state="NEEDS_DECISION",
                )
            )

        if not validate_cart_edit_calls(function_calls, current_cart, planning_request_text):
            session.pending_request_text = planning_request_text
            return ReactLoopResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text="I couldn't match that cart change to the item or quantity you named. Please name the item and the quantity again; nothing changed.",
                    conversation_state="NEEDS_DECISION",
                )
            )

        history.append({
            "role": "model",
            "parts": parts,
            "recorded_at": time.time(),
        })

        async def _execute_single_call(call: dict[str, Any]) -> tuple[dict[str, Any], bool, bool, dict[str, Any] | None]:
            fn_name = call.get("name")
            fn_args = call.get("args", {})
            call_id = call.get("id")

            if not isinstance(fn_args, dict):
                tool_result = {"success": False, "error": "INVALID_TOOL_ARGUMENTS"}
            elif suggestion_only and fn_name in {"quick_add_items", "manage_basket"}:
                suggest_items = fn_args.get("items", []) if fn_name == "quick_add_items" else fn_args.get("add", [])
                tool_result = await engine.tools.suggest_grocery_items(suggest_items, address_id or "")
            elif suggestion_only and fn_name in {"update_cart", "clear_cart", "checkout"}:
                tool_result = {"success": False, "error": "SUGGESTION_ONLY"}
            else:
                if "address_id" in fn_args and not fn_args["address_id"] and address_id:
                    fn_args["address_id"] = address_id

                explicit_removals = reconcile_explicit_removals(incoming_text)
                if fn_name == "quick_add_items":
                    items = fn_args.get("items", []) if isinstance(fn_args.get("items"), list) else []
                    if explicit_removals:
                        fn_name = "manage_basket"
                        fn_args = {
                            "add": reconcile_explicit_items(incoming_text, items),
                            "remove": explicit_removals,
                        }
                    else:
                        fn_args = {**fn_args, "items": reconcile_explicit_items(incoming_text, items)}
                elif fn_name == "manage_basket":
                    if isinstance(fn_args.get("add"), list):
                        fn_args["add"] = reconcile_explicit_items(incoming_text, fn_args["add"])
                    if explicit_removals:
                        existing_rem = fn_args.get("remove") or []
                        if isinstance(existing_rem, list):
                            fn_args["remove"] = list(set(existing_rem + explicit_removals))
                        else:
                            fn_args["remove"] = explicit_removals

                tool_result = await engine._execute_tool(
                    fn_name,
                    fn_args,
                    customer_id=customer_id,
                    address_id=address_id,
                    user_confirmed=user_confirmed,
                    current_cart=current_cart,
                )

            is_checkout = fn_name == "checkout"
            is_auth_failed = isinstance(tool_result, dict) and tool_result.get("error") == "AUTH_EXPIRED"

            tool_response_part = {
                "functionResponse": {
                    "name": fn_name,
                    "response": {"name": fn_name, "content": tool_result},
                }
            }
            if call_id:
                tool_response_part["functionResponse"]["id"] = call_id
            return tool_response_part, is_auth_failed, is_checkout, (tool_result if is_checkout else None)

        executed_calls = await execute_tool_calls(function_calls, _execute_single_call)
        normalized_calls = [
            ec if isinstance(ec, (tuple, list)) and len(ec) >= 4
            else (
                {"functionResponse": {"name": ec.get("tool", "unknown") if isinstance(ec, dict) else "unknown", "response": {"name": ec.get("tool", "unknown") if isinstance(ec, dict) else "unknown", "content": ec}}}
                if isinstance(ec, dict)
                else {"functionResponse": {"name": "unknown", "response": {"content": str(ec)}}},
                False, False, None,
            )
            for ec in executed_calls
        ]
        tool_responses = [nc[0] for nc in normalized_calls]
        history.append({
            "role": "user",
            "parts": tool_responses,
            "recorded_at": time.time(),
        })

        auth_failed = any(nc[1] for nc in normalized_calls)
        limited_results = [
            nc[0].get("functionResponse", {}).get("response", {}).get("content", {})
            for nc in normalized_calls
        ]
        limited_results = [r for r in limited_results if isinstance(r, dict) and r.get("error") == "RATE_LIMITED"]
        if limited_results:
            session.pending_request_text = session.pending_request_text or incoming_text
            seconds = limited_results[0].get("retry_after_seconds")
            wait_text = (
                f"Please wait {seconds} seconds, then reply *try again*."
                if isinstance(seconds, int)
                else "Please wait, then reply *try again*."
            )
            return ReactLoopResult(
                early_response=NormalizedOutgoingResponse(
                    recipient_id=message.sender_id,
                    channel=message.channel,
                    text=f"Swiggy is limiting requests right now. {wait_text} I'll keep your request.",
                    conversation_state="RECOVERING",
                )
            )

        for ec in executed_calls:
            part = ec[0].get("functionResponse", {})
            result = part.get("response", {}).get("content", {})
            if (
                part.get("name") == "update_cart"
                and isinstance(result, dict)
                and result.get("error") == "VARIANT_SELECTION_REQUIRED"
            ):
                session.pending_request_text = session.pending_request_text or incoming_text
                return ReactLoopResult(
                    early_response=NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text="Please choose an exact product and pack before I add it. I kept your request; nothing was added.",
                        conversation_state="NEEDS_DECISION",
                    )
                )
            if part.get("name") not in ("quick_add_items", "manage_basket") or not isinstance(result, dict):
                continue
            if not suggestion_only and result.get("success") and not result.get("formatted_receipt"):
                missing = result.get("unavailable_items", []) + result.get("restricted_items", [])
                if missing:
                    session.pending_request_text = None
                    return ReactLoopResult(
                        early_response=NormalizedOutgoingResponse(
                            recipient_id=message.sender_id,
                            channel=message.channel,
                            text="I couldn't find eligible products for: " + ", ".join(missing) + ". Nothing was added. Tell me what to try instead.",
                            conversation_state="NEEDS_DECISION",
                        )
                    )

        for ec in executed_calls:
            resp_part = ec[0].get("functionResponse", {})
            fn_call_name = resp_part.get("name")
            fn_content = resp_part.get("response", {}).get("content", {})
            if fn_call_name == "select_delivery_address":
                address_changed = True
                if isinstance(fn_content, dict) and fn_content.get("success"):
                    address_id = fn_content.get("address_id") or address_id
                    addr_lbl = engine._customer_address_label.get(customer_id) or addr_lbl
            if isinstance(fn_content, dict):
                if fn_content.get("error") in {"INGREDIENT_BUDGET_EXCEEDED", "SCOPED_BUDGET_USE_SEARCH"}:
                    guarded_change_message = str(fn_content.get("message") or "That change needs another review.")
                if fn_content.get("error") == "BUDGET_ROLLBACK_UNVERIFIED":
                    session.external_cart_pending = True
                if fn_call_name in ("quick_add_items", "manage_basket"):
                    unavailable_items.extend(str(item) for item in fn_content.get("unavailable_items", []))
                    reduced_items.extend(str(item) for item in fn_content.get("reduced_items", []))
                    restricted_items.extend(str(item) for item in fn_content.get("restricted_items", []))
                    search_failed_items.extend(str(item) for item in fn_content.get("search_failed_items", []))
                    budget_blocked_items.extend(str(item) for item in fn_content.get("budget_blocked_items", []))
                if suggestion_only and fn_content.get("suggestions") is not None:
                    suggested_items.extend(str(item) for item in fn_content["suggestions"])
                if fn_content.get("formatted_receipt"):
                    last_cart_receipt = fn_content["formatted_receipt"]
                if fn_content.get("grand_total") is not None:
                    last_cart_total = float(fn_content["grand_total"])
            if ec[2]:
                checkout_executed = True
                checkout_result = ec[3]

        if any(
            ec[0].get("functionResponse", {}).get("name")
            in ("update_cart", "quick_add_items", "select_delivery_address", "clear_cart")
            for ec in executed_calls
        ):
            try:
                current_cart = await engine.commerce.get_cart()
            except Exception:
                pass

        if auth_failed:
            auth_resp = await engine._auth_expired_response(message)
            return ReactLoopResult(early_response=auth_resp)

        if step_idx == max_iterations:
            step_limit_reached = True

        if last_cart_receipt:
            session.pending_request_text = None
            final_text = ""
            break
        elif planning_turn and step_idx >= max_iterations:
            final_text = "I couldn't finish checking those items. Please tell me which specific item you'd like me to search next."
            session.pending_request_text = planning_request_text
            break

    (
        conv_state,
        final_text,
        actions,
        out_order_id,
        out_order_total,
        out_bridge_url,
    ) = process_checkout_outcome(
        engine,
        customer_id,
        checkout_executed=checkout_executed,
        checkout_result=checkout_result,
        last_cart_receipt=last_cart_receipt,
        current_cart=current_cart,
        addr_lbl=addr_lbl,
        final_text=final_text,
        actions=actions,
        pending_request_needs_retry=pending_request_needs_retry,
    )

    return ReactLoopResult(
        early_response=None,
        final_text=final_text,
        actions=actions,
        conv_state=conv_state,
        last_cart_receipt=last_cart_receipt,
        last_cart_total=last_cart_total,
        out_order_id=out_order_id,
        out_order_total=out_order_total,
        out_bridge_url=out_bridge_url,
        address_changed=address_changed,
        suggestion_only=suggestion_only,
        suggested_items=suggested_items,
        restricted_items=restricted_items,
        search_failed_items=search_failed_items,
        budget_blocked_items=budget_blocked_items,
        unavailable_items=unavailable_items,
        reduced_items=reduced_items,
        guarded_change_message=guarded_change_message,
        pending_request_needs_retry=pending_request_needs_retry,
        step_limit_reached=step_limit_reached,
        checkout_executed=checkout_executed,
        user_confirmed=user_confirmed,
        incoming_text=incoming_text,
        addr_lbl=addr_lbl,
    )
