"""Native Google Gemini function-calling tool schema declarations for GROCER."""
from __future__ import annotations

RAW_TOOL_DECLARATIONS = [
    {
        "name": "get_saved_addresses",
        "description": "Fetch saved delivery addresses for the user from Swiggy Instamart. Call this first if you don't know the address_id or need to list available locations.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "select_delivery_address",
        "description": "Switch the active delivery destination. Call get_saved_addresses first to view address IDs, then call this tool when the user requests delivery to a specific location (e.g. Pune, Mumbai, Bangalore). If an active cart exists, this tool preserves and updates the basket for the new location.",
        "parameters": {
            "type": "object",
            "properties": {
                "address_id": {
                    "type": "string",
                    "description": "The target address_id from get_saved_addresses.",
                },
            },
            "required": ["address_id"],
        },
    },
    {
        "name": "create_address",
        "description": "Save a new delivery address to the customer's Swiggy Instamart account. Call this when the customer provides a new address in chat (via text description or GPS location pin).",
        "parameters": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Address label, e.g. 'Home', 'Office', 'Parents House', 'Friend'.",
                },
                "street": {
                    "type": "string",
                    "description": "Street name, building, flat or house number.",
                },
                "area": {
                    "type": "string",
                    "description": "Locality or neighborhood name, e.g. 'Kothrud', 'Baner', 'Hinjewadi', 'Aundh'.",
                },
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Pune', 'Bangalore', 'Mumbai'.",
                },
                "landmark": {
                    "type": "string",
                    "description": "Nearby landmark, e.g. 'Opposite D-Mart'.",
                },
            },
            "required": ["label", "street"],
        },
    },
    {
        "name": "delete_address",
        "description": "Delete an obsolete or unwanted saved delivery address from the customer's Swiggy account.",
        "parameters": {
            "type": "object",
            "properties": {
                "address_id": {
                    "type": "string",
                    "description": "The ID of the address to delete.",
                },
            },
            "required": ["address_id"],
        },
    },
    {
        "name": "get_go_to_items",
        "description": "Fetch the user's frequently ordered / usual grocery items from their Swiggy Instamart history. Call this when the user asks for their 'usuals', 'regular groceries', or 'weekly restock'.",
        "parameters": {
            "type": "object",
            "properties": {
                "address_id": {
                    "type": "string",
                    "description": "The user's Swiggy delivery address ID.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "manage_basket",
        "description": "Manage the Swiggy Instamart basket: add new items (searches catalogue and adds best in-stock matches), remove items (by cart line ID), or adjust quantities (by cart line ID). Updates the basket atomically and returns the fresh cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "address_id": {
                    "type": "string",
                    "description": "The user's Swiggy delivery address ID (optional).",
                },
                "add": {
                    "type": "array",
                    "description": "List of grocery items to search and add to the basket.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Item name to search for (e.g. 'amul butter', 'eggs', 'bread')."},
                            "quantity": {"type": "integer", "description": "Quantity to add (default 1)."},
                            "preferred_pack_size": {"type": "string", "description": "Optional pack size preference (e.g. '500g', '1L', '6 pcs')."},
                        },
                        "required": ["query"],
                    },
                },
                "remove": {
                    "type": "array",
                    "description": "List of cart line IDs to remove from the current basket (e.g. ['SPIN-101']). Each entry must be an exact line ID from the live cart. Do not guess or use item names. If two lines look identical, ask the customer which one to remove.",
                    "items": {"type": "string"},
                },
                "set_quantity": {
                    "type": "array",
                    "description": "List of cart line items to change quantity for by their line ID.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_id": {"type": "string", "description": "The exact cart line ID from the live basket (e.g. 'SPIN-101'). Do not guess or use item names. If two lines look identical, ask the customer which one to change."},
                            "quantity": {"type": "integer", "description": "New target quantity."},
                        },
                        "required": ["line_id", "quantity"],
                    },
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_cart",
        "description": "Fetch current cart contents, item count, formatted line items, subtotal, delivery & packaging fees, and grand total.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "clear_cart",
        "description": "Empty the current Swiggy Instamart cart completely.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_orders",
        "description": "Fetch the customer's recent past Swiggy Instamart orders. Call this when the customer asks what they ordered previously or wants to reorder from past purchases.",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of recent orders to fetch (default: 5).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_order_details",
        "description": "Fetch the itemized breakdown of a past order for inspection or 1-tap reordering.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The Swiggy order ID.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "checkout",
        "description": "Place the Swiggy Instamart order using the customer's selected payment option. NEVER call this unless the user has explicitly confirmed the basket and address.",
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The active cart ID from manage_basket or get_cart.",
                },
                "address_id": {
                    "type": "string",
                    "description": "The user's Swiggy delivery address ID.",
                },
                "payment_method": {
                    "type": "string",
                    "description": "Payment method, default 'UPI'.",
                },
                "payment_option_kind": {
                    "type": "string",
                    "description": "Exact kind of the selected, currently available provider option.",
                },
                "payment_option_id": {
                    "type": "string",
                    "description": "Exact ID of the payment option selected by the user.",
                },
                "is_user_confirmed": {
                    "type": "boolean",
                    "description": "Must be true ONLY when the user has explicitly confirmed the order.",
                },
            },
            "required": ["cart_id", "address_id", "is_user_confirmed"],
        },
    },
    {
        "name": "track_order",
        "description": "Fetch live order tracking status, delivery ETA, and rider details directly on WhatsApp.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The Swiggy order ID to track.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "list_coupons",
        "description": "Fetch available Swiggy Instamart coupons for the active cart.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "apply_coupon",
        "description": "Apply a coupon code to the active cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Coupon promo code, e.g. 'INSTA50'.",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "report_error",
        "description": "Report an issue (missing item, damaged goods, delivery delay) directly to Swiggy customer support.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "string",
                    "description": "Issue type, e.g. 'damaged_item', 'missing_item', 'delivery_delay'.",
                },
                "details": {
                    "type": "string",
                    "description": "Explanation of the issue.",
                },
            },
            "required": ["report_id"],
        },
    },
    {
        "name": "set_budget",
        "description": "Set the customer's maximum spending limit for this order. Call this when the customer mentions a budget, spending limit, or says they only have a certain amount of money.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount_inr": {
                    "type": "number",
                    "description": "Budget amount in Indian Rupees",
                },
            },
            "required": ["amount_inr"],
        },
    },
]
