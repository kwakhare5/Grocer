# Swiggy Instamart MCP API Reference

Authoritative technical specification for Swiggy Instamart Model Context Protocol (MCP) tools and JSON-RPC 2.0 integration.

---

## 1. Gateway Endpoint & Authentication

- **Production Gateway URL**: `https://mcp.swiggy.com/im`
- **Protocol**: JSON-RPC 2.0 over HTTPS POST
- **Authentication**: Bearer JWT passed in `Authorization: Bearer <mcp_token>` header
- **Token Validity**: Issued through Swiggy Builders Club OAuth PKCE flow; valid for 7 days.
- **Customer Scoping**: All requests are scoped to a verified customer session. Tokens are stored encrypted at rest via Fernet / AES-GCM in PostgreSQL (`grocer_internal.oauth_tokens`).

---

## 2. Tool Declarations & Schemas

### `get_addresses`
Retrieves customer's saved delivery addresses from Swiggy Instamart.
- **Parameters**:
  - `page` *(optional, int)*: Page number (default: 1)
  - `pageSize` *(optional, int)*: Number of addresses per page (default: 10)
- **Response Fields**:
  - `id`: Address ID
  - `label`: Friendly label (e.g. "Home", "Office")
  - `street`: Street address line
  - `city`: City name (e.g. "Pune")
  - `postal_code`: PIN code
  - `latitude` / `longitude`: Geographic coordinates

### `search_products`
Searches the live catalogue inventory of the local dark store mapped to the specified delivery address.
- **Parameters**:
  - `query` *(required, string)*: Product search term (e.g. "bread", "eggs", "amul milk")
  - `addressId` *(required, string)*: Active delivery address ID
- **Response Structure**:
  - `products`: Array of matching items with SKU-level variants:
    - `spin_id`: Variant unique identifier (mandatory for cart operations)
    - `sku_id`: Stock keeping unit identifier (mandatory for cart operations)
    - `name`: Variant display name
    - `pack_size`: Quantity/size (e.g. "400g", "500ml", "6 pcs")
    - `price`: Effective customer price in ₹
    - `mrp`: Maximum retail price in ₹
    - `in_stock`: Boolean inventory availability flag

### `get_cart`
Fetches current cart items, calculated bill totals, delivery charges, packaging fees, and discounts.
- **Parameters**: None
- **Response Fields**:
  - `cart_id`: Active cart ID
  - `items`: Line items with quantities, unit prices, total prices
  - `item_total`: Subtotal of all items in ₹
  - `delivery_fee`: Provider delivery charge in ₹
  - `packaging_fee`: Packaging / handling fee in ₹
  - `discount`: Applied promotional discount in ₹
  - `grand_total`: Final amount to pay in ₹

### `update_cart`
Adds, updates quantity, or removes items in the Swiggy Instamart cart.
- **Parameters**:
  - `items` *(required, array)*: List of items to update:
    - `spin_id` *(required, string)*
    - `sku_id` *(required, string)*
    - `quantity` *(required, int)*: Setting to 0 removes the item
  - `addressId` *(required, string)*: Active delivery address ID

### `clear_cart`
Removes all items from the active cart.
- **Parameters**: None

### `checkout`
Submits the active basket to place an order.
- **Parameters**:
  - `cartId` *(required, string)*: Active cart ID
  - `addressId` *(required, string)*: Delivery address ID
  - `paymentMethod` *(required, string)*: "UPI" or "cash_on_delivery"
  - `paymentOptionKind` *(string)*: "qr" to generate dynamic UPI QR / payment link
  - `generateUPIQR` *(bool)*: Set to true for UPI intent links
- **Response Fields**:
  - `order_id`: Swiggy order ID
  - `status`: Order status (`PAYMENT_PENDING`, `ORDER_PLACED`, `FAILED`)
  - `grand_total`: Final verified bill total
  - `bridge_url`: Mobile browser bridge URL for completing payment
  - `upi_intent_url`: Deep-link UPI intent URL (`upi://pay?...`)

### `track_order`
Retrieves live order delivery progress, driver assignment, and ETA.
- **Parameters**:
  - `orderId` *(required, string)*: Order ID to track
- **Response Fields**:
  - `order_id`: Order ID
  - `status`: Delivery status (`PACKING`, `RIDER_ASSIGNED`, `OUT_FOR_DELIVERY`, `DELIVERED`)
  - `eta_minutes`: Estimated minutes until delivery
  - `driver_name`: Assigned delivery partner's name
  - `driver_phone`: Masked contact number

---

## 3. Error Classification & Recovery

| Provider Code | Classification | Agent Behavior |
| :--- | :--- | :--- |
| `401` / `AUTH_EXPIRED` | Authentication failure | Prompts customer with re-authentication link (`https://grocerr.vercel.app`) |
| `ITEM_OUT_OF_STOCK` | Inventory shortfall | Suggests nearest in-stock variant conversationally |
| `UNSERVICEABLE` | Delivery location out of range | Informs customer that the chosen address is outside dark store delivery boundaries |
| `PAYMENT_FAILED` | Checkout/UPI payment unsuccessful | Explains failure honestly, preserves cart, provides retry payment link |
