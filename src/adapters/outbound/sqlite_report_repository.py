"""SQLite persistence adapter for domain reports."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from math import isfinite
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.ports.outbound.report_reader import ReportReader
from src.application.ports.outbound.report_writer import ReportWriter
from src.domain.assessment import GateAcceptance, MetricAcceptance, SourceAssessment
from src.domain.evidence import EvidencePack, GateEvidence
from src.domain.gates.gate import Gate
from src.domain.gates.performance.performance_gate import (
    MetricAssessment,
    MetricSummary,
    PerformanceGate,
    RequestOutcomes,
    ResourceMetric,
    ResponseTimeMetric,
    ThresholdConfiguration,
    ThroughputMetric,
    TransactionPerformance,
    ViolationPeriod,
)
from src.domain.history import generated_at
from src.domain.report import Report

_DOMAIN_TYPES = {
    item.__name__: item
    for item in (
        Gate,
        MetricAssessment,
        MetricSummary,
        PerformanceGate,
        RequestOutcomes,
        ResourceMetric,
        ResponseTimeMetric,
        ThresholdConfiguration,
        ThroughputMetric,
        TransactionPerformance,
        ViolationPeriod,
        SourceAssessment,
        MetricAcceptance,
        GateAcceptance,
        GateEvidence,
        EvidencePack,
    )
}


def _encode(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__type__": type(value).__name__,
            **{item.name: _encode(getattr(value, item.name)) for item in fields(value)},
        }
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if isinstance(value, UUID):
        return {"__type__": "UUID", "value": str(value)}
    if isinstance(value, float) and not isfinite(value):
        return {"__type__": "NonFiniteFloat", "value": str(value)}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        decoded = {
            key: _decode(item) for key, item in value.items() if key != "__type__"
        }
        type_name = value.get("__type__")
        if type_name is None:
            return decoded
        if type_name == "UUID":
            return UUID(decoded["value"])
        if type_name == "NonFiniteFloat":
            return float(decoded["value"])
        try:
            domain_type = _DOMAIN_TYPES[type_name]
        except KeyError as error:
            raise ValueError(f"Unknown stored domain type: {type_name}") from error
        return domain_type(**decoded)
    return value


class SQLiteReportRepository(ReportReader, ReportWriter):
    """Store reports and gates in SQLite; nested metric values use JSON."""

    def __init__(self, database_path: str | Path):
        self._closed = False
        self._database_path = str(database_path)
        self._memory_connection = (
            sqlite3.connect(":memory:") if self._database_path == ":memory:" else None
        )
        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        if self._closed:
            raise RuntimeError("Report repository is closed")
        connection = self._memory_connection or sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            if self._memory_connection is None:
                connection.close()

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None
        self._closed = True

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    source_path TEXT,
                    generated_at_date TEXT,
                    generated_at_time TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS gates (
                    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
                    gate_index INTEGER NOT NULL,
                    gate_type TEXT NOT NULL,
                    baseline_report_id TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (report_id, gate_index)
                );

                CREATE INDEX IF NOT EXISTS gates_baseline_report_id_idx
                    ON gates(baseline_report_id);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(reports)").fetchall()
            }
            additions = {
                "generated_at_date": "TEXT",
                "generated_at_time": "TEXT",
                "source_fingerprint": "TEXT",
                "ingestion_sequence": "INTEGER",
                "source_paths_json": "TEXT NOT NULL DEFAULT '[]'",
            }
            for column, definition in additions.items():
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE reports ADD COLUMN {column} {definition}"
                    )
            connection.execute(
                "UPDATE reports SET ingestion_sequence = rowid WHERE ingestion_sequence IS NULL"
            )
            connection.executescript(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS reports_fingerprint_idx
                    ON reports(source_fingerprint);
                CREATE UNIQUE INDEX IF NOT EXISTS reports_ingestion_sequence_idx
                    ON reports(ingestion_sequence);
                CREATE TABLE IF NOT EXISTS evidence_packs (
                    report_id TEXT NOT NULL REFERENCES reports(report_id),
                    assessment_version TEXT NOT NULL,
                    evidence_pack_id TEXT NOT NULL UNIQUE,
                    outcome TEXT NOT NULL CHECK(outcome IN ('pass', 'fail', 'unknown')),
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (report_id, assessment_version)
                );
                CREATE TABLE IF NOT EXISTS gate_acceptances (
                    report_id TEXT NOT NULL,
                    assessment_version TEXT NOT NULL,
                    gate_type TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK(outcome IN ('pass', 'fail', 'unknown')),
                    baseline_report_id TEXT REFERENCES reports(report_id),
                    PRIMARY KEY (report_id, assessment_version, gate_type),
                    FOREIGN KEY (report_id, assessment_version)
                        REFERENCES evidence_packs(report_id, assessment_version)
                );
                CREATE INDEX IF NOT EXISTS gate_acceptance_outcomes_idx
                    ON gate_acceptances(assessment_version, gate_type, outcome);
                """
            )

    def save(self, report: Report) -> None:
        with self._connect() as connection:
            self._save(connection, report)

    def _save(self, connection: sqlite3.Connection, report: Report) -> None:
        existing = connection.execute(
            "SELECT source_fingerprint, ingestion_sequence FROM reports WHERE report_id = ?",
            (str(report.report_id),),
        ).fetchone()
        if existing and existing["source_fingerprint"] is not None:
            raise ValueError("Imported source reports are immutable")
        if (
            existing
            and connection.execute(
                "SELECT 1 FROM evidence_packs WHERE report_id = ?",
                (str(report.report_id),),
            ).fetchone()
        ):
            raise ValueError("Assessed source reports are immutable")
        if report.ingestion_sequence is None:
            report.ingestion_sequence = (
                existing["ingestion_sequence"]
                if existing
                else connection.execute(
                    "SELECT COALESCE(MAX(ingestion_sequence), 0) + 1 FROM reports"
                ).fetchone()[0]
            )
        connection.execute(
            """INSERT INTO reports
                   (report_id, source_path, generated_at_date, generated_at_time, schema_version,
                    source_fingerprint, ingestion_sequence, source_paths_json)
                   VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                   ON CONFLICT(report_id) DO UPDATE SET
                       source_path = excluded.source_path,
                       generated_at_date = COALESCE(reports.generated_at_date, excluded.generated_at_date),
                       generated_at_time = COALESCE(reports.generated_at_time, excluded.generated_at_time),
                       schema_version = excluded.schema_version,
                       source_fingerprint = excluded.source_fingerprint,
                       source_paths_json = excluded.source_paths_json""",
            (
                str(report.report_id),
                report.source_path,
                report.generated_at_date,
                report.generated_at_time,
                report.source_fingerprint,
                report.ingestion_sequence,
                json.dumps(
                    report.source_paths
                    or ([report.source_path] if report.source_path else [])
                ),
            ),
        )
        connection.execute(
            "DELETE FROM gates WHERE report_id = ?", (str(report.report_id),)
        )
        connection.executemany(
            """INSERT INTO gates
                   (report_id, gate_index, gate_type, baseline_report_id, payload_json)
                   VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    str(report.report_id),
                    index,
                    type(gate).__name__,
                    str(gate.baseline_report_id) if gate.baseline_report_id else None,
                    json.dumps(_encode(gate), separators=(",", ":")),
                )
                for index, gate in enumerate(report.gates)
            ],
        )

    def get_by_id(self, report_id: UUID) -> Report | None:
        with self._connect() as connection:
            report_row = connection.execute(
                """SELECT report_id, source_path, generated_at_date, generated_at_time,
                          source_fingerprint, ingestion_sequence, source_paths_json
                   FROM reports WHERE report_id = ?""",
                (str(report_id),),
            ).fetchone()
            if report_row is None:
                return None
            gate_rows = connection.execute(
                "SELECT payload_json FROM gates WHERE report_id = ? ORDER BY gate_index",
                (str(report_id),),
            ).fetchall()

        gates = [_decode(json.loads(row["payload_json"])) for row in gate_rows]
        return Report(
            report_id=UUID(report_row["report_id"]),
            source_path=report_row["source_path"],
            generated_at_date=report_row["generated_at_date"],
            generated_at_time=report_row["generated_at_time"],
            gates=gates,
            source_fingerprint=report_row["source_fingerprint"],
            ingestion_sequence=report_row["ingestion_sequence"],
            source_paths=json.loads(report_row["source_paths_json"]),
        )

    def list_reports(self) -> list[Report]:
        with self._connect() as connection:
            ids = [
                UUID(row["report_id"])
                for row in connection.execute(
                    "SELECT report_id FROM reports ORDER BY ingestion_sequence"
                )
            ]
        reports = [self.get_by_id(report_id) for report_id in ids]
        return [report for report in reports if report is not None]

    def get_by_fingerprint(self, fingerprint: str) -> Report | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_id FROM reports WHERE source_fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return self.get_by_id(UUID(row["report_id"])) if row else None

    def save_import_batch(
        self,
        reports: list[Report],
        aliases: dict[UUID, list[str]],
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamps = [
                generated_at(
                    Report(
                        generated_at_date=row["generated_at_date"],
                        generated_at_time=row["generated_at_time"],
                    )
                )
                for row in connection.execute(
                    "SELECT generated_at_date, generated_at_time FROM reports"
                )
            ]
            latest = max(timestamps, default=None)
            if latest is not None and any(
                generated_at(report) < latest for report in reports
            ):
                raise ValueError("Backdated import rejected")
            for report in reports:
                self._save(connection, report)
            for report_id, paths in aliases.items():
                row = connection.execute(
                    "SELECT source_paths_json FROM reports WHERE report_id = ?",
                    (str(report_id),),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Alias target {report_id} was not found")
                stored_paths = json.loads(row["source_paths_json"])
                connection.execute(
                    "UPDATE reports SET source_paths_json = ? WHERE report_id = ?",
                    (
                        json.dumps(list(dict.fromkeys([*stored_paths, *paths]))),
                        str(report_id),
                    ),
                )

    def get_evidence(self, report_id: UUID, version: str) -> EvidencePack | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM evidence_packs WHERE report_id = ? AND assessment_version = ?",
                (str(report_id), version),
            ).fetchone()
        return _decode(json.loads(row["payload_json"])) if row else None

    def save_evidence(self, evidence: EvidencePack) -> None:
        payload = json.dumps(
            _encode(evidence), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT payload_json FROM evidence_packs WHERE report_id = ? AND assessment_version = ?",
                (str(evidence.report_id), evidence.assessment_version),
            ).fetchone()
            if existing:
                if existing["payload_json"] != payload:
                    raise ValueError("Evidence packs are immutable")
                return
            connection.execute(
                "INSERT INTO evidence_packs VALUES (?, ?, ?, ?, ?)",
                (
                    str(evidence.report_id),
                    evidence.assessment_version,
                    str(evidence.evidence_pack_id),
                    evidence.outcome,
                    payload,
                ),
            )
            connection.executemany(
                "INSERT INTO gate_acceptances VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        str(evidence.report_id),
                        evidence.assessment_version,
                        name,
                        item.acceptance.outcome,
                        str(item.baseline_report_id)
                        if item.baseline_report_id
                        else None,
                    )
                    for name, item in evidence.gates.items()
                ],
            )
