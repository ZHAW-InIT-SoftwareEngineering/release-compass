"""Gate-agnostic scoring of measurements against target ranges (ADR 0012).

Gates supply measurements; this module never knows which metrics exist.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from src.domain.assessment import (
    GateAcceptance,
    MetricAcceptance,
    Outcome,
    SourceAssessment,
    combine_outcomes,
)
from src.domain.targets import MetricTarget

POLICY_VERSION = "target-ranges-v1"


@dataclass(frozen=True)
class Measurement:
    """One measured value of a metric, e.g. one transaction's p90."""

    source: str
    path: str
    value: float | None
    unit: str | None
    # Share of the metric this value represents, e.g. its request count.
    # Zero excludes the measurement; ``None`` makes the metric unknown.
    weight: float | None


# Returns the measurements of ``metric`` aggregated on ``aggregation``.
type Measure = Callable[[str, str], list[Measurement]]


def _assess(measurement: Measurement, target: MetricTarget) -> SourceAssessment:
    evidence = {
        "value": measurement.value,
        "unit": measurement.unit,
        "min": target.range.min,
        "max": target.range.max,
    }

    def result(penalty, *, excluded=False, reason=None):
        return SourceAssessment(
            measurement.source,
            measurement.path,
            penalty,
            measurement.weight,
            excluded,
            reason,
            evidence,
        )

    if measurement.weight == 0:
        return result(None, excluded=True, reason="No observations")
    if measurement.value is None or measurement.weight is None:
        return result(None, reason="Missing measured value")
    if measurement.unit != target.unit:
        return result(
            None,
            reason=(
                f"Unit {measurement.unit!r} does not match target unit {target.unit!r}"
            ),
        )
    return result(0.0 if target.range.contains(measurement.value) else 1.0)


def _accept(
    score: float | None,
    target: MetricTarget,
    sources: list[SourceAssessment],
    reason: str | None = None,
) -> MetricAcceptance:
    outcome: Outcome = (
        "unknown"
        if score is None
        else ("pass" if score >= target.min_score else "fail")
    )
    return MetricAcceptance(
        outcome, score, target.min_score, target.metric, reason, sources
    )


def score_metric(
    measurements: list[Measurement], target: MetricTarget
) -> MetricAcceptance:
    """Score the weighted share of measurements inside the target range."""
    sources = [_assess(item, target) for item in measurements]
    included = [item for item in sources if not item.excluded]
    if not included:
        return _accept(None, target, sources, "No eligible sources")
    if any(item.penalty is None for item in included):
        return _accept(
            None, target, sources, "An included source lacks an evaluable value"
        )
    total_weight = sum(item.weight or 0 for item in included)
    if total_weight <= 0:
        return _accept(None, target, sources, "No positive source weight")
    penalty = (
        sum((item.penalty or 0) * (item.weight or 0) for item in included)
        / total_weight
    )
    return _accept(1 - penalty, target, sources)


def score_gate(targets: Mapping[str, MetricTarget], measure: Measure) -> GateAcceptance:
    """Score every targeted metric; the gate passes only if all pass."""
    results = {
        name: score_metric(measure(target.metric, target.aggregation), target)
        for name, target in targets.items()
    }
    return GateAcceptance(
        combine_outcomes([item.outcome for item in results.values()]), results
    )
