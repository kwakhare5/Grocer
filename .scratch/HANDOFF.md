Goal: the branch is merged and live. Verify the merged code live, then item 5. Production main a8e530c; rollback db6a297. No order.
Shipped: PR #3 merged fast-forward; Render deploy dep-dbiupgivcj2c73edh5t0 live on a8e530c; /health 200; post-merge smoke basket+addresses 2/2, add milk 1/1; set/remove returned a duplicate-name picker (pre-existing).
Passing: verify.ps1 -Db exit 0 2026-10-31 (148 offline + 75 DB, ruff, build); PR CI green; router 40/40; offline scorecard 31/31; production baseline 25/26 by intent.
Next action: post-merge 26-case scorecard in two runs (1-13, then 14-26 an hour later) against a8e530c; then item 5 on a new branch. Rollback = redeploy db6a297.
Unproven: set/remove with duplicate labels (needs a handset tap), Add-all/Change taps, reactions, live 24h scrub, post-merge scorecard. Checkout stays locked.
