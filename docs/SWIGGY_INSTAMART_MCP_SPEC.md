# Swiggy Instamart MCP Specification (v1.0)

> **Authoritative Specification for Swiggy Instamart Model Context Protocol (MCP)**  
> **Source**: Official Swiggy Builders Club (`https://mcp.swiggy.com/builders/docs/`)  
> **Endpoint**: `POST https://mcp.swiggy.com/im`  
> **Protocol**: JSON-RPC 2.0 over HTTPS POST  
> **Auth**: OAuth 2.1 Bearer Token (`Authorization: Bearer <mcp_token>`)  

---

## 1. Core Architecture & Multi-Turn Rules

1. **Server-Side Cart Identity**:
   - Swiggy Instamart cart state is stored server-side, keyed to the customer's authenticated OAuth session.
   - **Never cache the cart in agent memory.** The agent must call `get_cart` at the start of any turn involving cart decisions to observe the true server state.
2. **Address Binding**:
   - An Instamart cart binds directly to the delivery address. Changing delivery address invalidates item stock and pricing.
   - If a customer switches delivery addresses mid-order, the agent must call `clear_cart` before re-adding items for the new address.
3. **Idempotency & Retries**:
   - **Cart Mutations (`update_cart`, `clear_cart`)**: Idempotent. They set absolute cart state (not increments/deltas). Safe to retry on transient network failures.
   - **Order Placement (`checkout`)**: **STRICTLY NON-IDEMPOTENT**. Never blind-retry a failed or timed-out checkout call. On network or 5xx failures:
     1. Wait 2–5 seconds.
     2. Call `get_orders` to check if the order was created server-side.
     3. If the order exists, treat checkout as successful.
     4. If not found, only then prompt the user or re-attempt.
4. **Cancellation Policy**:
   - Swiggy provides **no API tool** to cancel an in-flight Instamart order once placed.
   - If a customer asks to cancel, the agent must respond with the official support instruction:
     > *"To cancel your order, please call Swiggy customer care at 080-67466729."*
5. **Official Branding**:
   - When an order is placed successfully, use the message from the tool response as-is:
     > *"Instamart order placed successfully."*

---

## 2. Complete Inventory of All 20 Instamart Tools

### Stage 1: Discover (5 Tools)

#### `get_addresses`
Retrieves customer's saved delivery addresses from Swiggy Instamart.
- **Parameters**:
  - `page` *(optional, int, default: 1)*: Page number.
  - `pageSize` *(optional, int, default: 10)*: Results per page.
- **Returns**: Array of addresses (`id`, `label`, `street`, `city`, `postal_code`, `lat`, `lng`) with pagination metadata.

#### `search_products`
Searches live dark store inventory for the given address.
- **Parameters**:
  - `query` *(required, string)*: Search keyword (e.g. "milk", "eggs", "bread").
  - `addressId` *(required for signed-in, string)*: Delivery address ID.
  - `latitude` / `longitude` *(optional for guest mode, float)*.
- **Returns**: Array of `products`, each containing SKU variants:
  - `spinId` *(required for cart)*: Variant unique identifier.
  - `skuId` *(required for cart)*: Stock keeping unit identifier.
  - `name`: Product variant name.
  - `pack_size`: Quantity/volume (e.g. "500 ml", "1 kg").
  - `price`: Effective customer price in ₹.
  - `mrp`: Maximum retail price in ₹.
  - `in_stock`: Boolean inventory flag.
  - `similarProducts`: Alternative recommendations if primary search has related items.

#### `your_go_to_items`
Retrieves customer's frequently or recently ordered items for quick replenishment.
- **Parameters**:
  - `addressId` *(required, string)*: Active delivery address ID.
- **Returns**: List of staple items with `spinId`, `skuId`, `name`, `pack_size`, and `price`.

#### `create_address`
Creates a new saved delivery address for the authenticated user.
- **Parameters**:
  - `street` *(required, string)*: Street line / house / flat.
  - `city` *(required, string)*: City name.
  - `postal_code` *(optional, string)*: Postal PIN code.
  - `lat` / `lng` *(optional, float)*: Coordinates (server geocodes if omitted).
  - `label` *(optional, string)*: "Home", "Work", or "Other".

#### `delete_address`
Deletes a saved delivery address for the authenticated user.
- **Parameters**:
  - `addressId` *(required, string)*: Address ID to remove.

---

### Stage 2: Cart (5 Tools)

#### `get_cart`
Fetches current live cart items, fees, discounts, and bill total.
- **Parameters**: None.
- **Returns**:
  - `cart_id`: Active cart ID.
  - `items`: Line items with quantities, unit prices, and line totals.
  - `item_total`: Items subtotal in ₹.
  - `delivery_fee`: Swiggy delivery fee in ₹.
  - `packaging_fee`: Handling and packaging fee in ₹.
  - `discount`: Applied coupon savings in ₹.
  - `grand_total`: Final amount to pay in ₹.

#### `update_cart`
Replaces the entire cart contents with the provided items.
- **Parameters**:
  - `items` *(required, array)*: Array of items:
    - `spinId` *(required, string)*
    - `skuId` *(required, string)*
    - `quantity` *(required, int)*: Setting to 0 removes the item.
  - `selectedAddressId` *(optional for signed-in, string)*: Delivery address ID.
  - `latitude` / `longitude` *(optional for guest mode, float)*.
