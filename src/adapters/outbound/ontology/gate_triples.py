"""Map a gate run of a report to an ai2core:QualityGate and its metrics."""

from uuid import UUID

from rdflib import RDF, Graph, Literal

from src.adapters.outbound.ontology.metric_triples import metric_triples
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    gate_iri,
    new_graph,
    report_iri,
)
from src.domain.gates.gate import Gate
from src.domain.gates.registry import gate_kind, gate_measurements


def gate_triples(gate: Gate, report_id: UUID) -> Graph:
    """Store the gate with exactly the measurements its scoring can request."""
    name = gate_kind(gate).name
    graph = new_graph()
    node = gate_iri(report_id, name)
    graph.add((report_iri(report_id), RELEASE_COMPASS.contains_gate, node))
    graph.add((node, RDF.type, AI2CORE.QualityGate))
    graph.add((node, RELEASE_COMPASS.gate_type, Literal(name)))
    for metric, statistic, measurement in gate_measurements(gate):
        graph += metric_triples(measurement, metric, statistic, node)
    return graph
