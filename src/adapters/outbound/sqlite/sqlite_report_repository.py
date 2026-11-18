"""SQLite adapter of ReportRepository, mirroring the knowledge base (ADR 0013).

Tables (`schema.sql`) hold the same facts as `facts.ttl` and the same results
as one `assessment-<version>.ttl`. `queries/` and `rules/` mirror the SPARQL
files of the knowledge base by name.
"""

import sqlite3
import threading
from collections.abc import Callable, Collection, Iterable, Mapping
from datetime import datetime
from functools import cache, wraps
from pathlib import Path
from typing import Concatenate
from uuid import UUID

from src.application.ports.outbound.report_questions import (
    Baselines,
    GateBaseline,
    GateResult,
    MeasurementChange,
    MetricResult,
    ReportSummary,
    SourceResult,
)
from src.application.ports.outbound.report_repository import ImportState
from src.domain.assessment import (
    GateAcceptance,
    MetricAcceptance,
    Outcome,
    combine_outcomes,
)
from src.domain.gates.registry import gate_kind, gate_measurements
from src.domain.history import generated_at
from src.domain.report import Report
from src.domain.scoring import Measurement
from src.domain.targets import MetricTarget

SCHEMA_VERSION = 2

_DIRECTORY = Path(__file__).resolve().parent
_QUERIES = _DIRECTORY / "queries"
_RULES = _DIRECTORY / "rules"
_SCHEMA = _DIRECTORY / "schema.sql"


@cache
def _query(name: str) -> str:
    return (_QUERIES / f"{name}.sql").read_text(encoding="utf-8")


@cache
def _rule(name: str) -> str:
    return (_RULES / f"{name}.sql").read_text(encoding="utf-8")


