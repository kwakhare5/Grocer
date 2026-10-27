# Grocery Shopping & Concierge

Grocery shopping lets a customer send unstructured grocery lists in Hinglish or English on WhatsApp, receive product matching from Swiggy Instamart dark stores, and review an interactive WhatsApp receipt card with payment buttons. Candidate evaluation still has a rank-1 fallback; Phase 7 removes it.

## Sub-features

- `shop-vague-staple`: resolves vague items like "milk" or "bread" to a named pack size. The `Change items` button has no handler yet, and the auto-pick versus show-choices behavior depends on the model. Phase 7 fixes both.
- `shop-recipe-checklist`: planned for Phase 7, not built. A meal request currently routes to chat or adds a single SKU.
- `shop-conversational-qa`: answers questions about cooking times or ingredients without generating unwanted receipt cards.
- `shop-receipt-dispatch`: dispatches interactive receipt cards with `[Pay: ₹X]` and `[Clear Basket]` buttons.

## How to get to it (user POV)

- Send a WhatsApp text message to Grocer phone number (e.g., "1L Amul Taaza milk", "bread and eggs", "how to make maggi").

## Driving it with scripts/drive_grocer.py

Preconditions:
- Backend server is alive at `http://127.0.0.1:8000`.
- Doctor check passes: `python scripts/drive_grocer.py doctor`.

- **Send grocery list.** Send a grocery text message. Run `python scripts/drive_grocer.py send-text --phone 919876543210 --text "1L Amul Taaza milk and bread"`. Status code 200 is returned.
- **Inspect database recording.** Confirm message ingestion. Run `python scripts/drive_grocer.py inspect-db --phone 919876543210`. The table `grocer.inbound_messages` contains a row with status `'received'`.
- **Conversational Q&A.** Send a question. Run `python scripts/drive_grocer.py send-text --phone 919876543210 --text "what spices do I need for pasta?"`. The message is processed without creating an unwanted approval record.
- **Proof.** Capture DB state to file. Run `python scripts/drive_grocer.py inspect-db --phone 919876543210 > .scratch/verification-proof/shopping_db.txt`.

## Gotchas

- Unauthenticated users receive a "Connect Swiggy" CTA button before grocery items can be added to the live dark-store cart.
- Stale messages (>15 minutes old) are automatically dropped by the webhook shield.
- Natural language "yes" does not trigger checkout; only physical button taps can authorize payments.
