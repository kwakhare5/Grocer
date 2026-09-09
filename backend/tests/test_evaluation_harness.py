"""Tests for the Phase 8 GROCER v2 evaluation framework and 9 core metrics (Spec §16, §20)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from backend.evaluation.harness import EvaluationHarness, EvaluationMetrics, EvaluationReport
from backend.evaluation.scenarios import get_canonical_scenarios
from backend.intent.recovery import FailureClass, RecoveryState


@pytest.mark.asyncio
async def test_evaluation_harness_runs_all_scenarios() -> None:
    """The evaluation harness executes every canonical scenario without exceptions."""
    harness = EvaluationHarness()
    scenarios = get_canonical_scenarios()
    assert len(scenarios) == 10

    report = await harness.run_all(scenarios)
    assert isinstance(report, EvaluationReport)
    assert report.total_scenarios == 10
    assert len(report.results) == 10


@pytest.mark.asyncio
async def test_evaluation_metrics_separate_safe_halts_from_preserved_intent() -> None:
    """A detected violation is not relabelled as a satisfied final basket."""
    harness = EvaluationHarness()
    report = await harness.run_all()
    metrics = report.metrics

    assert metrics.unsafe_autonomous_action_rate == 0.0, "Unsafe autonomous action rate must be 0%"
    assert metrics.unnecessary_clarification_rate == 0.0, "Unnecessary clarification rate must be 0%"
    assert metrics.autonomous_budget_overrun_pct <= 0.0, "Autonomous budget overrun must be <= 0%"
    assert metrics.policy_adherence_rate == 1.0
    assert metrics.failed_scenario_rate == 0.0
    assert metrics.mean_recovery_attempts <= 2.0
    assert metrics.intent_preservation_rate == 1.0
    assert metrics.hard_constraint_satisfaction == 1.0
    assert metrics.task_completion_rate == 0.5
    assert metrics.autonomous_recovery_rate == 0.4

    budget_drift = next(r for r in report.results if r.scenario_id == "SCN-04")
    assert budget_drift.final_recovery_state == RecoveryState.NEEDS_USER_DECISION
    assert budget_drift.recovery_succeeded is True
    assert budget_drift.hard_constraints_satisfied is False
    assert budget_drift.intent_preserved is False
    assert budget_drift.unsafe_autonomous_action is False


@pytest.mark.asyncio
async def test_evaluation_harness_exercises_production_orchestrator() -> None:
    """Proves that the evaluation harness executes the actual production orchestration path."""
    harness = EvaluationHarness()
    report = await harness.run_all()

    for r in report.results:
        if r.scenario_id == "SCN-09":
            assert r.orchestrator_executed is False
            assert "RECOVERY_STARTED" not in r.orchestrator_events
        else:
            assert r.orchestrator_executed is True, f"{r.scenario_id} did not execute orchestrator recovery"
            assert "RECOVERY_STARTED" in r.orchestrator_events, f"{r.scenario_id} missing RECOVERY_STARTED event"
        assert r.turn_state in ("AWAITING_CONFIRMATION", "NEEDS_DECISION")


def test_evaluation_report_formatting() -> None:
    """Report text formatting produces well-formed structured summary."""
    from backend.evaluation.harness import ScenarioRunResult
    from backend.intent.recovery import FailureClass, RecoveryState

    metrics = EvaluationMetrics(
        intent_preservation_rate=1.0,
        policy_adherence_rate=1.0,
        hard_constraint_satisfaction=1.0,
        unsafe_autonomous_action_rate=0.0,
        human_intervention_rate=0.625,
        unnecessary_clarification_rate=0.0,
        mean_recovery_attempts=1.0,
        adapter_call_success_ratio=0.957,
        mean_tool_calls_per_completed_task=3.0,
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
    assert "Hard Constraints (completed):" in formatted
    assert "100.0%" in formatted
    assert "Unsafe Recovery Mutation Rate:       0.0%" in formatted
    assert "Adapter Call Success Ratio:         95.7%" in formatted
    assert "Mean Calls / Completed Task:      3.00" in formatted


@pytest.mark.asyncio
async def test_observed_failure_class_is_not_copied_from_scenario_oracle() -> None:
    scenario = replace(
        get_canonical_scenarios()[0],
        expected_failure_class=FailureClass.BUDGET_DRIFT,
    )

    result = await EvaluationHarness().run_scenario(scenario)

    assert result.initial_failure_class == FailureClass.ITEM_UNAVAILABLE
    assert result.recovery_succeeded is False


def test_report_failure_requires_policy_agreement() -> None:
    from backend.evaluation.harness import ScenarioRunResult

    result = ScenarioRunResult(
        scenario_id="SCN-X",
        scenario_name="Wrong oracle result",
        intent_preserved=True,
        recovery_succeeded=False,
        hard_constraints_satisfied=True,
        unsafe_autonomous_action=False,
        human_intervention_required=False,
        unnecessary_clarification=False,
        budget_deviation=0.0,
        recovery_attempts=1,
        tool_calls_total=1,
        tool_calls_successful=1,
        initial_failure_class=FailureClass.ITEM_UNAVAILABLE,
        final_recovery_state=RecoveryState.RECOVERED,
        execution_time_ms=1.0,
    )
    report = EvaluationReport(
        total_scenarios=1,
        results=[result],
        metrics=EvaluationMetrics(policy_adherence_rate=0.0),
        duration_seconds=0.01,
    )

    assert report.is_healthy is False
    assert "[FAIL] SCN-X" in report.format_text()


def test_metric_defaults_do_not_claim_unrun_success() -> None:
    metrics = EvaluationMetrics()

    assert metrics.intent_preservation_rate == 0.0
    assert metrics.human_intervention_rate == 0.0
    assert metrics.adapter_call_success_ratio == 0.0
    assert metrics.mean_tool_calls_per_completed_task == 0.0
    assert metrics.policy_adherence_rate == 0.0
    assert metrics.hard_constraint_satisfaction == 0.0
