"""End-to-end integration test runner across signed Meta intake, PostgreSQL ordering, agent, and local delivery."""
from __future__ import annotations

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
    test_food_already_at_home_does_not_select_home_delivery_address,
)

from backend.tests.suites.planning_and_orders import (
    test_planning_clarification_reaches_customer_without_false_cart_claim,
    test_hinglish_groceries_search_english_catalog_without_losing_user_items,
)

from backend.tests.suites.cart_and_addresses import (
    test_customer_selects_exact_variants_before_one_cart_write_after_restart,
    test_product_name_used_as_model_pack_hint_does_not_hide_valid_bread,
    test_cart_write_with_failed_readback_never_claims_success_or_retries,
    test_cart_items_unresolved_guarded_message,
    test_changed_live_state_requires_fresh_review_before_selected_cart_write,
    test_customer_changes_request_while_product_choices_are_pending,
    test_basket_read_without_swiggy_token_sends_reconnect_link,
    test_real_mcp_rate_limit_stops_after_one_call_and_tells_customer_to_wait,
    test_search_rate_limit_stops_model_loop_without_retrying_mcp,
    test_address_choice_model_outage_then_retry_resumes_original_whatsapp_request,
    test_retry_preserves_pending_grocery_basket_during_address_disambiguation,
)

from backend.tests.suites.recipe_and_budgets import (
    test_long_recipe_request_uses_one_product_choice_batch,
    test_long_list_checks_every_item_in_paced_batches,
    test_catalog_rate_limit_stops_remaining_search_waves,
    test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage,
    test_missing_requested_item_requires_review_before_checkout,
    test_model_cannot_silently_drop_explicit_shopping_items,
    test_provider_dropped_manage_basket_item_is_named_before_partial_review,
    test_symptom_message_suggests_groceries_without_adding_medicine,
    test_recipe_and_extras_request_texts_with_mock_drop_guard,
)

from backend.tests.suites.replenishment_and_webhooks import (
    test_replayed_signed_webhook_has_one_durable_turn_and_one_reply,
    test_forged_whatsapp_signature_never_enters_inbox,
    test_unreviewed_whatsapp_confirmation_cannot_call_checkout,
    test_delete_my_data_purges_task_state_through_signed_whatsapp,
    test_local_simulator_uses_signed_webhook_and_rejects_customer_impersonation,
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

__all__ = [
    "postgres_pool",
    "configure_e2e_secrets",
    "_webhook",
    "_interactive_webhook",
    "test_valid_confirmation_token_confirms",
    "test_stale_confirmation_token_refused_with_fresh_summary_and_button",
    "test_expired_approval_refused_typed_and_by_button",
    "test_typed_yes_confirms_when_model_check_returns_true_refused_when_false",
    "test_typed_confirm_order_with_no_approval_still_refused",
    "test_price_change_forces_fresh_review_and_old_token_refused",
    "test_missing_known_cart_fingerprint_with_pending_approval_refuses_confirm",
    "test_crashed_turn_recovers_then_later_whatsapp_message_gets_reply",
    "test_greeting_does_not_ask_for_delivery_address_or_use_swiggy",
    "test_show_cart_does_not_demand_an_address",
    "test_food_already_at_home_does_not_select_home_delivery_address",
    "test_planning_clarification_reaches_customer_without_false_cart_claim",
    "test_hinglish_groceries_search_english_catalog_without_losing_user_items",
    "test_customer_selects_exact_variants_before_one_cart_write_after_restart",
    "test_product_name_used_as_model_pack_hint_does_not_hide_valid_bread",
    "test_cart_write_with_failed_readback_never_claims_success_or_retries",
    "test_cart_items_unresolved_guarded_message",
    "test_changed_live_state_requires_fresh_review_before_selected_cart_write",
    "test_customer_changes_request_while_product_choices_are_pending",
    "test_basket_read_without_swiggy_token_sends_reconnect_link",
    "test_real_mcp_rate_limit_stops_after_one_call_and_tells_customer_to_wait",
    "test_search_rate_limit_stops_model_loop_without_retrying_mcp",
    "test_address_choice_model_outage_then_retry_resumes_original_whatsapp_request",
    "test_retry_preserves_pending_grocery_basket_during_address_disambiguation",
    "test_long_recipe_request_uses_one_product_choice_batch",
    "test_long_list_checks_every_item_in_paced_batches",
    "test_catalog_rate_limit_stops_remaining_search_waves",
    "test_real_model_presents_recipe_and_extras_choices_over_whatsapp_path",
    "test_plain_language_rupee_cap_never_becomes_unreviewed_payable_overage",
    "test_missing_requested_item_requires_review_before_checkout",
    "test_recipe_request_cannot_silently_omit_pizza_base",
    "test_model_cannot_silently_drop_explicit_shopping_items",
    "test_provider_dropped_manage_basket_item_is_named_before_partial_review",
    "test_symptom_message_suggests_groceries_without_adding_medicine",
    "test_replayed_signed_webhook_has_one_durable_turn_and_one_reply",
    "test_forged_whatsapp_signature_never_enters_inbox",
    "test_unreviewed_whatsapp_confirmation_cannot_call_checkout",
    "test_delete_my_data_purges_task_state_through_signed_whatsapp",
    "test_local_simulator_uses_signed_webhook_and_rejects_customer_impersonation",
    "test_local_simulator_clear_failure_never_claims_empty_basket",
    "test_unknown_meta_delivery_does_not_freeze_later_customer_message",
    "test_confirmed_whatsapp_checkout_is_reconciled_and_notified_after_restart",
]
