"""Incrementally import static report sources, independently of client configuration."""

from dataclasses import dataclass
from datetime import datetime
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


@dataclass
class _ImportBatch:
    latest_stored_at: datetime | None
    next_sequence: int
    pending: dict[str, Report]
    aliases: dict[UUID, list[str]]
    selected: list[Report]


def import_reports(
    inputs: list[ReportInput],
    ingestion: ReportIngestionPort,
    repository: ReportHistory,
) -> list[Report]:
    batch = _new_import_batch(repository)
    for item in inputs:
        _import_report(item, ingestion, repository, batch)
    _persist_import_batch(repository, batch)
    return batch.selected


def _new_import_batch(repository: ReportHistory) -> _ImportBatch:
    existing = repository.list_reports()
    return _ImportBatch(
        latest_stored_at=max(
            (generated_at(report) for report in existing), default=None
        ),
        next_sequence=max(
            (report.ingestion_sequence or 0 for report in existing), default=0
        ),
        pending={},
        aliases={},
        selected=[],
    )


def _import_report(
    item: ReportInput,
    ingestion: ReportIngestionPort,
    repository: ReportHistory,
    batch: _ImportBatch,
) -> None:
    fingerprint = _fingerprint(item.path)
    report = batch.pending.get(fingerprint) or repository.get_by_fingerprint(
        fingerprint
    )
    if report is not None:
        _reuse_report(report, item, batch)
        return

    report = ingestion.ingest(item.path)
    _ensure_source_unchanged(item.path, fingerprint)
    _apply_timestamp(report, item)
    _reject_backdated_report(report, item.path, batch.latest_stored_at)
    batch.next_sequence += 1
    report.ingestion_sequence = batch.next_sequence
    report.source_fingerprint = fingerprint
    report.source_paths = [str(item.path)]
    batch.pending[fingerprint] = report
    batch.selected.append(report)


def _fingerprint(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _reuse_report(report: Report, item: ReportInput, batch: _ImportBatch) -> None:
    batch.aliases.setdefault(report.report_id, []).append(str(item.path))
    batch.selected.append(report)


def _ensure_source_unchanged(path: Path, fingerprint: str) -> None:
    # Static sources must not change between hashing and normalization.
    if _fingerprint(path) != fingerprint:
        raise ValueError(f"Report changed during import: {path}")


def _apply_timestamp(report: Report, item: ReportInput) -> None:
    if (report.generated_at_date is None) != (report.generated_at_time is None):
        raise ValueError(f"Report {item.path} must provide both generated-at fields")
    if report.generated_at_date is not None:
        return
    if (item.generated_at_date is None) != (item.generated_at_time is None):
        raise ValueError(
            f"Report configuration {item.path} must provide both generated-at fields"
        )
    if item.generated_at_date is None:
        raise ValueError(f"Report {item.path} has no complete generated-at timestamp")
    report.generated_at_date = item.generated_at_date
    report.generated_at_time = item.generated_at_time


def _reject_backdated_report(
    report: Report, path: Path, latest_stored_at: datetime | None
) -> None:
    timestamp = generated_at(report)
    if latest_stored_at is not None and timestamp < latest_stored_at:
        raise ValueError(f"Backdated import rejected: {path}")


def _persist_import_batch(repository: ReportHistory, batch: _ImportBatch) -> None:
    reports = sorted(batch.pending.values(), key=report_order)
    repository.save_import_batch(reports, batch.aliases)
