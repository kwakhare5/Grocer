# Wallet Advocate & Coupons

Wallet Advocate & Coupons champions the customer's wallet by automatically applying the best valid Swiggy coupon and recommending small staples when adding them saves net fees by unlocking free delivery.

## Sub-features

- `coupon-auto-best`: Evaluate all available Swiggy coupons and apply the one maximizing net savings.
- `coupon-guardrail`: Never apply a coupon if the final payable grand total increases.
- `threshold-nudge`: Proactively suggest 1-2 small staples if crossing a threshold drops high delivery charges.
- `savings-receipt`: Proudly display `Total Saved: ₹...` badge on checkout bills.

## How to get to it (user POV)

- Add groceries to cart reaching or approaching store discount thresholds (e.g., ₹299 or ₹499).
- Inspect the itemized receipt sent back by the bot.
- See coupon discount applied (e.g., `-₹50 [INSTA50]`) and total savings badge highlighted.

## Driving it with Simulator API

Preconditions:

- Grocer server is running at `http://127.0.0.1:8000`.
- Dark store has active coupons available (`list_coupons`).

- **Trigger threshold basket.** Post grocery order near coupon threshold. Run:
  ```powershell
  $body = @{
      sender_id = "wa:+919876543210"
      text = "Add 2 packs olive oil and 1 pack basmati rice"
  } | ConvertTo-Json
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -ContentType "application/json" -Body $body
  ```
  The bot returns a receipt with the best coupon auto-applied and total savings displayed.
- **Inspect discount badge.** Check that response text contains `-₹` under discounts and non-zero `Total Saved: ₹...`.
- **Capture evidence.** Save response JSON to `.scratch/verify-proof/02-coupon-proof.json`.

## Gotchas

- Coupons must never increase final grand total (e.g. dropping below a free-delivery cutoff without adding a staple).
- Only live Swiggy coupons (`list_coupons`) can be applied; zero hardcoded fake promotional codes.
