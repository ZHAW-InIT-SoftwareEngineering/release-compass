"""Composition of the Performance assessment policy and generic service."""

from src.application.ports.outbound.report_history import ReportHistory
from src.application.use_cases.assess_reports import AssessmentService
from src.configs.gates.performance.performance_gate import PerformanceGateConfig
from src.domain.assessment import GateAcceptance, GateDefinition
from src.domain.deltas.performance_comparison import compare_performance_values
from src.domain.gates.gate import Gate
from src.domain.gates.performance.assessment import POLICY_VERSION, assess_performance
from src.domain.gates.performance.performance_gate import PerformanceGate


def build_performance_assessment_service(
    repository: ReportHistory,
    config: PerformanceGateConfig,
) -> AssessmentService:
    """Wire the Performance policy into the gate-agnostic assessment service."""
    thresholds = {name: value.score for name, value in vars(config.metrics).items()}

    def assess(gate: Gate) -> GateAcceptance:
        if not isinstance(gate, PerformanceGate):
            raise TypeError("Expected PerformanceGate")
        return assess_performance(gate, thresholds)

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
            "performance": config.model_dump(),
            "policy_version": POLICY_VERSION,
        },
    )
