"""Tests for the Phase 8 GROCER v2 evaluation framework and 9 core metrics (Spec §16, §20)."""
from __future__ import annotations

import pytest

from backend.evaluation.harness import EvaluationHarness, EvaluationMetrics, EvaluationReport
from backend.evaluation.scenarios import get_canonical_scenarios


@pytest.mark.asyncio
async def test_evaluation_harness_runs_all_scenarios() -> None:
    """The evaluation harness must execute all 8 canonical scenarios without exceptions."""
    harness = EvaluationHarness()
    scenarios = get_canonical_scenarios()
    assert len(scenarios) == 8

    report = await harness.run_all(scenarios)
    assert isinstance(report, EvaluationReport)
    assert report.total_scenarios == 8
    assert len(report.results) == 8


@pytest.mark.asyncio
async def test_evaluation_metrics_satisfy_strict_safety_invariants() -> None:
    """Proves Spec §16 non-negotiable metric thresholds and separated semantics:
    - hard_constraint_satisfaction == 100.0%
    - unsafe_autonomous_action_rate == 0.0%
    - unnecessary_clarification_rate == 0.0%
    - intent_preservation_rate >= 95.0%
    - policy_adherence_rate == 100.0%
    - autonomous_recovery_rate == 37.5% (SCN-01, SCN-03, SCN-06)
    - safe_clarification_rate == 62.5% (SCN-02, SCN-04, SCN-05, SCN-07, SCN-08)
    - failed_scenario_rate == 0.0%
    - commerce_adapter_call_efficiency >= 80.0%
    """
    harness = EvaluationHarness()
    report = await harness.run_all()
    metrics = report.metrics

    # Strict safety invariants
    assert metrics.hard_constraint_satisfaction == 1.0, "Hard constraint satisfaction must be 100%"
    assert metrics.unsafe_autonomous_action_rate == 0.0, "Unsafe autonomous action rate must be 0%"
    assert metrics.unnecessary_clarification_rate == 0.0, "Unnecessary clarification rate must be 0%"
    assert metrics.autonomous_budget_overrun_pct <= 0.0, "Autonomous budget overrun must be <= 0%"

    # Separated metric semantics
    assert metrics.intent_preservation_rate == 1.0
    assert metrics.policy_adherence_rate == 1.0
    assert metrics.autonomous_recovery_rate == 0.375  # 3/8 recovered autonomously
    assert metrics.safe_clarification_rate == 0.625  # 5/8 safely clarified per policy
    assert metrics.failed_scenario_rate == 0.0
    assert metrics.commerce_adapter_call_efficiency >= 0.80
    assert metrics.mean_recovery_attempts <= 2.0


@pytest.mark.asyncio
async def test_evaluation_harness_exercises_production_orchestrator() -> None:
    """Proves that the evaluation harness executes the actual production orchestration path."""
    harness = EvaluationHarness()
    report = await harness.run_all()

    for r in report.results:
        assert r.orchestrator_executed is True, f"{r.scenario_id} did not execute orchestrator recovery"
        assert "RECOVERY_STARTED" in r.orchestrator_events, f"{r.scenario_id} missing RECOVERY_STARTED event"
        assert r.turn_state in ("AWAITING_CONFIRMATION", "NEEDS_DECISION")


def test_evaluation_report_formatting() -> None:
    """Report text formatting produces well-formed structured summary."""
    from backend.evaluation.harness import ScenarioRunResult
    from backend.intent.recovery import FailureClass, RecoveryState

    metrics = EvaluationMetrics(
        intent_preservation_rate=1.0,
        recovery_success_rate=1.0,
        hard_constraint_satisfaction=1.0,
        unsafe_autonomous_action_rate=0.0,
        human_intervention_rate=0.625,
        unnecessary_clarification_rate=0.0,
        mean_budget_deviation_pct=0.0,
        mean_recovery_attempts=1.0,
        mcp_tool_call_efficiency=0.957,
        autonomous_budget_overrun_pct=0.0,
        detected_upstream_surge_pct=6.2,
    )
    report = EvaluationReport(
        total_scenarios=1,
        results=[
            ScenarioRunResult(
                scenario_id="SCN-01",
                scenario_name="Test Scenario",
                intent_preserved=True,
                recovery_succeeded=True,
                hard_constraints_satisfied=True,
                unsafe_autonomous_action=False,
                human_intervention_required=False,
                unnecessary_clarification=False,
                budget_deviation=0.0,
                recovery_attempts=1,
                tool_calls_total=3,
                tool_calls_successful=3,
                initial_failure_class=FailureClass.ITEM_UNAVAILABLE,
                final_recovery_state=RecoveryState.RECOVERED,
                execution_time_ms=1.5,
            )
        ],
        metrics=metrics,
        duration_seconds=0.01,
    )

    formatted = report.format_text()
    assert "GROCER v2 RELIABILITY & INTENT EVALUATION REPORT" in formatted
    assert "Hard-Constraint Satisfaction:      100.0%" in formatted
    assert "Unsafe Autonomous Action Rate:       0.0%" in formatted
