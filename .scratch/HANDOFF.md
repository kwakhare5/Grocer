Goal: score the project, then shrink the write path without losing behaviour. Branch `scorecard` only; `main` and Render unchanged. No order.
Shipped: offline scorecard 31/31; live router eval 40/40 exact (avg 1535ms); write verbs collapsed to add/set/remove/clear; webhook split into turn_read/turn_address/turn_basket/turn_add (whatsapp.py 1,434 -> 926 lines).
Passing: verify.ps1 -Db exit 0 on 2026-10-29 (schema, ruff, 223 tests, Next build); live verb cases 10/10 after three quota retries; `main` is db6a297, branch has 12 commits, nothing pushed.
Next action: the 26-case live scorecard when Groq's token window frees (needs ~100k); then item 4, skipping the second model call. Merge only on Karan's go.
Unproven: scorecard, Add-all/Change taps, address add/delete, OAuth reconnect, reaction on a real handset, live 24h scrub. Checkout stays locked.
