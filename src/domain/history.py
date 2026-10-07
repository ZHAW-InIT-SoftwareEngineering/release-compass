"""Report ordering and passing-baseline policy."""

from datetime import UTC, datetime
from uuid import UUID

from src.domain.evidence import EvidencePack
from src.domain.report import Report


def generated_at(report: Report) -> datetime:
    if report.generated_at_date is None or report.generated_at_time is None:
        raise ValueError(
            f"Report {report.report_id} requires a complete generated-at timestamp"
        )
    value = datetime.fromisoformat(
        f"{report.generated_at_date}T{report.generated_at_time}"
    )
    if value.tzinfo is not None and value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("Report timestamps must be UTC")
    return value.replace(tzinfo=UTC)


def report_order(report: Report) -> tuple[datetime, int]:
    if report.ingestion_sequence is None:
        raise ValueError(f"Report {report.report_id} has no ingestion sequence")
    return generated_at(report), report.ingestion_sequence


def latest_passing(
    previous: list[Report],
    packs: dict[UUID, EvidencePack],
    gate_type: str | None = None,
) -> Report | None:
    for report in reversed(previous):
        pack = packs[report.report_id]
        if gate_type is None:
            passing = pack.outcome == "pass"
        else:
            gate = pack.gates.get(gate_type)
            passing = gate is not None and gate.acceptance.outcome == "pass"
        if passing:
            return report
    return None
