"""Composition of the Performance gate with the generic scoring and service."""

from dataclasses import asdict

from src.application.ports.outbound.report_history import ReportHistory
from src.application.use_cases.assess_reports import AssessmentService
from src.domain.assessment import GateAcceptance, GateDefinition
from src.domain.deltas.performance_comparison import compare_performance_values
from src.domain.gates.gate import Gate
from src.domain.gates.performance.measurements import SUPPORTED, performance_measure
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.domain.scoring import POLICY_VERSION, score_gate
from src.domain.targets import MetricTarget, check_targets


def build_performance_assessment_service(
    repository: ReportHistory,
    targets: dict[str, MetricTarget],
) -> AssessmentService:
    """Wire the Performance gate into the gate-agnostic assessment service."""
    check_targets(targets, SUPPORTED)

    def assess(gate: Gate) -> GateAcceptance:
        if not isinstance(gate, PerformanceGate):
            raise TypeError("Expected PerformanceGate")
        return score_gate(targets, performance_measure(gate))

    def compare(current: Gate, baseline: Gate | None) -> dict:
        if not isinstance(current, PerformanceGate) or (
            baseline is not None and not isinstance(baseline, PerformanceGate)
        ):
            raise TypeError("Expected PerformanceGate")
        return compare_performance_values(current, baseline)

    definition = GateDefinition(PerformanceGate, assess, compare, POLICY_VERSION)
    return AssessmentService(
        repository,
        [definition],
        {
            "performance": {name: asdict(target) for name, target in targets.items()},
            "policy_version": POLICY_VERSION,
        },
    )
