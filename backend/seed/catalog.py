"""
Canonical product catalog for Instamart Intelligence.
This is the single source of truth for item IDs, names, categories, prices, and units.

Used by:
  - backend/seed/generate_orders.py  (seed data generation)
  - backend/mcp/mock_server.py       (mock Swiggy API catalog)

Why a shared catalog?
  Previously, seed/ and mcp/ had separate, inconsistent item lists with different
  IDs (item_1 vs INS_001). This caused the ML models trained on seed data to
  reference item IDs that the mock server had never heard of.
"""

CATALOG = [
    {"id": "INS_001", "name": "Amul Taza Milk 1L",           "category": "dairy",      "price": 28.0,  "price_per_unit": 28.0,  "unit": "L"},
    {"id": "INS_002", "name": "Aashirvaad Atta 5kg",          "category": "staples",    "price": 198.0, "price_per_unit": 39.6,  "unit": "kg"},
    {"id": "INS_003", "name": "Fortune Sunflower Oil 1L",     "category": "staples",    "price": 127.0, "price_per_unit": 127.0, "unit": "L"},
    {"id": "INS_004", "name": "India Gate Basmati Rice 5kg",  "category": "staples",    "price": 310.0, "price_per_unit": 62.0,  "unit": "kg"},
    {"id": "INS_005", "name": "Nandini Eggs (Pack of 12)",    "category": "protein",    "price": 84.0,  "price_per_unit": 7.0,   "unit": "piece"},
    {"id": "INS_006", "name": "Tomatoes (500g)",               "category": "vegetables", "price": 29.0,  "price_per_unit": 58.0,  "unit": "kg"},
    {"id": "INS_007", "name": "Onions (1kg)",                  "category": "vegetables", "price": 42.0,  "price_per_unit": 42.0,  "unit": "kg"},
    {"id": "INS_008", "name": "Amul Butter 500g",             "category": "dairy",      "price": 270.0, "price_per_unit": 540.0, "unit": "kg"},
    {"id": "INS_009", "name": "Amul Fresh Cream 200ml",       "category": "dairy",      "price": 55.0,  "price_per_unit": 275.0, "unit": "L"},
    {"id": "INS_010", "name": "Tata Salt 1kg",                "category": "staples",    "price": 28.0,  "price_per_unit": 28.0,  "unit": "kg"},
    {"id": "INS_011", "name": "Britannia Whole Wheat Bread",  "category": "bakery",     "price": 50.0,  "price_per_unit": 50.0,  "unit": "400g"},
    {"id": "INS_012", "name": "Farm Fresh Onion 1kg",         "category": "vegetables", "price": 45.0,  "price_per_unit": 45.0,  "unit": "kg"},
]
