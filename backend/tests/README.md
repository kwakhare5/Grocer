# GROCER Backend Test Suite

Comprehensive, zero-skip test battery verifying deterministic intent verification, Swiggy Instamart MCP integration, and full PostgreSQL transactional persistence.

## Architecture

Tests are structured into two distinct execution tiers:

1. **Unit & Integration Suite (Layers 1–4, Invariants & Advocate)** — 88 tests
   - Runs in ~2.6s with zero external database dependencies.
   - Test files:
     - `test_layer1_swiggy_mcp.py` (14 tests): Swiggy MCP client, JSON-RPC HTTP/2, errors, and dark-store tools.
     - `test_layer2_session_intent.py` (11 tests): Postgres task state serialization, cart fingerprinting, address disambiguation, and intent understanding.
     - `test_layer3_basket_orchestrator.py` (11 tests): Product variant ranking, batch item addition, stock truth preservation, and Sangvi principle defaults.
     - `test_layer4_checkout_gate.py` (11 tests): 5-point physical checkout gate, 1-tap mobile UPI links (`upi://pay`), and hold tracking.
     - `test_customer_advocate.py` (5 tests): Wallet championship, auto-coupon selection, and free-delivery suggestions.
     - `test_invariants.py` (26 tests): Core invariants, math validation, and fast-paths.
     - `test_order_messages.py` (7 tests): Code-driven receipt formatting and button generation.
     - `test_two_step_clear_cart.py` (3 tests): Cryptographic 2-step cart clearing.

2. **WhatsApp PostgreSQL E2E Battery (`test_whatsapp_postgres_e2e.py`)** — 71 tests
   - Full integration across signed incoming webhooks, state machines, Swiggy Instamart catalog matching, and durable database transactions.
   - Modularized across `backend/tests/suites/`:
     - `turn_recovery.py`: Crash recovery, greetings, and cart display.
     - `planning_repairs.py`: Meal-kit decomposition and Hinglish grocery translation.
     - `cart_and_addresses.py` & `address_disambiguation.py`: Variant selection and multi-address disambiguation.
     - `recipe_and_budgets.py` & `budget_and_symptoms.py`: Rupee caps and item drop guards.
     - `webhook_and_simulator.py`: Webhook replay rejection, signed HMAC verification, and automated checkout.

## Running Tests

### Unit & Integration Suite (No DB required, 88 tests)
```bash
pytest --ignore=backend/tests/test_whatsapp_postgres_e2e.py
```
Expected output: **88 passed in ~2.6s**.

### Full Test Suite (Requires local PostgreSQL container)
```bash
pytest
```
Expected output: **159 passed, 0 skipped, 0 failed**.
