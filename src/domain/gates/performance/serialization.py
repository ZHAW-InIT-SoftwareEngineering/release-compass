"""Dataclass types required to serialize Performance gate payloads."""

from src.domain.gates.performance.performance_gate import (
    MetricAssessment,
    MetricSummary,
    PerformanceGate,
    RequestOutcomes,
    ResourceMetric,
    ResponseTimeMetric,
    ThresholdConfiguration,
    ThroughputMetric,
    TransactionPerformance,
    ViolationPeriod,
)

PERFORMANCE_DOMAIN_TYPES = (
    MetricAssessment,
    MetricSummary,
    PerformanceGate,
    RequestOutcomes,
    ResourceMetric,
    ResponseTimeMetric,
    ThresholdConfiguration,
    ThroughputMetric,
    TransactionPerformance,
    ViolationPeriod,
)
