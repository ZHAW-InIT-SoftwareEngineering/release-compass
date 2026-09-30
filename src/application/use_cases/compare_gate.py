from uuid import UUID

from src.application.ports.outbound.report_reader import ReportReader
from src.domain.deltas.comparison import compute_report_deltas
from src.domain.deltas.gate_deltas import GateDeltas
from src.domain.gates.gate import Gate


def compare_gate(
    report_id: UUID,
    baseline_report_id: UUID,
    report_reader: ReportReader,
    gate_type: type[Gate],
) -> GateDeltas:
    """Load reports and return a comparison for exactly one gate of the selected type."""

    current_report = report_reader.get_by_id(report_id)
    if current_report is None:
        raise LookupError(f"Current report {report_id} was not found")
    baseline_report = report_reader.get_by_id(baseline_report_id)
    if baseline_report is None:
        raise LookupError(f"Baseline report {baseline_report_id} was not found")
    return compute_report_deltas(current_report, baseline_report, gate_type)
