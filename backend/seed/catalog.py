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


def lookup_catalog_item(query: str) -> dict:
    """
    Find a catalog item by name or id using exact, substring, or fuzzy matching.
    """
    if not query:
        return None
    query_lower = query.lower().strip()
    
    # 1. Exact ID or Name match
    for item in CATALOG:
        if item["id"].lower() == query_lower or item["name"].lower() == query_lower:
            return item
            
    # 2. Check for exact substring match
    for item in CATALOG:
        name_lower = item["name"].lower()
        if query_lower in name_lower or name_lower in query_lower:
            return item
            
    # 3. Check for plural/singular spelling (e.g. "tomato" -> "tomatoes", "egg" -> "eggs", "onion" -> "onions")
    # Clean query from punctuation
    import string
    cleaned_query = query_lower.translate(str.maketrans("", "", string.punctuation))
    
    # Simple normalizer for plural / common variants
    def normalize_word(w: str) -> str:
        w = w.strip()
        if w.endswith("es"):
            return w[:-2]
        if w.endswith("s"):
            return w[:-1]
        return w
        
    query_words = [normalize_word(w) for w in cleaned_query.split() if len(w) > 2]
    
    for item in CATALOG:
        name_words = [normalize_word(w) for w in item["name"].lower().translate(str.maketrans("", "", string.punctuation)).split() if len(w) > 2]
        # Match if any query word normalizes to a name word
        for qw in query_words:
            for nw in name_words:
                if qw in nw or nw in qw:
                    return item
                    
    # 4. Levenshtein-based fuzzy match fallback
    def lev_dist(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return lev_dist(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                ins = prev[j + 1] + 1
                dl = curr[j] + 1
                sub = prev[j] + (c1 != c2)
                curr.append(min(ins, dl, sub))
            prev = curr
        return prev[-1]
        
    for item in CATALOG:
        name_lower = item["name"].lower()
        # Check distance on words
        for w1 in cleaned_query.split():
            if len(w1) < 3:
                continue
            for w2 in name_lower.split():
                if len(w2) < 3:
                    continue
                # If length <= 4, dist <= 1, else dist <= 2
                max_len = max(len(w1), len(w2))
                dist = lev_dist(w1, w2)
                if (max_len <= 4 and dist <= 1) or (max_len <= 7 and dist <= 2) or dist <= 3:
                    return item
                    
    return None


def format_restock_alert_message(items: list[dict]) -> str:
    """
    Format a list of depleting items into a detailed restock alert message.
    """
    if not items:
        return "No items depleting within threshold window."
        
    lines = []
    total_amount = 0.0
    
    for item in items:
        item_name = item.get("item_name") or item.get("name") or "Unknown Item"
        cat = lookup_catalog_item(item_name)
        
        name = cat["name"] if cat else item_name
        price = cat["price"] if cat else 0.0
        category = cat["category"] if cat else "unknown"
        unit = cat["unit"] if cat else "N/A"
        qty = 1  # Alert items default to qty 1
        
        total_amount += price * qty
        
        info_parts = [f"Category: {category}", f"Unit: {unit}"]
        
        if "confidence_score" in item:
            conf = int(item["confidence_score"] * 100)
            info_parts.append(f"Confidence: {conf}%")
        elif "confidence_label" in item:
            info_parts.append(f"Confidence: {item['confidence_label']}")
            
        if "days_remaining" in item:
            info_parts.append(f"Days remaining: {item['days_remaining']}")
            
        info_str = ", ".join(info_parts)
        lines.append(f"• {name} (Qty: {qty}) - Price: ₹{price:.0f} ({info_str})")
        
    items_list_str = "\n".join(lines)
    
    message = (
        "[ALERT] Running low on the following items:\n"
        f"{items_list_str}\n\n"
        f"Estimated Total: ₹{total_amount:.0f}\n\n"
        "Reply YES to reorder all, or tell me which ones."
    )
    return message

