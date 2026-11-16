from collections.abc import Mapping
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
    (today an ontology knowledge base, ADR 0013).
    """

    # Import (ADR 0008)

    def import_state(self) -> ImportState: ...

    def get_by_fingerprint(self, fingerprint: str) -> Report | None:
        """The stored report's import fields; gates are not rebuilt."""
        ...

    def save_import_batch(
        self, reports: list[Report], aliases: dict[UUID, list[str]]
    ) -> None:
        """Store new reports and add alias paths to stored ones, all or nothing."""
        ...

    # Assessment (ADR 0012), one version at a time

    def open_assessment(self, version: str) -> None: ...

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

    def save(self) -> None: ...
