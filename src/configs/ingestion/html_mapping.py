"""Configuration mapping a source's HTML-embedded JSON onto domain models.

Every key is required. ``null`` states explicitly that the source does not
provide a value, so a forgotten field fails validation instead of silently
becoming empty. Field names mirror the domain dataclasses they build.

Values are one of:

- a path into the embedded JSON, e.g. ``stats[name=Total]["p0.9"]``
- ``{const: <value>}``
- ``{transform: <name>, args: [<value>, ...]}``
"""

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Const(_Strict):
    const: JsonValue


TRANSFORM_ARITY = {
    "subtract": 2,
    "percent": 2,
    "seconds_between": 2,
    "date_of": 1,
    "time_of": 1,
}


class Transform(_Strict):
    transform: Literal["subtract", "percent", "seconds_between", "date_of", "time_of"]
    args: list[Value]

    @model_validator(mode="after")
    def _check_arity(self):
        expected = TRANSFORM_ARITY[self.transform]
        if len(self.args) != expected:
            raise ValueError(
                f"{self.transform} takes {expected} argument(s), got {len(self.args)}"
            )
        return self


type Value = str | Const | Transform


class ListMapping[T: BaseModel](_Strict):
    """Build one item per element of the list at ``for_each``."""

    for_each: str
    item: T


class DictMapping[T: BaseModel](_Strict):
    """Build one item per element of the list at ``for_each``, keyed by ``key``."""

    for_each: str
    key: Value
    item: T


class JsAssignmentExtractor(_Strict):
    """JSON object literal assigned in a script, e.g. ``window.data = {...}``."""

    kind: Literal["js_assignment"]
    variable: str


class AttributeExtractor(_Strict):
    """JSON stored in an HTML attribute, e.g. ``<div data-raw="{...}">``."""

    kind: Literal["attribute"]
    attribute: str


type Extractor = Annotated[
    JsAssignmentExtractor | AttributeExtractor, Field(discriminator="kind")
]


class ThresholdConfigurationMapping(_Strict):
    amber_violation_rate_percent: Value | None
    red_violation_rate_percent: Value | None
    amber_source: Value | None
    red_source: Value | None


class MetricAssessmentMapping(_Strict):
    status: Value | None
    threshold_configuration: ThresholdConfigurationMapping | None
    status_reason: Value | None


class ViolationPeriodMapping(_Strict):
    start_time: Value
    end_time: Value
    duration_seconds: Value
    mean_value: Value | None
    max_value: Value | None
    violation_type: Value | None


class MetricSummaryMapping(_Strict):
    source: Value
    unit: Value
    observation_count: Value
    duration_seconds: Value
    start_time: Value | None
    end_time: Value | None
    mean: Value | None
    p50: Value | None
    p90: Value | None
    maximum: Value | None
    target_nfr: Value | None
    violation_count: Value | None
    violation_rate_percent: Value | None
    violation_periods: ListMapping[ViolationPeriodMapping] | None
    supporting_evidence: dict[str, Value]


class ResponseTimeMetricMapping(MetricSummaryMapping):
    assessment: MetricAssessmentMapping | None


class RequestOutcomesMapping(_Strict):
    total_requests: Value
    failed_requests: Value
    passed_requests: Value
    failure_rate_percent: Value
    http_code_histogram: Value | None


class ThroughputMetricMapping(_Strict):
    source: Value
    unit: Value
    observation_count: Value | None
    target_nfr: Value | None
    tps: Value | None
    mean: Value | None
    violation_count: Value | None
    violation_rate_percent: Value | None
    duration_seconds: Value | None
    start_time: Value | None
    end_time: Value | None
    assessment: MetricAssessmentMapping | None
    supporting_evidence: dict[str, Value]


class TransactionPerformanceMapping(_Strict):
    name: Value
    response_time: ResponseTimeMetricMapping | None
    request_outcomes: RequestOutcomesMapping | None
    throughput: ThroughputMetricMapping | None


class PerformanceGateMapping(_Strict):
    response_time: ResponseTimeMetricMapping | None
    throughput: ThroughputMetricMapping | None
    request_outcomes: RequestOutcomesMapping | None
    transactions: DictMapping[TransactionPerformanceMapping] | None


class ReportMapping(_Strict):
    generated_at_date: Value | None
    generated_at_time: Value | None


class HtmlMappingConfig(_Strict):
    extractor: Extractor
    report: ReportMapping
    performance_gate: PerformanceGateMapping


def load_html_mapping(path: Path) -> HtmlMappingConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
    return HtmlMappingConfig.model_validate(config_data)
