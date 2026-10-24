# Address Management & Dark Store Grounding

Address Management grounds delivery strictly in the customer's real Swiggy address book, supports 1-tap switching between saved locations, and allows creating new addresses directly in chat via text or GPS pin.

## Sub-features

- `address-list-saved`: Retrieve customer's saved Swiggy Instamart addresses (`get_saved_addresses`).
- `address-select-button`: Select delivery location via 1-tap quick buttons (`select_address:<id>`).
- `address-store-sync`: Automatically re-price cart and recalculate fees against the dark store tied to the new location.
- `address-create-pin`: Create and save a new delivery address from text or a WhatsApp GPS location pin.

## How to get to it (user POV)

- Customer asks "Change delivery address" or taps an address choice button on WhatsApp.
- Bot presents saved addresses (e.g., *Home - Bandra West*, *Work - BKC*).
- Customer taps their preferred address; bot confirms and re-grounds catalog inventory and fees.

## Driving it with Simulator API

Preconditions:

- Grocer server is running at `http://127.0.0.1:8000`.
- Customer account has at least one saved address in Swiggy.

- **Request address list.** Send address inquiry. Run:
  ```powershell
  $body = @{
      sender_id = "wa:+919876543210"
      text = "Where are you delivering to?"
  } | ConvertTo-Json
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -ContentType "application/json" -Body $body
  ```
  The bot returns the current delivery location and interactive selection buttons for saved addresses.
- **Select address.** Tap 1-tap address selection button. Run:
  ```powershell
  $selectBody = @{
      sender_id = "wa:+919876543210"
      text = "Home"
      interactive_type = "button_reply"
      interactive_id = "select_address:addr-bandra-1"
  } | ConvertTo-Json
  $selectResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulator/chat" -Method Post -ContentType "application/json" -Body $selectBody
  ```
  The bot returns confirmation that delivery address is updated and dark store cart is synchronized.
- **Capture evidence.** Save response JSON to `.scratch/verify-proof/03-address-proof.json`.

## Gotchas

- Never hardcode city or area names; strictly ground delivery in customer's live Swiggy address book.
- Address change must trigger `update_cart(address_id=...)` to switch dark store inventory immediately.
