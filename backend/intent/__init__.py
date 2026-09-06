"""GROCER Intent Contract Subsystem (Spec §5).

Provides canonical domain representations of user intent, constraints,
preferences, authorization boundaries, and session snapshots.
"""
from backend.intent.enums import (
    AmbiguitySeverity,
    BrandTolerance,
    ConstraintType,
    PrecedenceLevel,
    PreferenceType,
    SubstitutionTolerance,
)
from backend.intent.models import (
    Ambiguity,
    AuthorizationScope,
    BrandPreference,
    BudgetConstraint,
    DeliveryPreferences,
    DietaryConstraint,
    HardConstraint,
    IntentContract,
    IntentItem,
    PackSizeRules,
    QuantityRules,
    SoftPreference,
    SourceContext,
    SubstitutionPolicy,
)
from backend.intent.storage import IntentSessionStore, default_intent_store
from backend.intent.parser import IntentParser
from backend.intent.policy import (
    ActionProposal,
    AutonomyLevel,
    PolicyDecision,
    PolicyEngine,
)
from backend.intent.preferences import (
    PreferenceStore,
    StoredPreference,
    default_preference_store,
)
from backend.intent.verifier import (
    ConstraintViolation,
    IntentVerifier,
    PreferenceDeviation,
    VerificationResult,
    VerificationStatus,
    ViolationCode,
)
from backend.intent.recovery import (
    FailureClass,
    RecoveryAction,
    RecoveryCandidate,
    RecoveryEngine,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.session import (
    BasketItem,
    BasketSummary,
    ClarificationOption,
    ConversationState,
    OrchestratorSession,
    OrchestratorSessionStore,
    PendingClarification,
    default_session_store,
)
from backend.intent.orchestrator import (
    GrocerOrchestrator,
    OrchestratorTurnResult,
)

__all__ = [
    # Enums
    "ConstraintType",
    "PreferenceType",
    "SubstitutionTolerance",
    "BrandTolerance",
    "AmbiguitySeverity",
    "PrecedenceLevel",
    # Domain Models
    "IntentItem",
    "HardConstraint",
    "SoftPreference",
    "BudgetConstraint",
    "QuantityRules",
    "PackSizeRules",
    "BrandPreference",
    "SubstitutionPolicy",
    "DietaryConstraint",
    "DeliveryPreferences",
    "AuthorizationScope",
    "Ambiguity",
    "SourceContext",
    "IntentContract",
    # Storage
    "IntentSessionStore",
    "default_intent_store",
    # Parser
    "IntentParser",
    # Policy (Phase 3)
    "ActionProposal",
    "AutonomyLevel",
    "PolicyDecision",
    "PolicyEngine",
    # Preferences (Phase 3)
    "PreferenceStore",
    "StoredPreference",
    "default_preference_store",
    # Verifier (Phase 4)
    "ConstraintViolation",
    "IntentVerifier",
    "PreferenceDeviation",
    "VerificationResult",
    "VerificationStatus",
    "ViolationCode",
    # Recovery (Phase 5)
    "FailureClass",
    "RecoveryAction",
    "RecoveryCandidate",
    "RecoveryEngine",
    "RecoveryOutcome",
    "RecoveryState",
    # Session (Phase 6)
    "BasketItem",
    "BasketSummary",
    "ClarificationOption",
    "ConversationState",
    "OrchestratorSession",
    "OrchestratorSessionStore",
    "PendingClarification",
    "default_session_store",
    # Orchestrator (Phase 6)
    "GrocerOrchestrator",
    "OrchestratorTurnResult",
]
