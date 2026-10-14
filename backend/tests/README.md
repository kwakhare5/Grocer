# GROCER Backend Test Suite

Comprehensive, zero-skip test battery verifying fast-path invariants, cryptographically signed Meta WhatsApp webhooks, and full PostgreSQL transactional persistence.

## Architecture

To enforce strict modular bounds (every file strictly < 500 lines), tests are structured into two distinct execution tiers:

1. **Deterministic Invariants (`test_invariants.py`)** — 13 tests
   - Pure logic, regex parsers, tool schemas, and 0ms reset command fast-paths.
   - Zero side-effects, zero network, zero database requirements.
   - Execution time: ~0.25 seconds.

2. **WhatsApp PostgreSQL E2E Battery (`test_whatsapp_postgres_e2e.py`)** — 81 tests
   - Full integration across signed incoming webhooks, state machines, Swiggy Instamart catalog matching, and durable database transactions.
   - Modularized across `backend/tests/suites/` to satisfy the `< 500 lines/file` rule:
     - `turn_recovery.py`: Crash recovery, greetings, and cart display.
     - `planning_and_orders.py` & `planning_repairs.py`: Meal-kit decomposition, Hinglish grocery translation, and validation repairs.
     - `cart_and_addresses.py` & `address_disambiguation.py`: Variant selection, rate limit pauses, and multi-address disambiguation.
     - `recipe_and_budgets.py` & `budget_and_symptoms.py`: Rupee caps, ingredient omissions, and medical symptom guards.
     - `replenishment_and_webhooks.py` & `webhook_and_simulator.py`: Webhook replay rejection, replenishment consent, and automated checkout.

## Running Tests

### Standard Run (All 94 tests)
Requires local PostgreSQL (Docker port 5432 or CI container):
```bash
pytest
```
Expected output: **94 passed, 0 skipped, 0 failed**.

### Pure Invariants Only (No database required)
```bash
pytest backend/tests/test_invariants.py
```
Expected output: **13 passed in ~0.25s**.
