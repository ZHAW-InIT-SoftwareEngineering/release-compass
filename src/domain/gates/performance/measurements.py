"""Expose a PerformanceGate's values as gate-agnostic measurements.

This is the only module that knows which performance metrics are scored.
"""

from src.domain.gates.performance.performance_gate import (
    PerformanceGate,
    TransactionPerformance,
)
from src.domain.scoring import Measure, Measurement

# Metrics a target may name, and the fields each may aggregate on.
SUPPORTED = {
    "response_time": ("mean", "p50", "p90", "maximum"),
    "request_outcomes": ("failure_rate_percent",),
    "throughput": ("tps",),
}
# Measured once for the whole run; all other metrics per transaction, since
# per-transaction throughput reflects the load mix, not system quality.
RUN_METRICS = ("throughput",)


def _read(
    holder: PerformanceGate | TransactionPerformance, metric: str, aggregation: str
) -> tuple[float | None, str | None, float | None]:
    """Return (value, unit, weight) of ``metric`` on a run or transaction."""
    match metric:
        case "response_time" if holder.response_time is not None:
            response_time = holder.response_time
            return (
                getattr(response_time, aggregation),
                response_time.unit,
                response_time.observation_count,
            )
        case "request_outcomes" if holder.request_outcomes is not None:
            outcomes = holder.request_outcomes
            return getattr(outcomes, aggregation), "%", outcomes.total_requests
        case "throughput" if holder.throughput is not None:
            return getattr(holder.throughput, aggregation), holder.throughput.unit, 1
    return None, None, None


def performance_measure(gate: PerformanceGate) -> Measure:
    def measure(metric: str, aggregation: str) -> list[Measurement]:
        if aggregation not in SUPPORTED.get(metric, ()):
            raise ValueError(f"Unsupported performance measure {metric}.{aggregation}")
        if metric in RUN_METRICS:
            return [
                Measurement(
                    "overall",
                    f"{metric}.{aggregation}",
                    *_read(gate, metric, aggregation),
                )
            ]
        return [
            Measurement(
                name,
                f"transactions[{name}].{metric}.{aggregation}",
                *_read(transaction, metric, aggregation),
            )
            for name, transaction in sorted(gate.transactions.items())
        ]

    return measure
