"""Knowledge base held in RDFLib graphs and persisted as Turtle (ADR 0013)."""

from collections.abc import Mapping
from datetime import datetime
from functools import cache
from pathlib import Path
from uuid import UUID

from rdflib import RDF, XSD, Dataset, Graph, Literal, URIRef
from rdflib.query import ResultRow

from src.adapters.outbound.ontology.assessment_triples import assessment_triples
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    RELEASE_COMPASS_DATA,
    bind_prefixes,
    report_iri,
)
from src.adapters.outbound.ontology.report_triples import report_triples
from src.application.ports.outbound.report_repository import ImportState
from src.domain.assessment import GateAcceptance
from src.domain.report import Report
from src.domain.scoring import Measurement
from src.domain.targets import MetricTarget

FACTS_FILE = "facts.ttl"
_NAMESPACES = {"release-compass": RELEASE_COMPASS, "ai2core": AI2CORE, "xsd": XSD}
_QUERIES = Path(__file__).resolve().parent / "queries"
_FACTS_GRAPH = RELEASE_COMPASS_DATA["graph/facts"]


def assessment_file(version: str) -> str:
    return f"assessment-{version}.ttl"


@cache
def _query(name: str) -> str:
    return (_QUERIES / f"{name}.rq").read_text(encoding="utf-8")


class TurtleKnowledgeBase:
    """Two named graphs: immutable report facts and one assessment version.

    Queries see both; writes go to exactly one, so assessing never changes
    the facts (ADR 0008).
    """

    def __init__(self, directory: Path):
        self._directory = directory
        self._dataset = Dataset(default_union=True)
        bind_prefixes(self._dataset)
        self._facts = self._dataset.graph(_FACTS_GRAPH)
        _load(self._facts, directory / FACTS_FILE)
        self._assessment: Graph | None = None
        self._version: str | None = None

    # Import

    def import_state(self) -> ImportState:
        rows = self.select(_query("import_state"))
        # An aggregate over no reports yields no row in RDFLib.
        state = rows[0] if rows else {}
        latest = state.get("latest_generated_at")
        sequence = state.get("max_sequence")
        return ImportState(
            latest_generated_at=latest if isinstance(latest, datetime) else None,
            max_ingestion_sequence=sequence if isinstance(sequence, int) else 0,
        )

    def get_by_fingerprint(self, fingerprint: str) -> Report | None:
        rows = self.select(
            _query("report_by_fingerprint"), {"fingerprint": fingerprint}
        )
        if not rows:
            return None
        first = rows[0]
        timestamp = first["generated_at"]
        sequence = first.get("sequence")
        if not isinstance(timestamp, datetime):
            raise TypeError(f"Stored report {first['id']} has no dateTime generated-at")
        return Report(
            report_id=UUID(str(first["id"])),
            generated_at_date=timestamp.date().isoformat(),
            generated_at_time=timestamp.time().isoformat(),
            source_fingerprint=fingerprint,
            ingestion_sequence=sequence if isinstance(sequence, int) else None,
            source_paths=sorted({str(row["path"]) for row in rows if "path" in row}),
        )

    def save_import_batch(
        self, reports: list[Report], aliases: dict[UUID, list[str]]
    ) -> None:
        new_ids = {report.report_id for report in reports}
        for report_id in aliases:
            known = (report_iri(report_id), RDF.type, RELEASE_COMPASS.Report)
            if report_id not in new_ids and known not in self._facts:
                raise ValueError(f"Alias target {report_id} was not found")
        for report in reports:
            self._facts += report_triples(report)
        for report_id, paths in aliases.items():
            for path in paths:
                self._facts.add(
                    (report_iri(report_id), RELEASE_COMPASS.source_path, Literal(path))
                )
        self.save()

    # Assessment

    def open_assessment(self, version: str) -> None:
        if self._assessment is not None:
            self._dataset.remove_graph(self._assessment)
        self._version = version
        self._assessment = self._dataset.graph(
            RELEASE_COMPASS_DATA[f"graph/assessment/{version}"]
        )
        _load(self._assessment, self._directory / assessment_file(version))

    def measurements(
        self, report_id: UUID, gate_type: str, metric: str, statistic: str
    ) -> list[Measurement]:
        rows = self.select(
            _query("measurements"),
            {
                "id": str(report_id),
                "gate_type": gate_type,
                "metric": metric,
                "statistic": statistic,
            },
        )
        return [
            Measurement(
                source=str(row["source"]),
                path=str(row["path"]),
                value=_float(row.get("value")),
                unit=str(row["unit"]) if "unit" in row else None,
                weight=_float(row.get("weight")),
            )
            for row in rows
        ]

    def add_gate_assessment(
        self,
        report_id: UUID,
        gate_type: str,
        acceptance: GateAcceptance,
        targets: Mapping[str, MetricTarget],
        policy_version: str,
    ) -> None:
        if self._assessment is None or self._version is None:
            raise RuntimeError("Open an assessment version before adding results")
        self._assessment += assessment_triples(
            report_id, gate_type, acceptance, targets, self._version, policy_version
        )

    # Shared

    def select(
        self, query: str, bindings: dict[str, object] | None = None
    ) -> list[dict[str, object]]:
        """Run SPARQL over facts and the open assessment; plain Python values."""
        result = self._dataset.query(
            query,
            initNs=_NAMESPACES,
            initBindings={
                name: Literal(value) for name, value in (bindings or {}).items()
            },
        )
        rows = []
        for row in result:
            assert isinstance(row, ResultRow)
            rows.append(
                {name: _to_python(value) for name, value in row.asdict().items()}
            )
        return rows

    def save(self) -> None:
        _save(self._facts, self._directory / FACTS_FILE)
        if self._assessment is not None and self._version is not None:
            _save(self._assessment, self._directory / assessment_file(self._version))


def _load(graph: Graph, path: Path) -> None:
    if path.exists():
        graph.parse(path, format="turtle")


def _save(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a sibling file first so a failed save never leaves a partial file.
    temporary = path.with_suffix(".ttl.tmp")
    bind_prefixes(graph)
    graph.serialize(temporary, format="turtle")
    temporary.replace(path)


def _float(value: object) -> float | None:
    return None if value is None else float(str(value))


def _to_python(value: object) -> object:
    if isinstance(value, URIRef):
        return str(value)
    if isinstance(value, Literal):
        return value.toPython()
    return value
