"""Map one measurement of a gate run to an ai2core:Metric."""

from decimal import Decimal
from math import isfinite

from rdflib import RDF, XSD, Graph, Literal, URIRef

from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    metric_iri,
    new_graph,
    source_iri,
)
from src.domain.scoring import Measurement


def decimal_literal(value: float) -> Literal:
    if not isfinite(value):
        raise ValueError(f"Cannot store non-finite value {value!r}")
    return Literal(Decimal(str(value)), datatype=XSD.decimal)


def metric_triples(
    measurement: Measurement, metric: str, statistic: str, gate: URIRef
) -> Graph:
    """Store a measurement as scoring reads it (src/domain/scoring.py).

    Missing value, unit or weight leave their triple out.
    """
    graph = new_graph()
    node = metric_iri(gate, measurement.source, metric, statistic)
    source = source_iri(measurement.source)
    graph.add((gate, RELEASE_COMPASS.produces_metric, node))
    graph.add((node, RDF.type, AI2CORE.Metric))
    graph.add((node, RELEASE_COMPASS.metric_name, Literal(metric)))
    graph.add((node, RELEASE_COMPASS.statistic, Literal(statistic)))
    graph.add((node, RELEASE_COMPASS.field_path, Literal(measurement.path)))
    graph.add((node, RELEASE_COMPASS.measured_from, source))
    graph.add((source, RDF.type, AI2CORE.Source))
    graph.add((source, RELEASE_COMPASS.source_name, Literal(measurement.source)))
    if measurement.value is not None:
        graph.add((node, RELEASE_COMPASS.value, decimal_literal(measurement.value)))
    if measurement.unit is not None:
        graph.add((node, RELEASE_COMPASS.unit, Literal(measurement.unit)))
    if measurement.weight is not None:
        graph.add(
            (node, RELEASE_COMPASS.request_count, decimal_literal(measurement.weight))
        )
    return graph
