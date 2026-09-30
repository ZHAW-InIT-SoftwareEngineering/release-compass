"""SQLite persistence adapter for domain reports."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Generator
from uuid import UUID

from src.application.ports.outbound.report_reader import ReportReader
from src.application.ports.outbound.report_writer import ReportWriter
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
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        decoded = {key: _decode(item) for key, item in value.items() if key != "__type__"}
        type_name = value.get("__type__")
        if type_name is None:
            return decoded
        if type_name == "UUID":
            return UUID(decoded["value"])
        try:
            domain_type = _DOMAIN_TYPES[type_name]
        except KeyError as error:
            raise ValueError(f"Unknown stored domain type: {type_name}") from error
        return domain_type(**decoded)
    return value


class SQLiteReportRepository(ReportReader, ReportWriter):
    """Store reports and gates in SQLite; nested metric values use JSON."""

    def __init__(self, database_path: str | Path):
        self._database_path = str(database_path)
        self._memory_connection = (
            sqlite3.connect(":memory:") if self._database_path == ":memory:" else None
        )
        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        connection = self._memory_connection or sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            if self._memory_connection is None:
                connection.close()

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    source_path TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS gates (
                    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
                    gate_index INTEGER NOT NULL,
                    gate_type TEXT NOT NULL,
                    baseline_run_id TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (report_id, gate_index)
                );

                CREATE INDEX IF NOT EXISTS gates_baseline_run_id_idx
                    ON gates(baseline_run_id);
                """
            )

    def save(self, report: Report) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO reports (report_id, source_path, schema_version)
                   VALUES (?, ?, 1)
                   ON CONFLICT(report_id) DO UPDATE SET
                       source_path = excluded.source_path,
                       schema_version = excluded.schema_version""",
                (str(report.report_id), report.source_path),
            )
            connection.execute("DELETE FROM gates WHERE report_id = ?", (str(report.report_id),))
            connection.executemany(
                """INSERT INTO gates
                   (report_id, gate_index, gate_type, baseline_run_id, payload_json)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (
                        str(report.report_id),
                        index,
                        type(gate).__name__,
                        str(gate.baseline_run_id) if gate.baseline_run_id else None,
                        json.dumps(_encode(gate), separators=(",", ":")),
                    )
                    for index, gate in enumerate(report.gates)
                ],
            )

    def get_by_id(self, report_id: UUID) -> Report | None:
        with self._connect() as connection:
            report_row = connection.execute(
                "SELECT report_id, source_path FROM reports WHERE report_id = ?",
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
            gates=gates,
        )
