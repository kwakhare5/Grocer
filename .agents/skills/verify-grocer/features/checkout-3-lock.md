# 3-Lock Checkout & Payment

3-Lock Checkout protects the customer against accidental purchases, double charges, and price shifts by enforcing physical button taps (Lock 1), live price/stock re-verification (Lock 2), and atomic database CAS transitions (Lock 3).

## Sub-features

- `checkout-lock-1`: rejects text "yes" and requires physical WhatsApp button callback (`pay:<approval_id>`).
- `checkout-lock-2`: re-checks live price and stock; aborts on any payable change because the cart fingerprint includes paise.
- `checkout-lock-3`: executes atomic CAS on `grocer.approvals` preventing double checkout on rapid double-taps.
- `checkout-bridge-url`: delivers an official HTTPS Swiggy payment bridge CTA button.

## How to get to it (user POV)

- Tap the `Pay ₹X` button on a WhatsApp receipt.

## Driving it with scripts/drive_grocer.py

Preconditions:
- Backend server is alive at `http://127.0.0.1:8000`.
- An active approval record exists in `grocer.approvals` with status `'shown'`.

- **Lock 1 rejection test.** Send text "yes". Run `python scripts/drive_grocer.py send-text --phone 919876543210 --text "yes"`. The system treats this as conversational text and never triggers an order.
- **Clear basket button.** Tap "Clear Basket". Run `python scripts/drive_grocer.py send-button --phone 919876543210 --button-id "cart:clear" --title "Clear Basket"`. Response status is `"button_dispatched"` with `"action": "cart:clear"`.
- **Payment authorization.** Tap "Pay". Run `python scripts/drive_grocer.py send-button --phone 919876543210 --button-id "pay:<approval_id>" --title "Pay ₹120"`. This build is locked (`LIVE_CHECKOUT_ENABLED=false`): the tap must return the locked reply and make no Swiggy call. A live order is the owner's post-handoff test; checkout has never been live-tested.
- **Proof.** Confirm approval state transition in DB. Run `python scripts/drive_grocer.py inspect-db --phone 919876543210 > .scratch/verification-proof/checkout_db.txt`.

## Gotchas

- Tap callbacks must arrive within the 10-minute approval TTL window; expired approvals reject payment.
- If total exceeds ₹1,000 launch safety cap, Lock 2 responds with a 1-tap "Raise Limit" button.
- Bridge URLs must use `https://` schemes; `upi://` deep links are strictly blocked.
