# Conversational Grocery Intake

Conversational Grocery Intake allows customers to text everyday grocery requests, recipes, or multi-item shopping lists in plain English or Hinglish over WhatsApp, receiving an itemized Swiggy Instamart cart with transparent Rupee pricing.

## Sub-features

- `intake-single-item`: Add a single product by name or brand (e.g., "1 packet Amul toned milk").
- `intake-multi-list`: Add multiple items in a single message (e.g., "milk, brown bread, 6 eggs").
- `intake-hinglish`: Parse common Indian staple terms (*doodh, dahi, atta, aloo*).
- `intake-standard-defaults`: Default to the store's #1 standard staple on unqualified requests (500ml milk on "milk").
- `intake-receipt-card`: Render itemized bill with item total, delivery fee, taxes, and coupon savings.

## How to get to it (user POV)

- Open WhatsApp conversation with Grocer concierge.
- Send a natural shopping message (e.g., *"Need 1 pack toned milk and 1 loaf brown bread"*).
- Receive an itemized bill with prices, quantities, and quick reply action buttons.

## Driving it with Simulator API

Preconditions:

- Grocer server is running at `http://127.0.0.1:8000`.
- Health check `http://127.0.0.1:8000/api/health` returns status `"alive"`.
- `SIMULATOR_ENABLED=true` and `SIMULATOR_ACCESS_TOKEN` configured in `.env`.

- **Send grocery list.** Post natural language shopping list. Run:
  ```powershell
  $headers = @{
      "Content-Type" = "application/json"
      "Authorization" = "Bearer grocer-local-simulator-token-16chars"
  }
  $body = @{
      text = "Need 1 pack toned milk and 1 loaf brown bread"
  } | ConvertTo-Json
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -Headers $headers -Body $body
  ```
  The bot returns an itemized bill containing milk and bread with individual Rupee (`₹`) prices.
- **Verify itemization and pricing.** Check that response text contains itemized lines with `₹`, a calculated grand total, and action buttons (`Confirm Order`, `Change Items`).
- **Capture evidence.** Save response JSON and formatted text to `.scratch/verify-proof/01-intake-proof.json`.

## Gotchas

- If an item is completely out of stock, the bot must state it honestly; zero silent drops allowed.
- Unqualified terms like "milk" should pick standard staples, never premium niche alternatives like almond milk.
- Output text must be in strict English even if customer input was in Hinglish.
