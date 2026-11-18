"""Shared assessment result contracts and gate-agnostic operations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from src.domain.targets import MetricTarget

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
    """A required gate type and the targets its runs are scored against."""

    gate_type: str
    targets: Mapping[str, MetricTarget]
    policy_version: str


def combine_outcomes(outcomes: list[Outcome]) -> Outcome:
    if "fail" in outcomes:
        return "fail"
    return (
        "pass" if outcomes and all(value == "pass" for value in outcomes) else "unknown"
    )
