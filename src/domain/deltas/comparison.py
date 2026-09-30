from dataclasses import fields, is_dataclass
from typing import Any

from src.domain.deltas.gate_deltas import GateDeltas, NumericDelta
from src.domain.gates.gate import Gate
from src.domain.report import Report


_NON_DELTA_FIELDS = {
    "supporting_evidence",
    "timeseries",
    "linear_trend",
    "violation_periods",
    "status",
    "nfr_status",
}


def _gate_for_type(report: Report, gate_type: type[Gate]) -> Gate:
    matches = [gate for gate in report.gates if type(gate) is gate_type]
    if not matches:
        raise ValueError(f"Report {report.report_id} has no {gate_type.__name__} gate")
    if len(matches) > 1:
        raise ValueError(f"Report {report.report_id} has multiple {gate_type.__name__} gates")
    return matches[0]


def _numeric_values(value: Any, prefix: str = "") -> dict[str, int | float]:
    values: dict[str, int | float] = {}
    if is_dataclass(value) and not isinstance(value, type):
        for item in fields(value):
            if item.name in _NON_DELTA_FIELDS:
                continue
            key = f"{prefix}.{item.name}" if prefix else item.name
            values.update(_numeric_values(getattr(value, item.name), key))
    elif isinstance(value, dict):
        for name, item in value.items():
            key = f"{prefix}.{name}" if prefix else str(name)
            values.update(_numeric_values(item, key))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        values[prefix] = value
    return values


def compute_report_deltas(
    current_report: Report,
    baseline_report: Report,
    gate_type: type[Gate],
) -> GateDeltas:
    """Compare one gate type; numeric deltas are current minus baseline."""

    current_gate = _gate_for_type(current_report, gate_type)
    baseline_gate = _gate_for_type(baseline_report, gate_type)
    current_values = _numeric_values(current_gate)
    baseline_values = _numeric_values(baseline_gate)

    numeric_deltas = {
        name: NumericDelta(
            baseline=baseline_values.get(name),
            current=current_values.get(name),
            delta=(current_values[name] - baseline_values[name])
            if name in current_values and name in baseline_values
            else None,
        )
        for name in sorted(current_values.keys() | baseline_values.keys())
    }
    return GateDeltas(
        gate_type=gate_type.__name__,
        baseline=baseline_gate,
        current=current_gate,
        numeric_deltas=numeric_deltas,
    )
