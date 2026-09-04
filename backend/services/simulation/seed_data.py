"""Deterministic seed data catalog for the GROCER v2 simulator.

Defines 5 dark stores, 8 suppliers, 25 products, and 25 customers.
All UUIDs are deterministic via uuid5 for reproducibility.
"""
import uuid
from dataclasses import dataclass, field

# Namespace for deterministic UUIDs
GROCER_NS = uuid.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')

def _id(name: str) -> uuid.UUID:
    """Generate a deterministic UUID from a name."""
    return uuid.uuid5(GROCER_NS, name)


@dataclass(frozen=True)
class SeedStore:
    store_id: uuid.UUID
    name: str
    latitude: float
    longitude: float

@dataclass(frozen=True)
class SeedSupplier:
    supplier_id: uuid.UUID
    name: str
    lead_time_hours: int

@dataclass(frozen=True)
class SeedProduct:
    product_id: uuid.UUID
    name: str
    category: str  # matches ProductCategory enum values
    unit: str
    shelf_life_hours: int
    base_price: float
    supplier_name: str  # resolved to supplier_id during seeding
    substitution_group: str | None = None
    # Demand characteristics for simulator
    daily_demand_mean: float = 10.0  # average daily demand per store
    daily_demand_std: float = 3.0   # demand variation
    weekend_multiplier: float = 1.0  # weekend demand factor

@dataclass(frozen=True)
class SeedCustomer:
    customer_id: uuid.UUID
    name: str
    home_store_name: str  # resolved to store_id during seeding
    order_frequency_days: float = 3.0  # avg days between orders
    avg_items_per_order: int = 4


# === 5 DARK STORES (Mumbai metro area) ===
STORES: list[SeedStore] = [
    SeedStore(_id('store-01'), 'Dark Store Andheri', 19.1136, 72.8697),
    SeedStore(_id('store-02'), 'Dark Store Bandra', 19.0596, 72.8295),
    SeedStore(_id('store-03'), 'Dark Store Powai', 19.1176, 72.9060),
    SeedStore(_id('store-04'), 'Dark Store Dadar', 19.0178, 72.8478),
    SeedStore(_id('store-05'), 'Dark Store Thane', 19.2183, 72.9781),
]

# === 8 SUPPLIERS ===
SUPPLIERS: list[SeedSupplier] = [
    SeedSupplier(_id('supplier-amul'), 'Amul Dairy', 24),
    SeedSupplier(_id('supplier-mother-dairy'), 'Mother Dairy', 18),
    SeedSupplier(_id('supplier-britannia'), 'Britannia Bakery', 12),
    SeedSupplier(_id('supplier-modern'), 'Modern Foods', 12),
    SeedSupplier(_id('supplier-safal'), 'Safal Fresh', 8),
    SeedSupplier(_id('supplier-farm-fresh'), 'Farm Fresh Produce', 6),
    SeedSupplier(_id('supplier-itc'), 'ITC Staples', 48),
    SeedSupplier(_id('supplier-nestle'), 'Nestlé Packaged', 72),
]

