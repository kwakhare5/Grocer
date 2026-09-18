"""GROCER v2 Evaluation Harness Package (Spec §16, §20).

Automated reliability and intent preservation evaluation framework.
Calculates the 9 core reliability metrics across reproducible failure scenarios.
"""
from backend.evaluation.scenarios import ScenarioDefinition, get_canonical_scenarios
from backend.evaluation.harness import EvaluationHarness, EvaluationReport, EvaluationMetrics

__all__ = [
    "ScenarioDefinition",
    "get_canonical_scenarios",
    "EvaluationHarness",
    "EvaluationReport",
    "EvaluationMetrics",
]
