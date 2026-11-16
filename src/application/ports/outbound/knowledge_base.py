from typing import Protocol

from src.domain.report import Report


class KnowledgeBase(Protocol):
    """Stores ingested facts as ontology triples and answers SPARQL (ADR 0013)."""

    def add_report(self, report: Report) -> None: ...

    def select(
        self, query: str, bindings: dict[str, object] | None = None
    ) -> list[dict[str, object]]:
        """Run a SPARQL SELECT; IRIs come back as strings, literals as Python values."""
        ...

    def save(self) -> None: ...