# === 25 PRODUCTS across 5 categories ===
PRODUCTS: list[SeedProduct] = [
    # DAIRY (5 products)
    SeedProduct(_id('prod-toned-milk'), 'Toned Milk 500ml', 'dairy', 'pack', 72, 28.0, 'Amul Dairy',
               substitution_group='milk', daily_demand_mean=18.0, daily_demand_std=4.0, weekend_multiplier=0.9),
    SeedProduct(_id('prod-full-cream-milk'), 'Full Cream Milk 1L', 'dairy', 'pack', 72, 66.0, 'Mother Dairy',
               substitution_group='milk', daily_demand_mean=14.0, daily_demand_std=3.5, weekend_multiplier=0.9),
    SeedProduct(_id('prod-curd'), 'Fresh Curd 400g', 'dairy', 'cup', 96, 40.0, 'Amul Dairy',
               daily_demand_mean=12.0, daily_demand_std=3.0, weekend_multiplier=1.1),
    SeedProduct(_id('prod-paneer'), 'Paneer 200g', 'dairy', 'pack', 120, 90.0, 'Amul Dairy',
               daily_demand_mean=8.0, daily_demand_std=2.5, weekend_multiplier=1.3),
    SeedProduct(_id('prod-butter'), 'Butter 100g', 'dairy', 'pack', 240, 56.0, 'Amul Dairy',
               daily_demand_mean=6.0, daily_demand_std=2.0, weekend_multiplier=1.1),

    # BAKERY (5 products)
    SeedProduct(_id('prod-white-bread'), 'White Bread 400g', 'bakery', 'loaf', 48, 40.0, 'Britannia Bakery',
               substitution_group='bread', daily_demand_mean=15.0, daily_demand_std=3.5, weekend_multiplier=1.0),
    SeedProduct(_id('prod-wheat-bread'), 'Whole Wheat Bread 400g', 'bakery', 'loaf', 48, 50.0, 'Modern Foods',
               substitution_group='bread', daily_demand_mean=12.0, daily_demand_std=3.0, weekend_multiplier=1.0),
    SeedProduct(_id('prod-pav'), 'Pav Buns 6pc', 'bakery', 'pack', 36, 30.0, 'Britannia Bakery',
               daily_demand_mean=10.0, daily_demand_std=4.0, weekend_multiplier=1.2),
    SeedProduct(_id('prod-rusk'), 'Toast Rusk 200g', 'bakery', 'pack', 720, 35.0, 'Britannia Bakery',
               daily_demand_mean=5.0, daily_demand_std=1.5, weekend_multiplier=1.0),
    SeedProduct(_id('prod-cake'), 'Fruit Cake Slice', 'bakery', 'piece', 72, 45.0, 'Modern Foods',
               daily_demand_mean=4.0, daily_demand_std=2.0, weekend_multiplier=1.5),

    # PRODUCE (5 products)
    SeedProduct(_id('prod-tomatoes'), 'Tomatoes 500g', 'produce', 'pack', 96, 32.0, 'Farm Fresh Produce',
               daily_demand_mean=16.0, daily_demand_std=4.0, weekend_multiplier=1.1),
    SeedProduct(_id('prod-onions'), 'Onions 1kg', 'produce', 'bag', 168, 40.0, 'Farm Fresh Produce',
               daily_demand_mean=14.0, daily_demand_std=3.0, weekend_multiplier=1.0),
    SeedProduct(_id('prod-potatoes'), 'Potatoes 1kg', 'produce', 'bag', 240, 35.0, 'Safal Fresh',
               daily_demand_mean=12.0, daily_demand_std=2.5, weekend_multiplier=1.0),
    SeedProduct(_id('prod-bananas'), 'Bananas 6pc', 'produce', 'bunch', 72, 45.0, 'Safal Fresh',
               daily_demand_mean=10.0, daily_demand_std=3.0, weekend_multiplier=1.2),
    SeedProduct(_id('prod-green-chillies'), 'Green Chillies 100g', 'produce', 'pack', 96, 15.0, 'Farm Fresh Produce',
               daily_demand_mean=8.0, daily_demand_std=2.5, weekend_multiplier=1.0),

    # STAPLES (5 products)
    SeedProduct(_id('prod-basmati-rice'), 'Basmati Rice 1kg', 'staples', 'bag', 4320, 120.0, 'ITC Staples',
               daily_demand_mean=8.0, daily_demand_std=2.0, weekend_multiplier=1.0),
    SeedProduct(_id('prod-atta'), 'Whole Wheat Atta 5kg', 'staples', 'bag', 2160, 250.0, 'ITC Staples',
               daily_demand_mean=5.0, daily_demand_std=1.5, weekend_multiplier=1.0),
    SeedProduct(_id('prod-toor-dal'), 'Toor Dal 1kg', 'staples', 'bag', 4320, 160.0, 'ITC Staples',
               daily_demand_mean=6.0, daily_demand_std=1.5, weekend_multiplier=1.0),
    SeedProduct(_id('prod-sugar'), 'Sugar 1kg', 'staples', 'bag', 8640, 48.0, 'ITC Staples',
               daily_demand_mean=5.0, daily_demand_std=1.0, weekend_multiplier=1.0),
    SeedProduct(_id('prod-cooking-oil'), 'Sunflower Oil 1L', 'staples', 'bottle', 4320, 140.0, 'ITC Staples',
               daily_demand_mean=5.0, daily_demand_std=1.5, weekend_multiplier=1.0),

    # PACKAGED (5 products)
    SeedProduct(_id('prod-maggi'), 'Maggi Noodles 4-pack', 'packaged', 'pack', 4320, 56.0, 'Nestlé Packaged',
               daily_demand_mean=8.0, daily_demand_std=3.0, weekend_multiplier=1.3),
    SeedProduct(_id('prod-biscuits'), 'Marie Biscuits 300g', 'packaged', 'pack', 2160, 30.0, 'Britannia Bakery',
               daily_demand_mean=7.0, daily_demand_std=2.0, weekend_multiplier=1.1),
    SeedProduct(_id('prod-chips'), 'Potato Chips 150g', 'packaged', 'pack', 2160, 40.0, 'ITC Staples',
               daily_demand_mean=6.0, daily_demand_std=2.5, weekend_multiplier=1.4),
    SeedProduct(_id('prod-jam'), 'Mixed Fruit Jam 200g', 'packaged', 'jar', 4320, 95.0, 'Nestlé Packaged',
               daily_demand_mean=3.0, daily_demand_std=1.0, weekend_multiplier=1.0),
    SeedProduct(_id('prod-ketchup'), 'Tomato Ketchup 500g', 'packaged', 'bottle', 4320, 110.0, 'Nestlé Packaged',
               daily_demand_mean=3.0, daily_demand_std=1.0, weekend_multiplier=1.0),
]

