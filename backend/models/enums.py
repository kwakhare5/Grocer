import enum

class StoreStatus(str, enum.Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    MAINTENANCE = 'maintenance'

class ProductCategory(str, enum.Enum):
    DAIRY = 'dairy'
    BAKERY = 'bakery'
    PRODUCE = 'produce'
    STAPLES = 'staples'
    PACKAGED = 'packaged'

class OrderStatus(str, enum.Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

class SupplierStatus(str, enum.Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DELAYED = 'delayed'

class RiskType(str, enum.Enum):
    STOCKOUT = 'stockout'
    SPOILAGE = 'spoilage'

class RiskSeverity(str, enum.Enum):
    LOW = 'low'
    WARNING = 'warning'
    CRITICAL = 'critical'

class ActionType(str, enum.Enum):
    TRANSFER = 'transfer'
    REORDER = 'reorder'
    DISCOUNT = 'discount'
    HOLD = 'hold'

class ActionStatus(str, enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    EXECUTING = 'executing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'

class RecommendationStatus(str, enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXECUTED = 'executed'
    EXPIRED = 'expired'

class SimulationStatus(str, enum.Enum):
    CREATED = 'created'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    RESET = 'reset'

class RiskStatus(str, enum.Enum):
    ACTIVE = 'active'
    MITIGATED = 'mitigated'
    RESOLVED = 'resolved'
    EXPIRED = 'expired'
