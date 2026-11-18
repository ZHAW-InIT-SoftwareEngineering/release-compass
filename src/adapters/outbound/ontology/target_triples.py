"""Map configured metric targets to ai2core:Target (ADR 0012)."""

from rdflib import RDF, Graph, Literal

from src.adapters.outbound.ontology.metric_triples import decimal_literal
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    new_graph,
    target_iri,
)
from src.domain.targets import MetricTarget


def target_triples(name: str, target: MetricTarget, version: str) -> Graph:
    """Targets belong to an assessment version, since configuration can change."""
    graph = new_graph()
    node = target_iri(version, name)
    graph.add((node, RDF.type, AI2CORE.Target))
    graph.add((node, RELEASE_COMPASS.metric_name, Literal(target.metric)))
    graph.add((node, AI2CORE.aggregation, Literal(target.aggregation)))
    graph.add((node, RELEASE_COMPASS.unit, Literal(target.unit)))
    if target.range.min is not None:
        graph.add((node, RELEASE_COMPASS.min, decimal_literal(target.range.min)))
    if target.range.max is not None:
        graph.add((node, RELEASE_COMPASS.max, decimal_literal(target.range.max)))
    graph.add((node, RELEASE_COMPASS.min_score, decimal_literal(target.min_score)))
    return graph
