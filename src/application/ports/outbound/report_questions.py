"""Read side of the store: one method per competency question (ADR 0013).

Answers come from the open assessment version, so a chat never mixes
configurations (ADR 0008). Both the knowledge base and SQLite implement it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.assessment import Outcome
from src.domain.scoring import Measurement


@dataclass(frozen=True)
class ReportSummary:
    """Q1, Q2: what a report is and where it sits in history."""

    report_id: UUID
    generated_at: datetime
    ingestion_sequence: int
    source_paths: list[str]
    gate_types: list[str]
    # None: not assessed in the open version.
    outcome: Outcome | None
    is_root: bool | None
    previous_report_id: UUID | None


@dataclass(frozen=True)
class GateBaseline:
    gate_type: str
    baseline_report_id: UUID | None
    policy_version: str | None


@dataclass(frozen=True)
class Baselines:
    """Q3: the latest earlier passing report and, per gate, passing gate run."""

    report_id: UUID
    baseline_report_id: UUID | None
    gates: list[GateBaseline]


@dataclass(frozen=True)
class SourceResult:
    source: str
    value: float | None
    # None when excluded or not evaluable.
    meets_target: bool | None
    excluded: bool
    reason: str | None


@dataclass(frozen=True)
class MetricResult:
    metric: str
    statistic: str
    unit: str
    min: float | None
    max: float | None
    min_score: float
    score: float | None
    outcome: Outcome
    reason: str | None
    policy_version: str
    sources: list[SourceResult] = field(default_factory=list)


@dataclass(frozen=True)
class GateResult:
    """Q6: a gate's outcome with the targets and evidence behind it."""

    gate_type: str
    # None: the gate was not assessed (not required in this version).
    outcome: Outcome | None
    metrics: list[MetricResult] = field(default_factory=list)


class ReportQuestions(Protocol):
    def describe_report(self, report_id: UUID) -> ReportSummary | None: ...

    def baselines(self, report_id: UUID) -> Baselines | None: ...

    def measurements(
        self, report_id: UUID, gate_type: str, metric: str, statistic: str
    ) -> list[Measurement]:
        """Q5 input: one statistic of a gate run, compared in Python (ADR 0015)."""
        ...

    def gate_results(self, report_id: UUID) -> list[GateResult]:
        """Every gate of the report, ordered by gate type."""
        ...
