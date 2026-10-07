"""Canonical domain models for the performance gate."""

from dataclasses import dataclass, field

from src.domain.gates.gate import Gate


@dataclass
class ViolationPeriod:
    start_time: str
    end_time: str
    duration_seconds: float
    mean_value: float | None = None
    max_value: float | None = None
    violation_type: str | None = None


@dataclass
class MetricSummary:
    """Summary statistics shared by response time, CPU, and memory metrics."""

    source: str
    unit: str
    observation_count: int
    duration_seconds: float
    start_time: str | None = None
    end_time: str | None = None
    mean: float | None = None
    p50: float | None = None
    p90: float | None = None
    maximum: float | None = None
    target_nfr: float | None = None
    violation_count: int | None = None
    violation_rate_percent: float | None = None
    violation_periods: list[ViolationPeriod] = field(default_factory=list)
    supporting_evidence: dict[str, object] = field(default_factory=dict)


@dataclass
class ThresholdConfiguration:
    amber_violation_rate_percent: float | None = None
    red_violation_rate_percent: float | None = None
    amber_source: str | None = None
    red_source: str | None = None


@dataclass
class MetricAssessment:
    status: int | None = None
    threshold_configuration: ThresholdConfiguration | None = None
    status_reason: str | None = None


@dataclass
class ResponseTimeMetric(MetricSummary):
    assessment: MetricAssessment = field(default_factory=MetricAssessment)


@dataclass
class RequestOutcomes:
    total_requests: int
    failed_requests: int
    passed_requests: int
    failure_rate_percent: float
    http_code_histogram: dict[str, int] = field(default_factory=dict)


@dataclass
class TransactionPerformance:
    name: str
    response_time: ResponseTimeMetric | None
    request_outcomes: RequestOutcomes | None = None
    nfr_status: int | None = None
    throughput: ThroughputMetric | None = None


@dataclass
class ThroughputMetric:
    source: str
    unit: str
    observation_count: int | None = None
    target_nfr: float | None = None
    tps: float | None = None
    mean: float | None = None
    violation_count: int | None = None
    violation_rate_percent: float | None = None
    duration_seconds: float | None = None
    start_time: str | None = None
    end_time: str | None = None
    assessment: MetricAssessment = field(default_factory=MetricAssessment)
    supporting_evidence: dict[str, object] = field(default_factory=dict)


@dataclass
class ResourceMetric:
    """CPU or memory summary for the run or a service/component."""

    summary: MetricSummary
    assessment: MetricAssessment = field(default_factory=MetricAssessment)
    timeseries: list[dict[str, object]] = field(default_factory=list)
    linear_trend: list[dict[str, object]] = field(default_factory=list)


@dataclass
class PerformanceGate(Gate):
    """Performance evidence normalized from a single report/run."""

    response_time: ResponseTimeMetric | None = None
    throughput: ThroughputMetric | None = None
    request_outcomes: RequestOutcomes | None = None
    transactions: dict[str, TransactionPerformance] = field(default_factory=dict)
    cpu: ResourceMetric | None = None
    cpu_components: dict[str, ResourceMetric] = field(default_factory=dict)
    memory: ResourceMetric | None = None
    memory_components: dict[str, ResourceMetric] = field(default_factory=dict)
    provider_assessments: dict[str, object] = field(default_factory=dict)
