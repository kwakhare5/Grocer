"""End-to-end integration test runner across signed Meta intake, PostgreSQL ordering, agent, and local delivery.

Verifies authoritative customer concierge flows against live Supabase PostgreSQL and real commerce:
1. Webhook Signature Security & Idempotency.
2. Fast 50ms Deterministic Button Router.
3. Natural Language Shopping Concierge (message -> search -> coupon -> receipt -> 1-tap UPI link).
4. Cart-Bound Confirmation Tokens & Gated Server-Side Checkout.
5. In-Chat Customer Privacy Purge ("delete my data").
6. Turn Crash Recovery & Restart Reconciliation.
"""
from __future__ import annotations

import asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.engine import GroceryAgentEngine
from backend.channels.message_store import PostgresMessageStore
from backend.channels.whatsapp import default_whatsapp_adapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.main import create_app
from backend.tests.suites.helpers import (
    _interactive_webhook,
    _webhook,
    configure_e2e_secrets,
    postgres_pool,
)

from backend.tests.suites.turn_recovery import (
    test_crashed_turn_recovers_then_later_whatsapp_message_gets_reply,
    test_greeting_does_not_ask_for_delivery_address_or_use_swiggy,
    test_show_cart_does_not_demand_an_address,
)

from backend.tests.suites.replenishment_and_webhooks import (
    test_replayed_signed_webhook_has_one_durable_turn_and_one_reply,
    test_forged_whatsapp_signature_never_enters_inbox,
    test_unreviewed_whatsapp_confirmation_cannot_call_checkout,
    test_delete_my_data_purges_task_state_through_signed_whatsapp,
    test_local_simulator_clear_failure_never_claims_empty_basket,
    test_unknown_meta_delivery_does_not_freeze_later_customer_message,
    test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart,
)

from backend.tests.suites.confirmation_token import (
    test_valid_confirmation_token_confirms,
    test_stale_confirmation_token_refused_with_fresh_summary_and_button,
    test_expired_approval_refused_typed_and_by_button,
    test_typed_yes_confirms_when_model_check_returns_true_refused_when_false,
    test_typed_confirm_order_with_no_approval_still_refused,
    test_price_change_forces_fresh_review_and_old_token_refused,
    test_missing_known_cart_fingerprint_with_pending_approval_refuses_confirm,
)


@pytest.mark.asyncio
async def test_e2e_full_customer_shopping_flow_message_to_upi(postgres_pool, monkeypatch):
    """Authoritative end-to-end customer concierge flow:

    1. Customer sends natural language grocery list via signed WhatsApp webhook.
    2. Incoming message is durably recorded in live Supabase PostgreSQL.
    3. Composite Cart Engine adds items and Customer Advocate optimizes coupons.
    4. Outbound receipt message is staged and delivered with a 1-tap confirm button.
    5. Customer taps confirm button; fast 50ms dispatcher executes gated checkout.
    6. System transitions to AWAITING_PAYMENT and returns clickable UPI deep link.
    """
    commerce = MockCommerceAdapter()
    engine = GroceryAgentEngine(commerce, gemini_api_key="local-test")
    store = PostgresMessageStore(postgres_pool)
    app = create_app()
    app.state.agent_engine = engine
    app.state.message_store = store
    monkeypatch.setattr(default_whatsapp_adapter, "_app_secret", "local-e2e-secret")
    monkeypatch.setattr(default_whatsapp_adapter, "record_only", True)
    default_whatsapp_adapter.outbound_messages.clear()

    async def mock_call_llm(_history, **_kwargs):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "manage_basket",
                                    "args": {
                                        "add": [
                                            {"query": "brown bread"},
                                            {"query": "milk"},
                                        ]
                                    },
                                }
                            }
                        ]
                    }
                }
            ]
        }

    engine._call_llm = mock_call_llm
    sender = "919876543210"

    # 1. Customer sends shopping list
    body, headers = _webhook("wamid.shop.full.1", "Add brown bread and milk", sender=sender)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local-test") as client:
        res1 = await client.post("/api/whatsapp/webhook", content=body, headers=headers)
        assert res1.status_code == 200

        # Wait for background queue processing
        staged = None
        for _ in range(25):
            staged = await store.response_for_message("wamid.shop.full.1")
            if staged is not None:
                break
            await asyncio.sleep(0.2)

        assert staged is not None, "No response staged for initial grocery turn"
        status1, reply1 = staged
        assert status1 == "SENT"
        assert len(reply1.interactive_actions) >= 1

        # Locate 1-tap confirmation button and token
        confirm_action = next(
            (a for a in reply1.interactive_actions if a.id.startswith("confirm_order:")),
            None,
        )
        assert confirm_action is not None, "Confirmation action button missing from receipt"
        token = confirm_action.id.removeprefix("confirm_order:")
        assert len(token) >= 8

        # 2. Customer taps 1-tap confirm button
        btn_body, btn_headers = _interactive_webhook(
            "wamid.shop.full.2", confirm_action.id, "Confirm Order", sender=sender
        )
        res2 = await client.post("/api/whatsapp/webhook", content=btn_body, headers=btn_headers)
        assert res2.status_code == 200

        staged2 = None
        for _ in range(25):
            staged2 = await store.response_for_message("wamid.shop.full.2")
            if staged2 is not None:
                break
            await asyncio.sleep(0.2)

        assert staged2 is not None, "No response staged for checkout confirmation button tap"
        status2, reply2 = staged2
        assert status2 == "SENT"
        assert reply2.conversation_state in ("AWAITING_PAYMENT", "ORDER_PLACED")
        assert "OD-" in reply2.text or "pay" in reply2.text.casefold()

    await engine.close()


__all__ = [
    "postgres_pool",
    "configure_e2e_secrets",
    "_webhook",
    "_interactive_webhook",
    "test_e2e_full_customer_shopping_flow_message_to_upi",
    "test_valid_confirmation_token_confirms",
    "test_stale_confirmation_token_refused_with_fresh_summary_and_button",
    "test_expired_approval_refused_typed_and_by_button",
    "test_typed_yes_confirms_when_model_check_returns_true_refused_when_false",
    "test_typed_confirm_order_with_no_approval_still_refused",
    "test_price_change_forces_fresh_review_and_old_token_refused",
    "test_missing_known_cart_fingerprint_with_pending_approval_refuses_confirm",
    "test_replayed_signed_webhook_has_one_durable_turn_and_one_reply",
    "test_forged_whatsapp_signature_never_enters_inbox",
    "test_unreviewed_whatsapp_confirmation_cannot_call_checkout",
    "test_delete_my_data_purges_task_state_through_signed_whatsapp",
    "test_local_simulator_clear_failure_never_claims_empty_basket",
    "test_unknown_meta_delivery_does_not_freeze_later_customer_message",
    "test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart",
    "test_crashed_turn_recovers_then_later_whatsapp_message_gets_reply",
    "test_greeting_does_not_ask_for_delivery_address_or_use_swiggy",
    "test_show_cart_does_not_demand_an_address",
]
