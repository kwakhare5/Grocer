"""Bounded ReAct turn coordination, tool dispatch execution, and checkout outcome handling."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.agent.checkout_outcome import process_checkout_outcome
from backend.agent.claim_check import build_facts_text, check_reply_claims, extract_product_facts
from backend.agent.formatters import format_cart_receipt
from backend.agent.item_drop_guard import check_for_dropped_items
from backend.agent.product_policy import is_symptom_suggestion_request
from backend.channels.models import (
    InteractiveAction,
    NormalizedIncomingMessage,
    NormalizedOutgoingResponse,
)
from backend.integrations.commerce.models import CommerceCart

logger = logging.getLogger("grocer.agent.react_coordinator")

MAX_TOOL_STEPS = 8
TURN_TIME_LIMIT_SECONDS = 60


def _now() -> float:
    return time.monotonic()


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
    session = engine.get_session(customer_id)
    history = session.history

    saved_request = session.pending_request_text
    extra_context_note = (
        f"Saved unfinished request from earlier: {saved_request}. "
        "If the customer's new message asks to continue or retry, resume it. Otherwise ignore this note."
    ) if saved_request and (saved_request not in incoming_text) else None

    # Append user message
    history.append({
        "role": "user",
        "parts": [{"text": incoming_text}],
        "recorded_at": time.time(),
    })

    final_text = ""
    actions: list[InteractiveAction] = []
    checkout_executed = False
    checkout_result: dict[str, Any] | None = None
    last_cart_receipt: str | None = None
    last_cart_total: float | None = None
    addr_lbl = session.address_label
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
    turn_tool_results: list[dict[str, Any]] = []
    session.current_turn_original_message = planning_request_text or incoming_text or (message.text if message else "")
    basket_step_executed = False
    manage_basket_contents: list[dict[str, Any]] = []

    initial_cart_items = tuple((it.spin_id or it.product_id, it.quantity) for it in current_cart.items) if current_cart else ()
    initial_budget = getattr(session, "budget_inr", None)
    initial_address_id = session.address_id

    start_time = _now()
    for step_idx in range(1, MAX_TOOL_STEPS + 2):
        if step_idx > MAX_TOOL_STEPS or (_now() - start_time > TURN_TIME_LIMIT_SECONDS):
            step_limit_reached = True
            session.pending_request_text = planning_request_text
            break

        if extra_context_note and history:
            model_contents = list(history[:-1])
            last_entry = history[-1]
            if last_entry.get("role") == "user":
                model_contents.append({
                    **last_entry,
                    "parts": [{"text": f"{extra_context_note}\n\n{incoming_text}"}],
                })
            else:
                model_contents.append(last_entry)
        else:
            model_contents = history

        response_data = await engine._call_llm(
            model_contents,
            address_id=address_id,
            address_label=addr_lbl,
            cart=current_cart,
            saved_addresses=getattr(session, "saved_addresses", None),
        )
        if not response_data:
            if last_cart_receipt or checkout_executed:
                final_text = ""
            elif session.pending_request_text or planning_request_text:
                session.pending_request_text = session.pending_request_text or planning_request_text
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

        if not function_calls:
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            response_text = "\n".join(t.strip() for t in text_parts if t.strip())
            if response_text:
                cart_items_now = tuple((it.spin_id or it.product_id, it.quantity) for it in current_cart.items) if current_cart else ()
                state_changed = (
                    (cart_items_now != initial_cart_items)
                    or address_changed
                    or (session.address_id != initial_address_id)
                    or (getattr(session, "budget_inr", None) != initial_budget)
                    or checkout_executed
                    or bool(budget_blocked_items)
                )
                if not state_changed:
                    facts_text = build_facts_text(
                        cart=current_cart,
                        tool_results=turn_tool_results,
                        session_facts=getattr(session, "recent_product_facts", None),
                        address_label=addr_lbl or (session.address_label if session else None),
                    )
                    try:
                        claim = await check_reply_claims(
                            getattr(engine, "gemini", None),
                            response_text,
                            facts_text=facts_text,
                        )
                    except Exception:
                        claim = "unclear"
                    if claim in {"supported", "no_claim"}:
                        final_text = response_text
                    else:
                        if current_cart is None:
                            try:
                                current_cart = await engine.commerce.get_cart()
                            except Exception:
                                current_cart = None
                        if current_cart and current_cart.items:
                            safe_receipt = format_cart_receipt(
                                current_cart, addr_lbl or session.address_label, item_reasons=getattr(session, "item_reasons", None)
                            )
                            final_text = safe_receipt
                            last_cart_receipt = safe_receipt
                        else:
                            final_text = "Your basket is empty. What groceries would you like to add?"
                else:
                    if last_cart_receipt:
                        final_text = ""
                    elif current_cart and current_cart.items:
                        safe_receipt = format_cart_receipt(
                            current_cart, addr_lbl or session.address_label, item_reasons=getattr(session, "item_reasons", None)
                        )
                        final_text = safe_receipt
                        last_cart_receipt = safe_receipt
                    elif address_changed:
                        final_text = f"I've updated your delivery address to *{addr_lbl or session.address_label}*! 📍"
                    else:
                        final_text = "Your basket is empty. What groceries would you like to add?"

                if final_text and final_text.strip():
                    history.append({
                        "role": "model",
                        "parts": [{"text": final_text}],
                        "recorded_at": time.time(),
                    })
                session.pending_request_text = None
                break
            final_text = "I couldn't process that request right now. Please tell me what you'd like to do."
            break

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
            elif suggestion_only and fn_name == "manage_basket":
                suggest_items = fn_args.get("add", [])
                tool_result = await engine.tools.suggest_grocery_items(suggest_items, address_id or "")
            elif suggestion_only and fn_name in {"clear_cart", "checkout"}:
                tool_result = {"success": False, "error": "SUGGESTION_ONLY"}
            else:
                if "address_id" in fn_args and not fn_args["address_id"] and address_id:
                    fn_args["address_id"] = address_id

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

        executed_calls: list[tuple[dict[str, Any], bool, bool, dict[str, Any] | None]] = []
        for call in function_calls:
            try:
                res = await _execute_single_call(call)
                executed_calls.append(res)
                if call.get("name") in ("select_delivery_address", "clear_cart", "manage_basket"):
                    try:
                        current_cart = await engine.commerce.get_cart()
                    except Exception:
                        pass
            except Exception as exc:
                t_name = call.get("name", "unknown")
                logger.warning("Tool execution error for %s: %s", t_name, exc)
                executed_calls.append((
                    {
                        "functionResponse": {
                            "name": t_name,
                            "response": {"name": t_name, "content": {"success": False, "error": "Tool execution failed. Please verify arguments or try another action."}},
                        }
                    },
                    False,
                    False,
                    None,
                ))
        normalized_calls = executed_calls
        for nc in normalized_calls:
            c = nc[0].get("functionResponse", {}).get("response", {}).get("content")
            if isinstance(c, dict):
                turn_tool_results.append(c)
                if session is not None and hasattr(session, "update_product_facts"):
                    prods = extract_product_facts(c)
                    if prods:
                        session.update_product_facts(prods)
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
            return ReactLoopResult(early_response=NormalizedOutgoingResponse(
                recipient_id=message.sender_id, channel=message.channel,
                text=f"Swiggy is limiting requests right now. {wait_text} I'll keep your request.",
                conversation_state="RECOVERING",
            ))

        for ec in executed_calls:
            part = ec[0].get("functionResponse", {})
            result = part.get("response", {}).get("content", {})
            if part.get("name") != "manage_basket" or not isinstance(result, dict):
                continue
            if not suggestion_only and result.get("selection_unavailable_items"):
                unavail = result["selection_unavailable_items"]
                first_query = unavail[0].get("query", "your items")
                logger.warning(
                    "Product selection model unavailable during basket management for %s",
                    [u.get("query") for u in unavail],
                )
                session.pending_request_text = None
                return ReactLoopResult(
                    early_response=NormalizedOutgoingResponse(
                        recipient_id=message.sender_id,
                        channel=message.channel,
                        text=f"Product picking is temporarily unavailable. Would you like me to show the top options for {first_query}?",
                        conversation_state="NEEDS_DECISION",
                    )
                )
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
                    addr_lbl = session.address_label or addr_lbl
            if isinstance(fn_content, dict):
                if fn_content.get("error") in {"INGREDIENT_BUDGET_EXCEEDED", "SCOPED_BUDGET_USE_SEARCH", "CART_ITEMS_UNRESOLVED"}:
                    guarded_change_message = str(fn_content.get("message") or "That change needs another review.")
                if fn_content.get("error") in {"CART_WRITE_UNVERIFIED", "BUDGET_ROLLBACK_UNVERIFIED"}:
                    session.external_cart_pending = True
                    return ReactLoopResult(
                        early_response=NormalizedOutgoingResponse(
                            recipient_id=message.sender_id,
                            channel=message.channel,
                            text="I couldn't verify your basket changes with Swiggy just now. Please review your basket or wait a moment before trying again.",
                            conversation_state="RECOVERING",
                        )
                    )
                if fn_call_name == "manage_basket":
                    basket_step_executed = True
                    if isinstance(fn_content, dict):
                        manage_basket_contents.append(fn_content)
                        for ai in fn_content.get("added_items", []):
                            r = getattr(ai, "reason", None) or (ai.get("reason") if isinstance(ai, dict) else None)
                            name = getattr(ai, "name", None) or (ai.get("name") if isinstance(ai, dict) else str(ai))
                            if r and name and session is not None and hasattr(session, "item_reasons"):
                                session.item_reasons[str(name)] = str(r)
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
            in ("select_delivery_address", "clear_cart", "manage_basket")
            for ec in executed_calls
        ):
            try:
                current_cart = await engine.commerce.get_cart()
            except Exception:
                pass

        if auth_failed:
            auth_resp = await engine._auth_expired_response(message)
            return ReactLoopResult(early_response=auth_resp)

        if last_cart_receipt:
            session.pending_request_text = None
            final_text = ""
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

    if checkout_executed and session is not None and hasattr(session, "clear_product_facts"):
        session.clear_product_facts()

    if basket_step_executed:
        added_names: list[str] = []
        for mb in manage_basket_contents:
            for item in mb.get("added_items", []):
                name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else str(item))
                if name:
                    added_names.append(str(name))
        if current_cart:
            for it in current_cart.items:
                added_names.append(it.name)

        unavailable_names = list(unavailable_items)
        for mb in manage_basket_contents:
            for u in mb.get("unavailable_items", []):
                unavailable_names.append(str(u))

        restricted_names = list(restricted_items)
        for mb in manage_basket_contents:
            for r in mb.get("restricted_items", []):
                restricted_names.append(str(r))

        pending_names: list[str] = []
        for mb in manage_basket_contents:
            for c in mb.get("clarifications_needed", []):
                if isinstance(c, dict) and c.get("query"):
                    pending_names.append(str(c["query"]))
            for s in mb.get("selection_unavailable_items", []):
                if isinstance(s, dict) and s.get("query"):
                    pending_names.append(str(s["query"]))
            for b in mb.get("budget_blocked_items", []):
                pending_names.append(str(b))

        dropped = await check_for_dropped_items(
            getattr(engine, "gemini", None),
            customer_message=session.current_turn_original_message or planning_request_text or incoming_text,
            added_items=list(dict.fromkeys(added_names)),
            unavailable_items=list(dict.fromkeys(unavailable_names)),
            restricted_items=list(dict.fromkeys(restricted_names)),
            pending_items=list(dict.fromkeys(pending_names)),
        )
        if dropped:
            session.dropped_requested_items = list(dropped)
            session.pending_approval = None
            dropped_str = ", ".join(dropped)
            notice = f"I noticed some requested items were not added: {dropped_str}. Please review your basket or tell me what to change."
            guarded_change_message = f"{notice}\n\n{last_cart_receipt}" if last_cart_receipt else notice
            final_text = guarded_change_message
            actions = [InteractiveAction(action_type="button", id="modify_cart", title="Change Items")]
            conv_state = "NEEDS_DECISION"

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
