# Unified catalog — imported from catalog.py (single source of truth).
# Previously this file had different item IDs (item_1, item_2...) than mock_server.py (INS_001...).
# Now both use the same catalog to ensure ML model IDs match MCP server IDs.
from backend.seed.catalog import CATALOG as REALISTIC_GROCERY_ITEMS  # noqa: F401
