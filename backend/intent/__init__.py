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

# Compatibility wiring: the orchestrator still imports RecoveryEngine directly.
# Replace that module-global with the bounded closed-loop implementation after
# the orchestrator module has finished importing, without changing its public API.
from backend.intent import orchestrator as _orchestrator_module
from backend.intent.recovery_loop import LoopingRecoveryEngine

_orchestrator_module.RecoveryEngine = LoopingRecoveryEngine

__all__ = [
    "ConstraintType",
    "PreferenceType",
    "SubstitutionTolerance",
    "BrandTolerance",
    "AmbiguitySeverity",
    "PrecedenceLevel",
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
    "IntentSessionStore",
    "default_intent_store",
    "IntentParser",
    "ActionProposal",
    "AutonomyLevel",
    "PolicyDecision",
    "PolicyEngine",
    "PreferenceStore",
    "StoredPreference",
    "default_preference_store",
    "ConstraintViolation",
    "IntentVerifier",
    "PreferenceDeviation",
    "VerificationResult",
    "VerificationStatus",
    "ViolationCode",
    "FailureClass",
    "RecoveryAction",
    "RecoveryCandidate",
    "RecoveryEngine",
    "LoopingRecoveryEngine",
    "RecoveryOutcome",
    "RecoveryState",
    "BasketItem",
    "BasketSummary",
    "ClarificationOption",
    "ConversationState",
    "OrchestratorSession",
    "OrchestratorSessionStore",
    "PendingClarification",
    "default_session_store",
    "GrocerOrchestrator",
    "OrchestratorTurnResult",
]
