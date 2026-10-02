"""OpenAI and Groq-compatible function-calling tool schema declarations for GROCER."""
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
        "name": "search_products",
        "description": "Search products in the live Swiggy Instamart store catalogue for the selected delivery address. Returns in-stock variants, pack sizes, formatted prices, spin_id, and sku_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Item name to search for (e.g. 'dairy milk', 'eggs', 'bread', 'amul milk').",
                },
                "address_id": {
                    "type": "string",
                    "description": "The user's Swiggy delivery address ID.",
                },
            },
            "required": ["query", "address_id"],
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
        "description": "Add, modify, or set items in the Swiggy Instamart cart. Both spin_id and sku_id from search_products are strictly mandatory for every item.",
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
        "description": "Place the Swiggy Instamart order and generate a UPI QR / payment link. NEVER call this unless the user has explicitly confirmed the basket.",
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
                    "description": "Payment option kind, default 'qr'.",
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
]

# Standard OpenAI / Groq / OpenRouter tool declarations
OPENAI_TOOL_DECLARATIONS = [
    {
        "type": "function",
        "function": tool,
    }
    for tool in RAW_TOOL_DECLARATIONS
]
