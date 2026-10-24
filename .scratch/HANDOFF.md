# Session Handoff: V2 Architectural Reset & Grand Simplification

- **Goal**: Re-architect Grocer from the 25-file defensive pile-up into a clean, 3-pillar native agent pipeline (Gemini Brain + Swiggy MCP + Python Checkout Gate) with zero regexes and zero keyword dictionaries.
- **Current State**:
  - Branch: `feat/architecture-v1` (working tree clean, 101/101 tests passing in 8.04s, ESLint clean).
  - Infrastructure verified live: Supabase PostgreSQL (`db.rxaqlqvhdoiduadikjeb.supabase.co`), Gemini 3.5 models, Swiggy MCP dark store in Sangvi, Pune.
  - Core audit complete: Uncovered why Band-Aids was rejected (prompt bouncer in `prompts.py`), why Late Night Fee broke (6-bucket fee list in `cart_parsers.py`), and cataloged 18 regexes + 3-model policing bureaucracy across 25 agent files.
- **Target Architecture (The Grand Simplification)**:
  1. *Unified Intake*: Reads WhatsApp text/voice/photos/buttons without keyword interceptors.
  2. *Autonomous Gemini Brain*: Directly executes Swiggy MCP tools (`search_products`, `manage_basket`, `select_delivery_address`, `apply_coupon`) without intermediate bouncers or drop guards.
  3. *Deterministic Safety Gate*: Python only latches the final checkout call (User confirmed, Budget met, Store serviceable).
  4. *Outbound & Payment*: WhatsApp interactive cards + crash-proof 15s payment poller.
- **Passing Tests**: 101 passed in 8.04s (`pytest --ignore=backend/tests/test_whatsapp_postgres_e2e.py`).
- **Next Action in Fresh Session**: Deep-dive into the V2 specification, systematically prune obsolete defensive files (`claim_check.py`, `item_drop_guard.py`, `preflight_handler.py`, etc.), and implement the streamlined 3-pillar pipeline.
