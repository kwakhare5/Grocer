# Address Management & Onboarding

Address Management lets a customer onboard with a WhatsApp GPS location pin, select delivery locations from saved addresses, send one-time orders to friends or relatives, and prevents accidental address deletion while a delivery is en route.

## Sub-features

- `address-pin-onboarding`: converts cold-start WhatsApp GPS pin into a verified address using Swiggy's two-step `recommend_address` geocoding.
- `address-switch`: clears the active basket when switching delivery locations to prevent dark-store inventory mismatches.
- `address-one-time`: sends groceries to a temporary address and automatically reverts the user session to their home primary address.
- `address-deletion-guard`: blocks address deletion if an active delivery is currently in transit to that address.

## How to get to it (user POV)

- Share a WhatsApp GPS location pin when prompted by Grocer.
- Tap an address quick-reply button or send "deliver to office".

## Driving it with scripts/drive_grocer.py

Preconditions:
- Backend server is alive at `http://127.0.0.1:8000`.
- Doctor check passes: `python scripts/drive_grocer.py doctor`.

- **Send GPS location pin.** Send location pin. Run `python scripts/drive_grocer.py send-location --phone 919876543210 --lat 12.9279 --lng 77.6271`. Webhook responds with `200 OK` and saves coordinates in session state.
- **Inspect DB.** Confirm location recording. Run `python scripts/drive_grocer.py inspect-db --phone 919876543210`. Message type `'location'` is saved in `grocer.inbound_messages`.
- **Proof.** Capture DB state to file. Run `python scripts/drive_grocer.py inspect-db --phone 919876543210 > .scratch/verification-proof/address_db.txt`.

## Gotchas

- GPS location pins without house number require a second-turn prompt asking for flat/door number before dark-store confirmation.
- Active deliveries lock the destination address; address deletion requests for in-flight addresses fail with a safety notice.