# === 25 CUSTOMERS (synthetic identities, distributed across stores) ===
CUSTOMERS: list[SeedCustomer] = [
    # Store 01 - Andheri (6 customers)
    SeedCustomer(_id('cust-sharma-family'), 'Sharma Family', 'Dark Store Andheri', 2.5, 5),
    SeedCustomer(_id('cust-patel-household'), 'Patel Household', 'Dark Store Andheri', 3.0, 4),
    SeedCustomer(_id('cust-reddy-home'), 'Reddy Home', 'Dark Store Andheri', 4.0, 3),
    SeedCustomer(_id('cust-singh-family'), 'Singh Family', 'Dark Store Andheri', 3.5, 4),
    SeedCustomer(_id('cust-das-house'), 'Das House', 'Dark Store Andheri', 5.0, 3),
    # Store 02 - Bandra (5 customers)
    SeedCustomer(_id('cust-mehta-family'), 'Mehta Family', 'Dark Store Bandra', 2.0, 6),
    SeedCustomer(_id('cust-joshi-home'), 'Joshi Home', 'Dark Store Bandra', 3.0, 4),
    SeedCustomer(_id('cust-khan-household'), 'Khan Household', 'Dark Store Bandra', 3.5, 5),
    SeedCustomer(_id('cust-desai-family'), 'Desai Family', 'Dark Store Bandra', 4.0, 3),
    SeedCustomer(_id('cust-nair-house'), 'Nair House', 'Dark Store Bandra', 2.5, 4),
    # Store 03 - Powai (5 customers)
    SeedCustomer(_id('cust-gupta-family'), 'Gupta Family', 'Dark Store Powai', 2.0, 5),
    SeedCustomer(_id('cust-verma-home'), 'Verma Home', 'Dark Store Powai', 3.0, 4),
    SeedCustomer(_id('cust-iyer-household'), 'Iyer Household', 'Dark Store Powai', 4.0, 3),
    SeedCustomer(_id('cust-bhatt-family'), 'Bhatt Family', 'Dark Store Powai', 3.5, 5),
    SeedCustomer(_id('cust-shetty-house'), 'Shetty House', 'Dark Store Powai', 5.0, 3),
    # Store 04 - Dadar (5 customers)
    SeedCustomer(_id('cust-kulkarni-family'), 'Kulkarni Family', 'Dark Store Dadar', 2.5, 4),
    SeedCustomer(_id('cust-thakur-home'), 'Thakur Home', 'Dark Store Dadar', 3.0, 5),
    SeedCustomer(_id('cust-rao-household'), 'Rao Household', 'Dark Store Dadar', 3.5, 4),
    SeedCustomer(_id('cust-chopra-family'), 'Chopra Family', 'Dark Store Dadar', 4.0, 3),
    SeedCustomer(_id('cust-pillai-house'), 'Pillai House', 'Dark Store Dadar', 2.0, 6),
    # Store 05 - Thane (4 customers)
    SeedCustomer(_id('cust-mishra-family'), 'Mishra Family', 'Dark Store Thane', 3.0, 4),
    SeedCustomer(_id('cust-saxena-home'), 'Saxena Home', 'Dark Store Thane', 3.5, 5),
    SeedCustomer(_id('cust-pandey-household'), 'Pandey Household', 'Dark Store Thane', 4.0, 3),
    SeedCustomer(_id('cust-dubey-family'), 'Dubey Family', 'Dark Store Thane', 5.0, 4),
    SeedCustomer(_id('cust-trivedi-house'), 'Trivedi House', 'Dark Store Thane', 2.5, 4),
]
