"""Incrementally import static report sources, independently of client configuration."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from src.application.ports.outbound.report_history import ReportHistory
from src.application.ports.outbound.report_ingestion import ReportIngestionPort
from src.domain.history import generated_at, report_order
from src.domain.report import Report


@dataclass(frozen=True)
class ReportInput:
    path: Path
    generated_at_date: str | None = None
    generated_at_time: str | None = None


def import_reports(
    inputs: list[ReportInput],
    ingestion: ReportIngestionPort,
    repository: ReportHistory,
) -> list[Report]:
    existing = repository.list_reports()
    latest = max((generated_at(report) for report in existing), default=None)
    sequence = max((report.ingestion_sequence or 0 for report in existing), default=0)
    pending: dict[str, Report] = {}
    aliases: dict[UUID, list[str]] = {}
    selected: list[Report] = []
    for item in inputs:
        source_path = str(item.path)
        fingerprint = sha256(item.path.read_bytes()).hexdigest()
        report = pending.get(fingerprint) or repository.get_by_fingerprint(fingerprint)
        if report is not None:
            aliases.setdefault(report.report_id, []).append(source_path)
            selected.append(report)
            continue
        report = ingestion.ingest(item.path)
        # Static sources must not change between hashing and normalization.
        if sha256(item.path.read_bytes()).hexdigest() != fingerprint:
            raise ValueError(f"Report changed during import: {item.path}")
        if (report.generated_at_date is None) != (report.generated_at_time is None):
            raise ValueError(
                f"Report {item.path} must provide both generated-at fields"
            )
        if report.generated_at_date is None:
            if (item.generated_at_date is None) != (item.generated_at_time is None):
                raise ValueError(
                    f"Report configuration {item.path} must provide both generated-at fields"
                )
            now = datetime.now(UTC)
            report.generated_at_date = item.generated_at_date or now.date().isoformat()
            report.generated_at_time = item.generated_at_time or now.time().isoformat()
        if latest is not None and generated_at(report) < latest:
            raise ValueError(f"Backdated import rejected: {item.path}")
        generated_at(report)
        sequence += 1
        report.ingestion_sequence = sequence
        report.source_fingerprint = fingerprint
        report.source_paths = [source_path]
        pending[fingerprint] = report
        selected.append(report)
    repository.save_import_batch(sorted(pending.values(), key=report_order), aliases)
    return selected
