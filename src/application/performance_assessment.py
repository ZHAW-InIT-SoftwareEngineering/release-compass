"""Composition of the Performance gate with the gate-agnostic assessment."""

from src.application.ports.outbound.report_repository import ReportRepository
from src.application.use_cases.assess_reports import AssessmentService
from src.domain.assessment import GateDefinition
from src.domain.gates.performance.measurements import GATE_TYPE, SUPPORTED
from src.domain.scoring import POLICY_VERSION
from src.domain.targets import MetricTarget, check_targets


def build_performance_assessment_service(
    repository: ReportRepository,
    targets: dict[str, MetricTarget],
) -> AssessmentService:
    """Require the Performance gate, scored against the configured targets."""
    check_targets(targets, SUPPORTED)
    return AssessmentService(
        repository, [GateDefinition(GATE_TYPE, targets, POLICY_VERSION)]
    )
