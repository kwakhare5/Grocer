Goal: give the project a score, then simplify the write path. Branch `scorecard` only; `main` and Render unchanged. No order.
Shipped on the branch: offline scorecard (31 cases, 31/31) and a live scorer (26 cases), no keyword lists in candidate selection, and the webhook split into `turn_read`, `turn_address`, `turn_basket`, `turn_add`. `whatsapp.py` 1,434 -> 925 lines.
Passing tests: ruff clean; `pytest -m "not live"` -> 222 passed, 20 deselected, twice back to back. `main` is still `db6a297`.
Next action: rerun the live 26 when Groq's daily cap resets, then the 40-case router eval, then Phase 1 (one write verb set). Merge only on Karan's go.
Unproven: full live scorecard (cap), Add-all/Change taps, address add/delete, OAuth reconnect, reaction on a real handset, live 24h scrub. Checkout stays locked.
