# Session Handoff: Grocer WhatsApp Bot

- **Goal**: Fix the Swiggy Instamart catalog stock-check bug (`v.in_stock is None`) in `composite_cart.py` and auto-lock default delivery address so recipe searches (e.g., butter chicken) add items directly to cart without false "out of stock" errors.
- **Changes Completed**:
  - Solved initial "Your Swiggy login has expired" dead-lock by generating 1-tap connect tickets in `backend/agent/engine.py` and `backend/agent/formatters.py`.
  - Mapped Karan's phone number (`918237803170`) to `cust_wa_0b6664ee8fa961926993ac7e` in `.env`, Render, and Supabase Postgres `oauth_tokens`.
  - Proved live Swiggy MCP address and cart retrieval on Render (`rev d6dd7de`).
- **Passing Tests**: 129/129 tests passed locally via `verify.ps1`; all 22 WhatsApp Postgres E2E tests passed green (`pytest backend/tests/test_whatsapp_postgres_e2e.py`); `npm run lint` exited 0.
- **Root Cause Diagnosed**:
  - In `backend/agent/composite_cart.py:100`: `[v for v in product.variants if getattr(v, "in_stock", True)]` treats `v.in_stock = None` as `False`, causing real Swiggy search results (butter, chicken, cream, etc.) to be falsely dropped as "out of stock".
  - In `backend/agent/engine.py` / `session.py`: No default address is auto-selected when `session.address_id` is `None`, causing queries like "which address is selected?" to fall back to old cart turns in conversation history.
- **Next Action**:
  1. In `backend/agent/composite_cart.py:100`, fix the stock check: `[v for v in product.variants if getattr(v, "in_stock", None) is not False and getattr(v, "is_available", None) is not False]`.
  2. Auto-select the first saved address (or `Home`) when `session.address_id` is missing in `execute_preflight` or `manage_basket`.
  3. Add deterministic handler for "which address is selected" so it states the active address name immediately.
  4. Run `.\verify.ps1`, push to `main`, and verify with live butter chicken test turn.
