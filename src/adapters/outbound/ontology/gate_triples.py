"""Map a gate run of a report to an ai2core:QualityGate and its metrics."""

from collections.abc import Callable, Mapping
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
from src.domain.gates.performance.measurements import SUPPORTED, performance_measure
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.domain.scoring import Measure

# Gate type -> (name, measure, metric -> statistics scoring may ask for).
# Each gate stores exactly the measurements its scoring can request.
_GATE_KINDS: dict[
    type[Gate], tuple[str, Callable[..., Measure], Mapping[str, tuple[str, ...]]]
] = {
    PerformanceGate: ("performance", performance_measure, SUPPORTED),
}


def gate_type(gate: Gate) -> str:
    return _gate_kind(gate)[0]


def _gate_kind(
    gate: Gate,
) -> tuple[str, Callable[..., Measure], Mapping[str, tuple[str, ...]]]:
    try:
        return _GATE_KINDS[type(gate)]
    except KeyError:
        raise ValueError(f"Unsupported gate type {type(gate).__name__}") from None


def gate_triples(gate: Gate, report_id: UUID) -> Graph:
    name, measure_of, supported = _gate_kind(gate)
    graph = new_graph()
    node = gate_iri(report_id, name)
    graph.add((report_iri(report_id), RELEASE_COMPASS.contains_gate, node))
    graph.add((node, RDF.type, AI2CORE.QualityGate))
    graph.add((node, RELEASE_COMPASS.gate_type, Literal(name)))
    measure = measure_of(gate)
    for metric, statistics in supported.items():
        for statistic in statistics:
            for measurement in measure(metric, statistic):
                graph += metric_triples(measurement, metric, statistic, node)
    return graph
