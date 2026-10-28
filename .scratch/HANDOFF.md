Goal: finish the size-aware basket pass and keep checkout locked. Render env unchanged.
Shipped: simplification branch merged and live on main (code 2c63289, docs b821751). Adds always add/increment; sizes exact; missing items named; explicit set applies; remove/clear confirm; 20 msgs/hour, 10 items, qty 1-99; media reply; DPDP scrub at startup; logs masked; deps pinned.
Passing tests: verify.ps1 -Db exit 0; 146 offline + 73 DB; Next build pass; CI green on 2c63289; Render live with /health 200.
Next action: run the remaining live route wordings (multi-item, eggs, Hinglish, bare "milk", remove) when the shared Groq TPM clears; then phone taps (Add-all, Change, reaction) and address/OAuth proofs. No order.
Unproven: live multi-item/Hinglish wording; beta allowlist (needs Render env + numbers); global daily AI cap; real order, bills/tracking; live 24h scrub. Checkout stays simulated.
