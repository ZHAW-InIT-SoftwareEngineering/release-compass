from collections.abc import Collection, Mapping
from datetime import datetime
from typing import NamedTuple, Protocol
from uuid import UUID

from src.domain.assessment import GateAcceptance
from src.domain.report import Report
from src.domain.scoring import Measurement
from src.domain.targets import MetricTarget


class ImportState(NamedTuple):
    latest_generated_at: datetime | None
    max_ingestion_sequence: int


class ReportRepository(Protocol):
    """Stored reports and their assessment results.

    Methods are shaped by the use cases, independent of the storage technology
    (an ontology knowledge base, ADR 0013, or SQLite).
    """

    def import_state(self) -> ImportState: ...

    def get_by_fingerprint(self, fingerprint: str) -> Report | None:
        """The stored report's import fields; gates are not rebuilt."""
        ...

    def save_import_batch(
        self, reports: list[Report], aliases: dict[UUID, list[str]]
    ) -> None:
        """Store new reports and add alias paths to stored ones, all or nothing."""
        ...

    def open_assessment(self, version: str) -> None: ...

    def unassessed_reports(self) -> list[UUID]:
        """Reports without an outcome in the open version, oldest first (ADR 0006)."""
        ...

    def gate_types(self, report_id: UUID) -> set[str]: ...

    def measurements(
        self, report_id: UUID, gate_type: str, metric: str, statistic: str
    ) -> list[Measurement]:
        """A gate run's stored measurements, as src/domain/scoring.py reads them."""
        ...

    def add_gate_assessment(
        self,
        report_id: UUID,
        gate_type: str,
        acceptance: GateAcceptance,
        targets: Mapping[str, MetricTarget],
        policy_version: str,
    ) -> None: ...

    def apply_rules(
        self, report_id: UUID, required_gate_types: Collection[str]
    ) -> None:
        """Derive the report's history links, outcome and baselines.

        Runs after its gates are assessed and after every earlier report:
        previous report or root (ADR 0008), report outcome from the gate
        outcomes (ADR 0005), latest earlier passing report and gates (ADR 0006).
        """
        ...

    def save(self) -> None: ...
