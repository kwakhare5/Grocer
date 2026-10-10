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
        "name": "quick_add_items",
        "description": "Search for grocery items and prepare exact product, pack-size and price choices for the customer. Does not change the basket; the customer must choose one listed variant per item first.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of grocery items to search and present for customer choice.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Item name to search for (e.g. 'amul milk', 'eggs', 'bread')."},
                            "quantity": {"type": "integer", "description": "Quantity to add (default 1)."},
                            "preferred_pack_size": {"type": "string", "description": "Optional pack size preference (e.g. '500ml', '1L', '6 pcs', '12 pcs')."},
                        },
                        "required": ["query"],
                    },
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "manage_basket",
        "description": "Manage the Swiggy Instamart basket: add new items (searches catalogue and adds best in-stock matches), remove items (by name or query), or adjust quantities. Updates the basket atomically and returns the fresh cart.",
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
                    "description": "List of product names or keywords to remove from the current basket (e.g. ['bread']).",
                    "items": {"type": "string"},
                },
                "set_quantity": {
                    "type": "array",
                    "description": "List of items in the basket to change quantity for.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Name or keyword of the item in the basket."},
                            "quantity": {"type": "integer", "description": "New target quantity."},
                        },
                        "required": ["query", "quantity"],
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
        "name": "update_cart",
        "description": "Change quantity or remove products already in the basket. New products must go through quick_add_items and the customer's exact variant choice. Both spin_id and sku_id are required.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to update in the cart.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "spin_id": {"type": "string", "description": "The variant's spin_id from search results."},
                            "sku_id": {"type": "string", "description": "The variant's sku_id from search results."},
                            "quantity": {"type": "integer", "description": "Quantity to set in the cart (0 to remove)."},
                            "name": {"type": "string", "description": "Human-readable item name."},
                        },
                        "required": ["spin_id", "sku_id", "quantity"],
                    },
                },
                "address_id": {
                    "type": "string",
                    "description": "The user's Swiggy delivery address ID.",
                },
            },
            "required": ["items", "address_id"],
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
        "name": "checkout",
        "description": "Place the Swiggy Instamart order using a payment option the user selected from get_payment_options. NEVER call this unless the user has explicitly confirmed the basket and address.",
        "parameters": {
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The active cart ID from update_cart or get_cart.",
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
                    "description": "Exact ID of the payment option selected by the user from get_payment_options.",
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
        "description": "Fetch live order tracking status, delivery ETA, and rider details.",
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
        "name": "check_replenishment",
        "description": "Check what recurring grocery staples (e.g. milk, eggs, bread) may be running low for this household based on consented past Swiggy purchase history.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
