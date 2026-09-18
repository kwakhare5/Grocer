"""Policy Engine — deterministic agent autonomy classification (Spec §6).

Evaluates proposed agent actions against the active IntentContract and returns
a PolicyDecision with an AutonomyLevel governing whether the action can be
auto-executed, requires user input, requires explicit confirmation, or is blocked.

Architecture:
    ActionProposal + IntentContract → PolicyEngine.evaluate() → PolicyDecision
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.intent.enums import ConstraintType, SubstitutionTolerance
from backend.intent.models import IntentContract


# ---------------------------------------------------------------------------
# Autonomy classification (Spec §6)
# ---------------------------------------------------------------------------

class AutonomyLevel(str, Enum):
    """Three-level conversational autonomy model plus hard block.

    AUTO_EXECUTE:          Safe, deterministic, inside the intent — act automatically.
    ASK_USER:              Meaningful ambiguity or multiple valid choices — ask the user.
    REQUIRE_CONFIRMATION:  Consequential financial action — require explicit confirmation.
    BLOCKED:               Violates a hard constraint — cannot proceed at all.
    """
    AUTO_EXECUTE = "auto_execute"
    ASK_USER = "ask_user"
    REQUIRE_CONFIRMATION = "require_confirmation"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Action proposal and decision models
# ---------------------------------------------------------------------------

class ActionProposal(BaseModel):
    """Describes a proposed agent action to be evaluated against policy."""
    model_config = ConfigDict(extra="ignore")

    action_type: str = Field(
        ...,
        description="Type of action: add_item, substitute, remove_item, "
                    "adjust_quantity, checkout, retry, clear_cart",
    )
    target: str = Field(default="", description="Item or product identifier")
    details: dict[str, Any] = Field(default_factory=dict, description="Action-specific payload")
    reason: str = Field(default="", description="Why the agent proposes this action")


class PolicyDecision(BaseModel):
    """Result of evaluating an ActionProposal against the active IntentContract."""
    model_config = ConfigDict(extra="ignore")

    autonomy_level: AutonomyLevel
    reason: str = Field(..., description="Human-readable explanation of the decision")
    violations: list[str] = Field(default_factory=list, description="Hard constraint violations")
    clarification_needed: Optional[str] = Field(
        default=None, description="Suggested clarification question for user",
    )


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Deterministic action authorization engine (Spec §6, §12.2).

    Evaluates whether a proposed action is safe to auto-execute, requires
    user input, requires explicit confirmation, or is blocked by a hard constraint.

    Rules:
        1. Checkout → always REQUIRE_CONFIRMATION (Spec §8.3)
        2. Hard constraint violation → BLOCKED
        3. Action within approved substitution policy → AUTO_EXECUTE
        4. Ambiguous or outside policy → ASK_USER
    """

    def evaluate(self, proposal: ActionProposal, contract: IntentContract) -> PolicyDecision:
        """Evaluate a proposed action against the active intent contract.

        Args:
            proposal: The action the agent wants to take.
            contract: The current validated IntentContract.

        Returns:
            A PolicyDecision with the appropriate autonomy level.
        """
        action = proposal.action_type.lower()

        # Rule 1: Checkout is always consequential
        if action == "checkout":
            return PolicyDecision(
                autonomy_level=AutonomyLevel.REQUIRE_CONFIRMATION,
                reason="Checkout is a consequential financial action requiring explicit user confirmation",
            )

        # Rule 2: Check hard constraint violations
        violations = self._check_hard_constraints(proposal, contract)
        if violations:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.BLOCKED,
                reason=f"Action violates hard constraint(s): {'; '.join(violations)}",
                violations=violations,
            )

        # Rule 3: Substitution evaluation
        if action == "substitute":
            return self._evaluate_substitution(proposal, contract)

        # Rule 4: Budget-affecting actions
        if action in ("add_item", "adjust_quantity"):
            return self._evaluate_budget_impact(proposal, contract)

        # Rule 5: Safe deterministic actions
        if action in ("remove_item", "clear_cart", "retry"):
            return PolicyDecision(
                autonomy_level=AutonomyLevel.AUTO_EXECUTE,
                reason=f"Action '{action}' is safe and deterministic",
            )

        # Default: ask user for unknown action types
        return PolicyDecision(
            autonomy_level=AutonomyLevel.ASK_USER,
            reason=f"Action type '{action}' is not covered by an explicit policy rule",
            clarification_needed=f"Can I proceed with: {proposal.reason}?",
        )

    def _check_hard_constraints(
        self, proposal: ActionProposal, contract: IntentContract,
    ) -> list[str]:
        """Check if a proposal violates any hard constraints."""
        violations: list[str] = []
        target_lower = proposal.target.lower()
        details = proposal.details

        # Dietary violation: adding a non-veg item to a vegetarian contract
        if proposal.action_type.lower() in ("add_item", "substitute"):
            item_category = details.get("category", "").lower()
            item_name = details.get("item_name", target_lower).lower()

            _non_veg = {"chicken", "mutton", "lamb", "fish", "prawn", "shrimp",
                        "pork", "beef", "meat", "egg", "eggs"}

            if contract.has_dietary_constraint("vegetarian"):
                if item_name in _non_veg or item_category in ("poultry", "meat", "seafood"):
                    violations.append(
                        f"Adding '{item_name}' violates vegetarian dietary constraint"
                    )

        # Brand lock violation: substituting a brand-locked product
        if proposal.action_type.lower() == "substitute":
            new_brand = details.get("new_brand", "").lower()
            if new_brand:
                bp = contract.get_brand_preference(target_lower)
                if bp and bp.is_hard and new_brand != bp.preferred_brand.lower():
                    violations.append(
                        f"Substituting '{target_lower}' with brand '{new_brand}' "
                        f"violates brand lock (required: '{bp.preferred_brand}')"
                    )

        # Budget violation with zero tolerance
        if proposal.action_type.lower() in ("add_item", "substitute", "adjust_quantity"):
            price_delta = details.get("price_delta", 0.0)
            if contract.budget and contract.budget.is_hard and price_delta > 0:
                max_dev = contract.budget.max_deviation
                if contract.authorization_scope.max_auto_spend_deviation > 0:
                    max_dev = max(max_dev, contract.authorization_scope.max_auto_spend_deviation)
                if max_dev == 0 and price_delta > 0:
                    current_total = details.get("current_total", 0.0)
                    budget_limit = contract.budget.max_budget or float("inf")
                    if current_total + price_delta > budget_limit:
                        violations.append(
                            f"Price increase of ₹{price_delta:.0f} would breach "
                            f"hard budget limit of ₹{budget_limit:.0f} (zero deviation allowed)"
                        )

        return violations

    def _evaluate_substitution(
        self, proposal: ActionProposal, contract: IntentContract,
    ) -> PolicyDecision:
        """Evaluate whether a substitution can be auto-executed or needs user input."""
        details = proposal.details
        target_lower = proposal.target.lower()
        sub_policy = contract.substitution_policy

        # If substitutions are globally disabled
        if not sub_policy.allow_substitutions:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.BLOCKED,
                reason="Substitutions are disabled by user policy",
                violations=["no_substitution policy active"],
            )

        # Check if auto-replace is authorized
        if not contract.authorization_scope.can_auto_replace:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.ASK_USER,
                reason="Auto-replacement is disabled; user approval required",
                clarification_needed=f"Can I replace {proposal.target} with {details.get('replacement', 'an alternative')}?",
            )

        # Check price increase approval requirement
        price_delta = details.get("price_delta", 0.0)
        if price_delta > 0 and contract.authorization_scope.requires_approval_for_price_increase:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.ASK_USER,
                reason=f"Substitution increases price by ₹{price_delta:.0f}; approval required per policy",
                clarification_needed=(
                    f"Replacing {proposal.target} costs ₹{price_delta:.0f} more. Should I proceed?"
                ),
            )

        # Check brand tolerance
        new_brand = details.get("new_brand", "")
        bp = contract.get_brand_preference(target_lower)
        if bp and new_brand:
            if bp.is_hard:
                # Already caught by _check_hard_constraints, but double-check
                if new_brand.lower() != bp.preferred_brand.lower():
                    return PolicyDecision(
                        autonomy_level=AutonomyLevel.BLOCKED,
                        reason=f"Brand lock prevents switching from '{bp.preferred_brand}' to '{new_brand}'",
                        violations=[f"brand_lock:{target_lower}"],
                    )
            elif new_brand.lower() not in [b.lower() for b in bp.alternative_brands]:
                # Soft brand preference but not in alternatives list
                if sub_policy.brand_tolerance == "same_brand":
                    return PolicyDecision(
                        autonomy_level=AutonomyLevel.ASK_USER,
                        reason=f"Brand '{new_brand}' is not in known alternatives for {target_lower}",
                        clarification_needed=f"Your usual brand isn't available. Can I use {new_brand} instead?",
                    )

        # Check pack size rules
        old_pack = details.get("old_pack_size", "").strip()
        new_pack = details.get("new_pack_size", "").strip()
        if old_pack and new_pack and old_pack.lower() != new_pack.lower():
            if not contract.pack_size_rules.preferred_multiples or contract.pack_size_rules.tolerance == SubstitutionTolerance.STRICT:
                return PolicyDecision(
                    autonomy_level=AutonomyLevel.ASK_USER,
                    reason=f"Pack size change from '{old_pack}' to '{new_pack}' requires user approval per pack size rules",
                    clarification_needed=f"'{old_pack}' is unavailable. Can I substitute with '{new_pack}' ({details.get('item_name')}) instead?",
                )

        # Same category, no price increase, within tolerance → auto-execute
        return PolicyDecision(
            autonomy_level=AutonomyLevel.AUTO_EXECUTE,
            reason=f"Substitution for '{proposal.target}' is within approved policy bounds",
        )

    def _evaluate_budget_impact(
        self, proposal: ActionProposal, contract: IntentContract,
    ) -> PolicyDecision:
        """Evaluate whether a budget-affecting action can proceed."""
        details = proposal.details
        price_delta = details.get("price_delta", 0.0)

        if not contract.budget or contract.budget.max_budget is None:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.AUTO_EXECUTE,
                reason="No budget constraint set; action is safe",
            )

        current_total = details.get("current_total", 0.0)
        new_total = current_total + price_delta
        budget_limit = contract.budget.max_budget

        if new_total <= budget_limit:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.AUTO_EXECUTE,
                reason=f"Action keeps total (₹{new_total:.0f}) within budget (₹{budget_limit:.0f})",
            )

        # Over budget
        max_dev = contract.budget.max_deviation
        if contract.authorization_scope.max_auto_spend_deviation > 0:
            max_dev = max(max_dev, contract.authorization_scope.max_auto_spend_deviation)

        overrun = new_total - budget_limit

        if contract.budget.is_hard and max_dev == 0:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.BLOCKED,
                reason=f"Adding ₹{price_delta:.0f} would breach hard budget (₹{budget_limit:.0f}) with zero deviation",
                violations=[f"budget_breach:{overrun:.0f}"],
            )

        if overrun <= max_dev:
            return PolicyDecision(
                autonomy_level=AutonomyLevel.ASK_USER,
                reason=f"Budget overrun of ₹{overrun:.0f} is within allowed deviation (₹{max_dev:.0f}), but needs approval",
                clarification_needed=f"This would put your total ₹{overrun:.0f} over budget. Continue?",
            )

        return PolicyDecision(
            autonomy_level=AutonomyLevel.ASK_USER,
            reason=f"Budget overrun of ₹{overrun:.0f} exceeds allowed deviation (₹{max_dev:.0f})",
            clarification_needed=f"This would put your total ₹{overrun:.0f} over your ₹{budget_limit:.0f} budget. Should I adjust?",
        )
