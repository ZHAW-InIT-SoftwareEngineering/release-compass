"""Map domain reports to Release Compass ontology triples."""

from rdflib import RDF, XSD, Graph, Literal

from src.adapters.outbound.ontology.gate_triples import gate_triples
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    new_graph,
    report_iri,
)
from src.domain.history import generated_at
from src.domain.report import Report


def report_triples(report: Report) -> Graph:
    """Return the ingested facts of one report, its gates and their metrics.

    Derived links (previous report, outcomes, baselines) come from rules.
    Strings are plain literals: in RDF 1.1 they are xsd:string, and SPARQL
    bindings of Python strings match them.
    """
    graph = new_graph()
    node = report_iri(report.report_id)
    graph.add((node, RDF.type, RELEASE_COMPASS.Report))
    # The ID as a literal lets queries find reports without parsing IRIs.
    graph.add((node, AI2CORE.has_id, Literal(str(report.report_id))))
    graph.add(
        (
            node,
            RELEASE_COMPASS.generated_at,
            Literal(generated_at(report), datatype=XSD.dateTime),
        )
    )
    if report.ingestion_sequence is not None:
        graph.add(
            (
                node,
                RELEASE_COMPASS.ingestion_sequence,
                Literal(report.ingestion_sequence, datatype=XSD.integer),
            )
        )
    if report.source_fingerprint is not None:
        graph.add(
            (
                node,
                RELEASE_COMPASS.source_fingerprint,
                Literal(report.source_fingerprint),
            )
        )
    for path in dict.fromkeys([report.source_path, *report.source_paths]):
        if path is not None:
            graph.add((node, RELEASE_COMPASS.source_path, Literal(path)))
    for gate in report.gates:
        graph += gate_triples(gate, report.report_id)
    return graph