- **Returns**: Updated cart summary, plus `removedOutOfStockItems` or `reducedQuantityItems` if dark-store stock changed.

#### `clear_cart`
Removes all items from the active cart.
- **Parameters**: None.

#### `list_coupons`
Lists all promotional coupons available for the current cart and delivery address.
- **Parameters**: None.
- **Returns**: Array of eligible coupon codes, minimum order requirements, and discount amounts.

#### `apply_coupon`
Applies a promotional coupon to the active cart.
- **Parameters**:
  - `couponCode` *(required, string)*: Valid coupon code from `list_coupons`.
- **Returns**: Updated cart bill breakdown with discount applied.

---

### Stage 3: Payment (3 Tools)

#### `get_payment_options`
Retrieves live payment methods available for the current cart and address.
- **Parameters**: None (session-scoped).
- **Returns**:
  - `platforms.mobile.methods[]`: UPI app intent options (`gpay://`, `phonepe://`, etc.).
  - `platforms.desktop.methods[]`: Dynamic scan-and-pay UPI QR option (`kind: "qr"`).
  - `cod`: Cash on delivery availability (`is_eligible`).
  - `allMethods[]`: Fallback payment list.

#### `check_payment_status`
Polls payment status for an in-flight UPI payment.
- **Behavior**: **Server Long-Poll (~19 seconds)**. The Swiggy gateway holds the connection open until a payment event occurs or the poll times out.
- **Parameters**:
  - `orderId` *(required, string)*: Swiggy order ID.
  - `paasId` *(required, string)*: Payment gateway transaction ID.
- **Returns**:
  - `status`: `success` | `paid` | `pending` | `failed` | `cancelled` | `cart_changed`.
  - `terminal`: Boolean flag indicating if polling should stop.
  - `confirmed`: Boolean flag indicating if order is finalized.

#### `confirm_order`
Completes order placement after a successful UPI payment if not auto-confirmed.
- **Parameters**:
  - `orderId` *(required, string)*
  - `paasId` *(required, string)*
- **Returns**: Final confirmed order details.

---

### Stage 4: Order (1 Tool)

#### `checkout`
Places the Instamart order and initiates payment.
- **Rules**:
  - Requires explicit user confirmation before execution.
  - `cartId` is NOT a parameter. The user session implicitly identifies the active cart.
- **Parameters**:
  - `addressId` *(required, string)*: Selected delivery address ID.
  - `paymentMethod` *(optional, string)*: `"UPI"`, `"Cash"` / `"COD"`, or `"SwiggyPay"`.
  - `intentApp` *(optional, string)*: UPI app URI for direct mobile intent.
  - `generateUPIQR` *(optional, bool)*: Set to `true` to generate a dynamic UPI scan-and-pay QR code.
  - `confirmDuplicate` *(optional, bool)*: Set `true` ONLY if a previous order was rejected as duplicate and user explicitly re-confirmed.
- **Returns**:
  - `orderId`: Swiggy order ID.
  - `paasId`: Payment gateway transaction ID.
  - `status`: `PAYMENT_PENDING` | `ORDER_PLACED` | `FAILED`.
  - `qr_code_url` / `bridge_url`: UPI payment link or QR asset.

---

### Stage 5: Tracking & History (4 Tools)

#### `track_order`
Real-time tracking for an active in-flight order.
- **Parameters**:
  - `orderId` *(required, string)*
- **Returns**: Delivery status (`PACKING`, `RIDER_ASSIGNED`, `OUT_FOR_DELIVERY`, `DELIVERED`), ETA in minutes, rider name, and masked rider phone.

#### `get_delivery_status`
Lightweight polling endpoint for live packaging and delivery updates.
- **Parameters**:
  - `orderId` *(required, string)*
- **Returns**: `eta_text`, `status_text`, `delivered` (bool), `cancelled` (bool).

#### `get_orders`
Fetches past order history for replenishment analysis.
- **Parameters**:
  - `count` *(optional, int, default: 10)*
  - `active_only` *(optional, bool)*
- **Returns**: Array of past orders with line items, timestamps, and total bills.

#### `get_order_details`
Fetches itemized breakdown of a specific past order.
- **Parameters**:
  - `orderId` *(required, string)*
- **Returns**: Complete receipt lines, prices, and status.

---

### Stage 6: Support (2 Tools)

#### `recommend_address`
Geocodes a free-text address string into coordinates and formatted locality.
- **Parameters**:
  - `addressString` *(required, string)*

#### `report_error`
Generates an error report bundle to share with the Swiggy MCP team.
- **Parameters**:
  - `errorDetails` *(optional, string)*
- **Returns**: Pre-filled diagnostic link and report ID.

---

## 3. Error Handling & Gateway Responses

All tools return a standard JSON envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "human-readable message"
}
```

On failure:

```json
{
  "success": false,
  "error": {
    "message": "Human readable error description",
    "reportId": "ERR-XXXXX",
    "reportHint": "Run report_error to share diagnostics"
  }
}
```

### JSON-RPC Transport Codes
- `-32001`: Authentication expired / unauthorized (trigger OAuth re-auth).
- `-32000`: Rate limited (HTTP 429 - honor `Retry-After` header).
- `-32603`: Upstream internal error (exponential backoff with jitter).