def _locked[**P, R](
    method: Callable[Concatenate[SQLiteReportRepository, P], R],
) -> Callable[Concatenate[SQLiteReportRepository, P], R]:
    """Run the method while holding the repository lock (ADR 0015)."""

    @wraps(method)
    def wrapper(self: SQLiteReportRepository, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class SQLiteReportRepository:
    """Imports commit at once; assessment results commit on `save()`.

    One connection, shared across threads behind a lock (ADR 0015).
    """

    def __init__(self, database_path: str | Path):
        if str(database_path) != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        # LangGraph's ToolNode calls tools from worker threads.
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._lock = threading.RLock()
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._version: str | None = None
        try:
            self._initialize_schema()
        except Exception:
            self._connection.close()
            raise

    @_locked
    def close(self) -> None:
        self._connection.close()

    def _initialize_schema(self) -> None:
        (version,) = self._connection.execute("PRAGMA user_version").fetchone()
        if version == SCHEMA_VERSION:
            return
        (tables,) = self._connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()
        if tables:
            raise ValueError(
                "SQLite file uses an older schema; delete it and import again"
            )
        with self._connection:
            self._connection.executescript(_SCHEMA.read_text(encoding="utf-8"))
            self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    # Import

    @_locked
    def import_state(self) -> ImportState:
        latest, sequence = self._connection.execute(_query("import_state")).fetchone()
        return ImportState(
            latest_generated_at=datetime.fromisoformat(latest) if latest else None,
            max_ingestion_sequence=sequence or 0,
        )

    @_locked
    def get_by_fingerprint(self, fingerprint: str) -> Report | None:
        row = self._connection.execute(
            _query("report_by_fingerprint"), {"fingerprint": fingerprint}
        ).fetchone()
        if row is None:
            return None
        report_id, timestamp, sequence = row
        at = datetime.fromisoformat(timestamp)
        return Report(
            report_id=UUID(report_id),
            generated_at_date=at.date().isoformat(),
            generated_at_time=at.time().isoformat(),
            source_fingerprint=fingerprint,
            ingestion_sequence=sequence,
            source_paths=self._column("source_paths", {"report_id": report_id}),
        )

    @_locked
    def save_import_batch(
        self, reports: list[Report], aliases: dict[UUID, list[str]]
    ) -> None:
        new_ids = {report.report_id for report in reports}
        with self._connection:
            for report_id in aliases:
                if report_id not in new_ids and not self._report_exists(report_id):
                    raise ValueError(f"Alias target {report_id} was not found")
            for report in reports:
                self._insert_report(report)
            for report_id, paths in aliases.items():
                self._insert_paths(report_id, paths)

    def _report_exists(self, report_id: UUID) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM reports WHERE report_id = ?", (str(report_id),)
            ).fetchone()
            is not None
        )

    def _insert_report(self, report: Report) -> None:
        report_id = str(report.report_id)
        self._connection.execute(
            "INSERT INTO reports VALUES (?, ?, ?, ?)",
            (
                report_id,
                generated_at(report).isoformat(),
                report.ingestion_sequence,
                report.source_fingerprint,
            ),
        )
        self._insert_paths(report.report_id, [report.source_path, *report.source_paths])
        for gate in report.gates:
            gate_type = gate_kind(gate).name
            self._connection.execute(
                "INSERT INTO gates VALUES (?, ?)", (report_id, gate_type)
            )
            self._connection.executemany(
                "INSERT INTO measurements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        report_id,
                        gate_type,
                        metric,
                        statistic,
                        item.source,
                        item.path,
                        item.value,
                        item.unit,
                        item.weight,
                    )
                    for metric, statistic, item in gate_measurements(gate)
                ],
            )

    def _insert_paths(self, report_id: UUID, paths: Iterable[str | None]) -> None:
        self._connection.executemany(
            "INSERT OR IGNORE INTO source_paths VALUES (?, ?)",
            [(str(report_id), path) for path in paths if path is not None],
        )

    # Assessment

    @_locked
    def open_assessment(self, version: str) -> None:
        self._connection.rollback()
        self._version = version

    @_locked
    def unassessed_reports(self) -> list[UUID]:
        version = self._require_assessment()
        rows = self._column("unassessed_reports", {"version": version})
        return [UUID(report_id) for report_id in rows]

    @_locked
    def gate_types(self, report_id: UUID) -> set[str]:
        return set(self._column("gate_types", {"report_id": str(report_id)}))

    @_locked
    def measurements(
        self, report_id: UUID, gate_type: str, metric: str, statistic: str
    ) -> list[Measurement]:
        rows = self._connection.execute(
            _query("measurements"),
            {
                "report_id": str(report_id),
                "gate_type": gate_type,
                "metric": metric,
                "statistic": statistic,
            },
        ).fetchall()
        return [Measurement(*row) for row in rows]

    @_locked
    def add_gate_assessment(
        self,
        report_id: UUID,
        gate_type: str,
        acceptance: GateAcceptance,
        targets: Mapping[str, MetricTarget],
        policy_version: str,
    ) -> None:
        version = self._require_assessment()
        key = (version, str(report_id), gate_type)
        self._connection.execute(
            "INSERT INTO gate_assessments VALUES (?, ?, ?, ?, NULL)",
            (*key, acceptance.outcome),
        )
        for name, result in acceptance.metrics.items():
            target = targets[name]
            self._connection.execute(
                "INSERT OR REPLACE INTO targets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version,
                    name,
                    target.metric,
                    target.aggregation,
                    target.unit,
                    target.range.min,
                    target.range.max,
                    target.min_score,
                ),
            )
            self._insert_metric_assessment(key, name, result, policy_version)

    def _insert_metric_assessment(
        self,
        key: tuple[str, str, str],
        name: str,
        result: MetricAcceptance,
        policy_version: str,
    ) -> None:
        self._connection.execute(
            "INSERT INTO metric_assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (*key, name, result.outcome, result.score, result.reason, policy_version),
        )
        self._connection.executemany(
            "INSERT INTO source_assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    *key,
                    name,
                    source.name,
                    source.excluded,
                    None if source.penalty is None else source.penalty == 0,
                    source.reason,
                )
                for source in result.sources
            ],
        )

    @_locked
    def apply_rules(
        self, report_id: UUID, required_gate_types: Collection[str]
    ) -> None:
        """Apply `rules/` in the order of the knowledge base's RULES."""
        bindings = {"version": self._require_assessment(), "report_id": str(report_id)}
        previous = self._first(_rule("previous_report"), bindings)
        gate_outcomes: dict[str, Outcome] = dict(
            self._connection.execute(_rule("report_outcome"), bindings).fetchall()
        )
        missing = set(required_gate_types) - gate_outcomes.keys()
        unknown: list[Outcome] = ["unknown"] * len(missing)
        outcome = combine_outcomes([*gate_outcomes.values(), *unknown])
        baseline = self._first(_rule("baseline_report"), bindings)
        self._connection.execute(
            "INSERT INTO report_assessments VALUES (?, ?, ?, ?, ?, ?)",
            (
                bindings["version"],
                bindings["report_id"],
                previous,
                previous is None,
                outcome,
                baseline,
            ),
        )
        self._connection.execute(_rule("baseline_gate"), bindings)

    # Questions, answered from the open version

    @_locked
    def describe_report(self, report_id: UUID) -> ReportSummary | None:
        bindings = {"version": self._version, "report_id": str(report_id)}
        row = self._connection.execute(_query("describe_report"), bindings).fetchone()
        if row is None:
            return None
        at, sequence, outcome, is_root, previous = row
        return ReportSummary(
            report_id=report_id,
            generated_at=datetime.fromisoformat(at),
            ingestion_sequence=sequence,
            source_paths=self._column("source_paths", bindings),
            gate_types=self._column("gate_types", bindings),
            outcome=outcome,
            is_root=None if is_root is None else bool(is_root),
            previous_report_id=None if previous is None else UUID(previous),
        )

    @_locked
    def baselines(self, report_id: UUID) -> Baselines | None:
        if not self._report_exists(report_id):
            return None
        bindings = {"version": self._version, "report_id": str(report_id)}
        baseline = self._first(_query("report_baseline"), bindings)
        rows = self._connection.execute(_query("gate_baselines"), bindings).fetchall()
        return Baselines(
            report_id,
            None if baseline is None else UUID(baseline),
            [
                GateBaseline(gate_type, None if gate is None else UUID(gate), policy)
                for gate_type, gate, policy in rows
            ],
        )

    @_locked
    def compare_measurements(
        self,
        report_id: UUID,
        baseline_report_id: UUID,
        gate_type: str,
        metric: str,
        statistic: str,
    ) -> list[MeasurementChange]:
        rows = self._connection.execute(
            _query("compare_measurements"),
            {
                "report_id": str(report_id),
                "baseline_report_id": str(baseline_report_id),
                "gate_type": gate_type,
                "metric": metric,
                "statistic": statistic,
            },
        ).fetchall()
        return [MeasurementChange(*row) for row in rows]

    @_locked
    def gate_results(self, report_id: UUID) -> list[GateResult]:
        bindings = {"version": self._version, "report_id": str(report_id)}
        gates = self._connection.execute(_query("gate_results"), bindings).fetchall()
        return [
            GateResult(
                gate_type,
                outcome,
                self._metric_results({**bindings, "gate_type": gate_type}),
            )
            for gate_type, outcome in gates
        ]

    def _metric_results(self, bindings: dict[str, str | None]) -> list[MetricResult]:
        rows = self._connection.execute(_query("metric_results"), bindings).fetchall()
        return [
            MetricResult(
                *values,
                sources=self._source_results(
                    {
                        **bindings,
                        "name": name,
                        "metric": values[0],
                        "statistic": values[1],
                    }
                ),
            )
            for name, *values in rows
        ]

    def _source_results(self, bindings: dict[str, str | None]) -> list[SourceResult]:
        rows = self._connection.execute(_query("source_results"), bindings)
        return [
            SourceResult(
                source,
                value,
                None if meets is None else bool(meets),
                bool(excluded),
                reason,
            )
            for source, value, meets, excluded, reason in rows
        ]

    def _column(self, name: str, bindings: Mapping[str, str | None]) -> list[str]:
        """The first column of every row of a query in `queries/`."""
        return [value for (value,) in self._connection.execute(_query(name), bindings)]

    def _first(self, query: str, bindings: Mapping[str, str | None]) -> str | None:
        row = self._connection.execute(query, bindings).fetchone()
        return row[0] if row else None

    def _require_assessment(self) -> str:
        if self._version is None:
            raise RuntimeError("Open an assessment version before adding results")
        return self._version

    @_locked
    def save(self) -> None:
        self._connection.commit()
