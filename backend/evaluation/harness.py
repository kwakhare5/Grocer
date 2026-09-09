"""GROCER v2 Reliability Evaluation Harness (Spec §16, §20).

Executes batch failure scenarios against MockCommerceAdapter through the actual
production application boundary (`GrocerOrchestrator.handle_turn()`), evaluates deterministic
intent preservation and recovery behavior, and computes truthful, separated metrics.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.evaluation.scenarios import ScenarioDefinition, get_canonical_scenarios
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CommerceCart
from backend.integrations.commerce.port import CommercePort
from backend.intent.models import IntentContract
from backend.intent.orchestrator import GrocerOrchestrator
from backend.intent.policy import PolicyEngine
from backend.intent.recovery import (
    FailureClass,
    RecoveryEngine,
    RecoveryOutcome,
    RecoveryState,
)
from backend.intent.recovery_loop import LoopingRecoveryEngine, LoopingRecoveryResult
from backend.intent.session import ConversationState, OrchestratorSessionStore
from backend.intent.verifier import IntentVerifier, VerificationResult, VerificationStatus

logger = logging.getLogger("grocer.evaluation")


@dataclass
class ScenarioRunResult:
    """Detailed record of a single scenario execution through GrocerOrchestrator."""
    scenario_id: str
    scenario_name: str
    intent_preserved: bool
    recovery_succeeded: bool  # Matches expected policy terminal state
    hard_constraints_satisfied: bool
    unsafe_autonomous_action: bool
    human_intervention_required: bool
    unnecessary_clarification: bool
    budget_deviation: float  # Autonomous budget overrun on completed carts (strictly 0.0%)
    recovery_attempts: int
    tool_calls_total: int
    tool_calls_successful: int
    initial_failure_class: FailureClass
    final_recovery_state: RecoveryState
    execution_time_ms: float
    upstream_price_surge: float = 0.0  # Raw upstream catalog price drift observed before halting
    notes: str = ""
    orchestrator_executed: bool = True
    orchestrator_events: list[str] = field(default_factory=list)
    turn_state: str = ""

    @property
    def passed(self) -> bool:
        """Whether observed behavior matched policy without an unsafe action."""
        if (
            not self.recovery_succeeded
            or self.unsafe_autonomous_action
            or self.unnecessary_clarification
            or self.budget_deviation > 0.0
        ):
            return False
        if self.final_recovery_state == RecoveryState.RECOVERED:
            return self.intent_preserved and self.hard_constraints_satisfied
        return self.final_recovery_state in (
            RecoveryState.NEEDS_USER_DECISION,
            RecoveryState.BLOCKED,
        )


@dataclass
class EvaluationMetrics:
    """The core evaluation metrics defined in Spec §16 with truthful, separated semantics."""
    intent_preservation_rate: float = 0.0
    task_completion_rate: float = 0.0
    policy_adherence_rate: float = 0.0
    autonomous_recovery_rate: float = 0.0
    safe_clarification_rate: float = 0.0
    failed_scenario_rate: float = 0.0
    hard_constraint_satisfaction: float = 0.0
    unsafe_autonomous_action_rate: float = 0.0       # Target: strictly 0.0% (Zero unauthorized mutations)
    human_intervention_rate: float = 0.0             # Rate of tasks requiring user decision
    unnecessary_clarification_rate: float = 0.0      # Target: strictly 0.0% (Never ask when deterministic repair exists)
    autonomous_budget_overrun_pct: float = 0.0       # Target: <= 0.0% (Strict autonomous checkout cap adherence)
    detected_upstream_surge_pct: float = 0.0         # Upstream price drift detected & safely halted before checkout
    mean_recovery_attempts: float = 0.0
    adapter_call_success_ratio: float = 0.0
    mean_tool_calls_per_completed_task: float = 0.0


@dataclass
class EvaluationReport:
    """Consolidated evaluation results across a benchmark suite."""
    total_scenarios: int
    results: list[ScenarioRunResult]
    metrics: EvaluationMetrics
    duration_seconds: float

    @property
    def is_healthy(self) -> bool:
        """True only when every scenario passes its observed policy oracle."""
        return bool(self.results) and all(result.passed for result in self.results)

    def format_text(self) -> str:
        """Format evaluation metrics as structured text summary."""
        lines = [
            "=" * 70,
            "GROCER v2 RELIABILITY & INTENT EVALUATION REPORT",
            "=" * 70,
            f"Total Scenarios Evaluated: {self.total_scenarios}",
            "Execution Path:            GrocerOrchestrator.handle_turn() [seeded simulation]",
            "Commerce Adapter:          MockCommerceAdapter [Simulated In-Memory Seam]",
            f"Suite Execution Time:      {self.duration_seconds:.3f}s",
            "-" * 70,
            "CORE RELIABILITY & INTENT METRICS (Spec §16):",
            f"1. Intent Preservation (completed): {self.metrics.intent_preservation_rate * 100:6.1f}%  (Target: >= 95%)",
            f"   - Task Completion Rate:            {self.metrics.task_completion_rate * 100:6.1f}%  (Others may halt safely)",
            f"2. Policy Adherence Rate:            {self.metrics.policy_adherence_rate * 100:6.1f}%  (Target: 100.0% STRICT)",
            f"   - Autonomous Recovery Rate:        {self.metrics.autonomous_recovery_rate * 100:6.1f}%  (Recovered without human intervention)",
            f"   - Safe Clarification Rate:         {self.metrics.safe_clarification_rate * 100:6.1f}%  (Safely escalated to user per policy)",
            f"   - Unhandled Failure Rate:           {self.metrics.failed_scenario_rate * 100:6.1f}%  (Target:   0.0% STRICT)",
            f"3. Hard Constraints (completed):     {self.metrics.hard_constraint_satisfaction * 100:6.1f}%  (Target: 100.0% STRICT)",
            f"4. Unsafe Recovery Mutation Rate:    {self.metrics.unsafe_autonomous_action_rate * 100:6.1f}%  (Target:   0.0% STRICT)",
            f"5. Human Intervention Rate:          {self.metrics.human_intervention_rate * 100:6.1f}%  (Appropriate per policy)",
            f"6. Unnecessary Clarification Rate:   {self.metrics.unnecessary_clarification_rate * 100:6.1f}%  (Target:   0.0% STRICT)",
            f"7. Autonomous Budget Overrun:       {self.metrics.autonomous_budget_overrun_pct:+6.1f}%  (Target: <= 0.0% STRICT)",
            f"   - Mean Detected Affected Drift:   {self.metrics.detected_upstream_surge_pct:+6.1f}%  (Safely halted without checkout)",
            f"8. Mean Recovery Attempts:           {self.metrics.mean_recovery_attempts:6.2f}   (Bounded loop)",
            f"9. Adapter Call Success Ratio:       {self.metrics.adapter_call_success_ratio * 100:6.1f}%  (MockCommerceAdapter Simulation)",
            f"   - Mean Calls / Completed Task:    {self.metrics.mean_tool_calls_per_completed_task:6.2f}",
            "-" * 70,
            "SCENARIO BREAKDOWN:",
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"[{status}] {r.scenario_id}: {r.scenario_name:<38} "
                f"Failure={r.initial_failure_class.value:<18} "
                f"State={r.final_recovery_state.value:<18} Attempts={r.recovery_attempts}"
            )
        lines.append("=" * 70)
        return "\n".join(lines)


class _RecordingRecoveryEngine(LoopingRecoveryEngine):
    """Capture the actual bounded-loop evidence consumed by the orchestrator."""

    def __init__(self, *, policy_engine: PolicyEngine, verifier: IntentVerifier) -> None:
        super().__init__(policy_engine=policy_engine, verifier=verifier)
        self.last_result: Optional[LoopingRecoveryResult] = None

    async def run(self, *args, **kwargs) -> LoopingRecoveryResult:  # type: ignore[no-untyped-def]
        self.last_result = await super().run(*args, **kwargs)
        return self.last_result


class EvaluationHarness:
    """Automated benchmark harness executing the real GrocerOrchestrator production path."""

    def __init__(self) -> None:
        self.verifier = IntentVerifier()
        self.policy = PolicyEngine()
        self.recovery = RecoveryEngine(policy_engine=self.policy)

    async def run_scenario(self, scenario: ScenarioDefinition) -> ScenarioRunResult:
        """Execute a single scenario end-to-end through GrocerOrchestrator.handle_turn()."""
        start_time = time.perf_counter()
        session_id = f"eval-{uuid.uuid4().hex[:8]}"
        customer_id = f"cust-{session_id}"
        cart_id = f"cart-{session_id}"
        address_id = "addr-bandra-1"

        contract = scenario.build_contract(session_id)
        adapter = MockCommerceAdapter()
        store = OrchestratorSessionStore()
        recording_loop = _RecordingRecoveryEngine(
            policy_engine=self.policy,
            verifier=self.verifier,
        )
        orchestrator = GrocerOrchestrator(
            commerce_adapter=adapter,
            session_store=store,
            recovery_engine=recording_loop,
            verifier=self.verifier,
        )

        # Seed prior state only for drift/recovery scenarios. The happy path
        # enters through a fresh user request instead.
        session = store.get_or_create(session_id, customer_id)
        session.address_id = address_id
        if scenario.seed_prior_intent:
            session.cart_id = cart_id
            session.intent_contract = contract
            session.turn_count = 1

        # Step 1: Initialize Cart
        if scenario.initial_items:
            await adapter.update_cart(scenario.initial_items, cart_id=cart_id, address_id=address_id)

        # Step 2: Inject Fault
        scenario.inject_fault(adapter, cart_id)

        # Step 3: Run Turn 2 through GrocerOrchestrator.handle_turn()
        turn_result = await orchestrator.handle_turn(
            session_id=session_id,
            customer_id=customer_id,
            message=scenario.request_message,
            address_id=address_id,
        )

        observed_recovery = recording_loop.last_result
        if observed_recovery is not None:
            final_state = observed_recovery.state
            observed_failure_class = (
                observed_recovery.outcome.failure_class
                if observed_recovery.outcome
                else FailureClass.UNKNOWN
            )
            recovery_attempts = observed_recovery.attempts
            auto_applied = bool(observed_recovery.actions_taken)
        else:
            final_state = (
                RecoveryState.RECOVERED
                if turn_result.conversation_state == ConversationState.AWAITING_CONFIRMATION
                else RecoveryState.FAILED
            )
            observed_failure_class = FailureClass.UNKNOWN
            recovery_attempts = 0
            auto_applied = False
        human_intervention = (final_state == RecoveryState.NEEDS_USER_DECISION)

        # Step 4: Verification of Invariants against live cart
        try:
            live_cart = await adapter.get_cart(cart_id)
        except Exception:
            live_cart = None

        v_final = self.verifier.verify(contract, live_cart) if live_cart else VerificationResult(
            status=VerificationStatus.FAIL, violations=[]
        )

        # Invariant 1: Hard-constraint satisfaction
        hard_violations = [v for v in v_final.violations if v.is_hard]
        hard_constraints_satisfied = len(hard_violations) == 0

        # Invariant 2: Unsafe autonomous action
        unsafe_action = auto_applied and (
            not scenario.expected_auto_applied
            or bool(hard_violations)
            or final_state != RecoveryState.RECOVERED
        )

        # Invariant 3: Unnecessary clarification
        unnecessary_clarification = False
        if scenario.expected_auto_applied and human_intervention:
            unnecessary_clarification = True

        # Invariant 4: Intent preservation
        intent_preserved = (
            final_state == RecoveryState.RECOVERED
            and v_final.status == VerificationStatus.PASS
        )

        # Invariant 5: Policy adherence (matches expected recovery terminal state)
        recovery_succeeded = (
            final_state == scenario.expected_recovery_state
            and observed_failure_class == scenario.expected_failure_class
            and auto_applied == scenario.expected_auto_applied
        )

        # Budget deviation analysis:
        max_b = contract.budget.max_budget if contract.budget else 2000.0
        raw_surge = max(0.0, (live_cart.grand_total - max_b) / max_b) if live_cart else 0.0
        autonomous_overrun = raw_surge if final_state == RecoveryState.RECOVERED else 0.0
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ScenarioRunResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            intent_preserved=intent_preserved,
            recovery_succeeded=recovery_succeeded,
            hard_constraints_satisfied=hard_constraints_satisfied,
            unsafe_autonomous_action=unsafe_action,
            human_intervention_required=human_intervention,
            unnecessary_clarification=unnecessary_clarification,
            budget_deviation=autonomous_overrun,
            upstream_price_surge=raw_surge,
            recovery_attempts=recovery_attempts,
            tool_calls_total=adapter.call_count,
            tool_calls_successful=adapter.successful_call_count,
            initial_failure_class=observed_failure_class,
            final_recovery_state=final_state,
            execution_time_ms=elapsed_ms,
            notes=f"TurnResult={turn_result.conversation_state.value}",
            orchestrator_executed=("RECOVERY_STARTED" in turn_result.events),
            orchestrator_events=turn_result.events,
            turn_state=turn_result.conversation_state.value,
        )

    async def run_all(
        self, scenarios: Optional[list[ScenarioDefinition]] = None
    ) -> EvaluationReport:
        """Run all evaluation scenarios and compute aggregated metrics."""
        t0 = time.perf_counter()
        target_scenarios = scenarios or get_canonical_scenarios()
        results: list[ScenarioRunResult] = []

        for scn in target_scenarios:
            res = await self.run_scenario(scn)
            results.append(res)

        total = len(results)
        completed_results = [
            result
            for result in results
            if result.final_recovery_state == RecoveryState.RECOVERED
        ]
        completed_count = len(completed_results)
        preserved_count = sum(1 for r in completed_results if r.intent_preserved)
        adherent_count = sum(1 for r in results if r.recovery_succeeded)
        auto_recovered_count = sum(
            1 for r in completed_results if r.passed and r.orchestrator_executed
        )
        clarified_count = sum(
            1
            for r in results
            if r.final_recovery_state == RecoveryState.NEEDS_USER_DECISION and r.passed
        )
        failed_count = sum(1 for r in results if not r.passed)
        hard_sat_count = sum(
            1 for r in completed_results if r.hard_constraints_satisfied
        )
        unsafe_count = sum(1 for r in results if r.unsafe_autonomous_action)
        human_count = sum(1 for r in results if r.human_intervention_required)
        unnecessary_count = sum(1 for r in results if r.unnecessary_clarification)
        mean_budget_dev = (
            sum(r.budget_deviation for r in completed_results) / completed_count * 100.0
            if completed_count
            else 0.0
        )
        affected_drifts = [r.upstream_price_surge for r in results if r.upstream_price_surge > 0]
        detected_upstream_surge = (
            sum(affected_drifts) / len(affected_drifts) * 100.0
            if affected_drifts
            else 0.0
        )
        mean_attempts = sum(r.recovery_attempts for r in results) / total if total else 0.0
        total_tool_calls = sum(r.tool_calls_total for r in results)
        total_successful_calls = sum(r.tool_calls_successful for r in results)
        adapter_success_ratio = total_successful_calls / max(1, total_tool_calls)
        completed_tool_calls = sum(r.tool_calls_total for r in completed_results)
        mean_completed_tool_calls = (
            completed_tool_calls / completed_count if completed_count else 0.0
        )

        metrics = EvaluationMetrics(
            intent_preservation_rate=round(
                preserved_count / completed_count, 4
            ) if completed_count else 0.0,
            task_completion_rate=round(completed_count / total, 4),
            policy_adherence_rate=round(adherent_count / total, 4),
            autonomous_recovery_rate=round(auto_recovered_count / total, 4),
            safe_clarification_rate=round(clarified_count / total, 4),
            failed_scenario_rate=round(failed_count / total, 4),
            hard_constraint_satisfaction=round(
                hard_sat_count / completed_count, 4
            ) if completed_count else 0.0,
            unsafe_autonomous_action_rate=round(unsafe_count / total, 4),
            human_intervention_rate=round(human_count / total, 4),
            unnecessary_clarification_rate=round(unnecessary_count / total, 4),
            autonomous_budget_overrun_pct=round(mean_budget_dev, 2),
            detected_upstream_surge_pct=round(detected_upstream_surge, 2),
            mean_recovery_attempts=round(mean_attempts, 2),
            adapter_call_success_ratio=round(adapter_success_ratio, 4),
            mean_tool_calls_per_completed_task=round(mean_completed_tool_calls, 2),
        )

        return EvaluationReport(
            total_scenarios=total,
            results=results,
            metrics=metrics,
            duration_seconds=time.perf_counter() - t0,
        )


async def main() -> None:
    """CLI entrypoint for running the GROCER evaluation harness."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    harness = EvaluationHarness()
    report = await harness.run_all()
    print(report.format_text())
    if not report.is_healthy:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
