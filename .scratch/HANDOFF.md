Goal: land the light-theme page, then fix the live 5 kg almonds bug. Production main 4ca64a9 (backend a8e530c); rollback db6a297. No order.
Shipped: landing rewrite (light paper, receipt hero, /privacy, /proof), OAuth state-cookie patch parked, post-merge scorecard 25/26 (case 16 still open).
Passing: verify.ps1 -Db exit 0 on 2026-11-01 (148 offline + 75 DB, ruff, Next build); proven OAuth routes restored.
Next action: push the page to main, verify Vercel 200, update STATUS/DESIGN/TASKS to live; then fix live "5 kg almonds" on a short branch with a messy-candidate test and a 5-case live smoke. Then handset proofs.
Unproven: live OAuth reconnect, Add-all/Change taps, reactions, address add/delete, 24h scrub, case 16. Checkout stays locked.
