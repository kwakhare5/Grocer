# 1-Tap Mobile UPI Checkout

1-Tap Mobile UPI Checkout enforces deterministic 3-lock checkout safety and delivers clickable `upi://pay` deep links directly inside WhatsApp buttons for 1-tap payment in GPay or PhonePe without LLM interference.

## Sub-features

- `checkout-3-lock-gate`: Validate address, verify cart SHA-256 fingerprint, and enforce explicit customer click before checkout.
- `checkout-fast-dispatcher`: Process button confirmation in Python in <50ms without calling Gemini.
- `checkout-upi-link`: Generate genuine `upi://pay` deep link from live Swiggy gateway without fake VPA fallbacks.
- `checkout-status-poller`: Poll live payment status asynchronously and notify customer on confirmation.

## How to get to it (user POV)

- Customer reviews itemized receipt on WhatsApp and taps the "Confirm Order" button.
- Bot responds in milliseconds with order confirmation and a clickable "Pay with UPI" button.
- Customer taps the button, which opens PhonePe/GPay on their phone to complete payment.

## Driving it with Simulator API

Preconditions:

- Grocer server is running at `http://127.0.0.1:8000`.
- Customer has an active cart with verified approval token.

- **Dispatch confirm order.** Post 1-tap button action. Run:
  ```powershell
  $body = @{
      sender_id = "wa:+919876543210"
      text = "Confirm Order"
      interactive_type = "button_reply"
      interactive_id = "confirm_order"
  } | ConvertTo-Json
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -ContentType "application/json" -Body $body
  ```
  The bot returns order status and dynamic UPI payment action.
- **Inspect payment action.** Check that response text contains order details and interactive actions include `upi://pay` link or payment URL.
- **Capture evidence.** Save response JSON to `.scratch/verify-proof/04-checkout-proof.json`.

## Gotchas

- Python deterministically enforces checkout; Gemini LLM can NEVER place an order or deduct money.
- Hardcoded fake VPAs like `swiggy@icici` are forbidden; only live gateway links are delivered.
- Meta 1024-char body limit must be respected to prevent WhatsApp delivery failure.
