"""Release Compass ontology namespaces, instance IRIs and graph setup (ADR 0013)."""

from urllib.parse import quote
from uuid import UUID

from rdflib import Graph, Namespace, URIRef

_BASE = "https://github.com/ZHAW-InIT-SoftwareEngineering/release-compass/"

# Vocabulary terms, declared in ontology/release-compass.ttl.
RELEASE_COMPASS = Namespace(f"{_BASE}ontology#")
# Instance IRIs, e.g. <…/data/report/{uuid}>.
RELEASE_COMPASS_DATA = Namespace(f"{_BASE}data/")
# Reused AI-Square terms, e.g. ai2core:has_id (domain owl:Thing).
AI2CORE = Namespace("https://ai-square.ch/ai2core#")


def new_graph() -> Graph:
    graph = Graph()
    bind_prefixes(graph)
    return graph


def bind_prefixes(graph: Graph) -> None:
    graph.bind("release-compass", RELEASE_COMPASS)
    graph.bind("ai2core", AI2CORE)


def _segment(name: str) -> str:
    # Transaction and target names may contain spaces or slashes.
    return quote(name, safe="")


def report_iri(report_id: UUID) -> URIRef:
    return RELEASE_COMPASS_DATA[f"report/{report_id}"]


def gate_iri(report_id: UUID, gate_type: str) -> URIRef:
    return URIRef(f"{report_iri(report_id)}/gate/{_segment(gate_type)}")


def metric_iri(gate: URIRef, source: str, metric: str, statistic: str) -> URIRef:
    return URIRef(
        f"{gate}/metric/{_segment(source)}/{_segment(metric)}/{_segment(statistic)}"
    )


def source_iri(source: str) -> URIRef:
    # Shared across reports, so the same transaction can be compared (Q5).
    return RELEASE_COMPASS_DATA[f"source/{_segment(source)}"]


def target_iri(version: str, name: str) -> URIRef:
    return RELEASE_COMPASS_DATA[f"target/{_segment(version)}/{_segment(name)}"]


def assessment_iri(gate: URIRef, version: str, name: str) -> URIRef:
    return URIRef(f"{gate}/assessment/{_segment(version)}/{_segment(name)}")
