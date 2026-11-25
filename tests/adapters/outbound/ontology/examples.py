"""Small example data shared by the ontology adapter and vocabulary tests."""

from uuid import UUID

from src.domain.assessment import GateAcceptance
from src.domain.gates.performance.measurements import performance_measure
from src.domain.gates.performance.performance_gate import (
    PerformanceGate,
    RequestOutcomes,
    ResponseTimeMetric,
    ThroughputMetric,
    TransactionPerformance,
)
from src.domain.report import Report
from src.domain.scoring import score_gate
from src.domain.targets import MetricTarget, TargetRange

REPORT_ID = UUID("3f2a6c1e-0000-4000-8000-000000000001")
VERSION = "v1"
POLICY = "target-ranges-v1"

TARGETS = {
    "response_time": MetricTarget(
        "response_time", "p90", "ms", TargetRange(None, 1000), 0.8
    ),
    "throughput": MetricTarget("throughput", "tps", "req/s", TargetRange(40, None), 1),
}


def performance_gate() -> PerformanceGate:
    """Login is fast, Search is slow, Logout has no requests."""
    gate = PerformanceGate(throughput=ThroughputMetric("overall", "req/s", tps=50))
    for name, requests, p90 in (
        ("Login", 300, 800.5),
        ("Search", 100, 2500.0),
        ("Logout", 0, None),
    ):
        gate.transactions[name] = TransactionPerformance(
            name,
            ResponseTimeMetric("locust", "ms", requests, 60, p90=p90),
            RequestOutcomes(requests, 0, requests, 0),
        )
    return gate


def report(**overrides) -> Report:
    values: dict = {
        "report_id": REPORT_ID,
        "source_path": "data/raw/report.html",
        "generated_at_date": "2026-11-09",
        "generated_at_time": "14:03:00",
        "source_fingerprint": "9b1c",
        "ingestion_sequence": 4,
        "source_paths": ["data/raw/report.html", "data/raw/renamed.html"],
        "gates": [performance_gate()],
    }
    return Report(**(values | overrides))


def acceptance() -> GateAcceptance:
    """Response time fails (0.75 < 0.8), throughput passes, Logout is excluded."""
    return score_gate(TARGETS, performance_measure(performance_gate()))
