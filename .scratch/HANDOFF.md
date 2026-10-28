Goal: give the project a score, then simplify the write path. Branch `scorecard` only; `main` and Render unchanged. No order.
Shipped on the branch: offline scorecard (31 cases, expects per item) and a live scorer (26 cases against the deployed webhook). No production code changed. `main` is still `db6a297`.
Passing tests: ruff clean; `pytest -m "not live"` -> 220 passed, 20 deselected. Offline score 28/31 = 90.3%.
Next action: fix the three named findings, reach 31/31, then rerun the live 26 when Groq's daily cap resets. Merge only after that.
Unproven: full live scorecard (cap), Add-all/Change taps, address add/delete, OAuth reconnect, reaction on a real handset, live 24h scrub. Checkout stays locked.
