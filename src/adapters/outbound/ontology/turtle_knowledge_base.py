"""Knowledge base held in RDFLib graphs and persisted as Turtle (ADR 0013)."""

from pathlib import Path

from rdflib import XSD, Literal, URIRef
from rdflib.query import ResultRow

from src.adapters.outbound.ontology.release_compass_ontology import (
    RELEASE_COMPASS,
    new_graph,
)
from src.adapters.outbound.ontology.report_triples import report_triples
from src.domain.report import Report

FACTS_FILE = "facts.ttl"
_NAMESPACES = {"release-compass": RELEASE_COMPASS, "xsd": XSD}


class TurtleKnowledgeBase:
    def __init__(self, directory: Path):
        self._facts_path = directory / FACTS_FILE
        self._facts = new_graph()
        if self._facts_path.exists():
            self._facts.parse(self._facts_path, format="turtle")

    def add_report(self, report: Report) -> None:
        self._facts += report_triples(report)

    def select(
        self, query: str, bindings: dict[str, object] | None = None
    ) -> list[dict[str, object]]:
        result = self._facts.query(
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
        self._facts_path.parent.mkdir(parents=True, exist_ok=True)
        # Write a sibling file first so a failed save never leaves partial facts.
        temporary = self._facts_path.with_suffix(".ttl.tmp")
        self._facts.serialize(temporary, format="turtle")
        temporary.replace(self._facts_path)


def _to_python(value: object) -> object:
    if isinstance(value, URIRef):
        return str(value)
    if isinstance(value, Literal):
        return value.toPython()
    return value
