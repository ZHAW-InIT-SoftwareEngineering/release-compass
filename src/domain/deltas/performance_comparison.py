"""Compare defined performance measurements while retaining their units."""

from typing import Any

from src.domain.gates.performance.performance_gate import PerformanceGate

_SUMMARY_FIELDS = (
    "mean",
    "p50",
    "p90",
    "maximum",
    "target_nfr",
    "violation_count",
    "violation_rate_percent",
)


def _measurements(gate: PerformanceGate) -> dict[str, tuple[Any, str]]:
    values: dict[str, tuple[Any, str]] = {}

    def summary(prefix, value):
        if value is None:
            return
        for name in _SUMMARY_FIELDS:
            unit = (
                "count"
                if name == "violation_count"
                else "percent"
                if name == "violation_rate_percent"
                else value.unit
            )
            values[f"{prefix}.{name}"] = (getattr(value, name), unit)

    def throughput(prefix, value):
        if value is None:
            return
        for name in (
            "tps",
            "mean",
            "target_nfr",
            "violation_count",
            "violation_rate_percent",
        ):
            unit = (
                "count"
                if name == "violation_count"
                else ("percent" if name == "violation_rate_percent" else value.unit)
            )
            values[f"{prefix}.{name}"] = (getattr(value, name), unit)

    def outcomes(prefix, value):
        if value is None:
            return
        for name in (
            "total_requests",
            "passed_requests",
            "failed_requests",
            "failure_rate_percent",
        ):
            values[f"{prefix}.{name}"] = (
                getattr(value, name),
                "percent" if name == "failure_rate_percent" else "count",
            )
        for code, count in value.http_code_histogram.items():
            values[f"{prefix}.http_code_histogram.{code}"] = (count, "count")

    summary("response_time", gate.response_time)
    throughput("throughput", gate.throughput)
    outcomes("request_outcomes", gate.request_outcomes)
    for name, tx in gate.transactions.items():
        prefix = f"transactions.{name}"
        summary(f"{prefix}.response_time", tx.response_time)
        throughput(f"{prefix}.throughput", tx.throughput)
        outcomes(f"{prefix}.request_outcomes", tx.request_outcomes)
    for metric in ("cpu", "memory"):
        overall = getattr(gate, metric)
        summary(metric, overall.summary if overall else None)
        for name, item in getattr(gate, f"{metric}_components").items():
            summary(f"{metric}_components.{name}", item.summary)
    return values


def compare_performance_values(
    current: PerformanceGate,
    baseline: PerformanceGate | None,
) -> dict[str, Any]:
    current_values = _measurements(current)
    baseline_values = _measurements(baseline) if baseline else {}
    numeric = {}
    for name in sorted(current_values.keys() | baseline_values.keys()):
        current_value, current_unit = current_values.get(name, (None, None))
        baseline_value, baseline_unit = baseline_values.get(name, (None, None))
        reason = (
            "No prior passing baseline"
            if baseline is None
            else "Missing current or baseline value"
            if current_value is None or baseline_value is None
            else "Incompatible units"
            if current_unit != baseline_unit
            else None
        )
        delta = (
            current_value - baseline_value
            if current_value is not None
            and baseline_value is not None
            and current_unit == baseline_unit
            else None
        )
        relative = (
            None
            if delta is None or baseline_value is None or baseline_value == 0
            else delta / abs(baseline_value) * 100
        )
        numeric[name] = {
            "current": current_value,
            "baseline": baseline_value,
            "current_unit": current_unit,
            "baseline_unit": baseline_unit,
            "absolute_delta": delta,
            "relative_delta_percent": relative,
            "unavailable_reason": reason,
            "relative_unavailable_reason": reason
            or ("Zero baseline" if baseline_value == 0 else None),
        }
    categorical = {}
    for name in sorted(
        current.transactions.keys()
        | (baseline.transactions.keys() if baseline else set())
    ):
        current_tx = current.transactions.get(name)
        baseline_tx = baseline.transactions.get(name) if baseline else None
        categorical[name] = {
            "current": current_tx.nfr_status if current_tx else None,
            "baseline": baseline_tx.nfr_status if baseline_tx else None,
        }
    return {"numeric": numeric, "transaction_nfr_status": categorical}
