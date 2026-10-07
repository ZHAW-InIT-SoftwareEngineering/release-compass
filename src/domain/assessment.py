"""Shared assessment result contracts and gate-agnostic operations."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from src.domain.gates.gate import Gate

Outcome = Literal["pass", "fail", "unknown"]


@dataclass(frozen=True)
class SourceAssessment:
    name: str
    source: str
    penalty: float | None
    weight: float | None
    excluded: bool = False
    reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricAcceptance:
    outcome: Outcome
    score: float | None
    threshold: float
    source: str
    reason: str | None = None
    sources: list[SourceAssessment] = field(default_factory=list)
    provider_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateAcceptance:
    outcome: Outcome
    metrics: dict[str, MetricAcceptance] = field(default_factory=dict)
    reason: str | None = None


@dataclass(frozen=True)
class GateDefinition:
    gate_type: type[Gate]
    assess: Callable[[Gate], GateAcceptance]
    compare: Callable[[Gate, Gate | None], dict[str, Any]]
    policy_version: str


def combine_outcomes(outcomes: list[Outcome]) -> Outcome:
    if "fail" in outcomes:
        return "fail"
    return (
        "pass" if outcomes and all(value == "pass" for value in outcomes) else "unknown"
    )


def compare_acceptance_scores(
    current: GateAcceptance,
    baseline: GateAcceptance | None,
) -> dict[str, Any]:
    values = {}
    for name, metric in current.metrics.items():
        prior = baseline.metrics.get(name) if baseline else None
        delta = (
            metric.score - prior.score
            if metric.score is not None
            and prior is not None
            and prior.score is not None
            else None
        )
        reason = (
            "No prior passing baseline"
            if baseline is None
            else "Missing current or baseline score"
            if delta is None
            else None
        )
        values[name] = {
            "current": metric.score,
            "baseline": prior.score if prior else None,
            "unit": "score_0_to_1",
            "absolute_delta": delta,
            "relative_delta_percent": (
                delta / abs(prior.score) * 100
                if delta is not None
                and prior
                and prior.score is not None
                and prior.score != 0
                else None
            ),
            "current_source": metric.source,
            "baseline_source": prior.source if prior else None,
            "unavailable_reason": reason,
            "relative_unavailable_reason": reason
            or ("Zero baseline" if prior and prior.score == 0 else None),
        }
    return values
