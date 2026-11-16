"""Map domain reports to Release Compass ontology triples."""

from uuid import UUID

from rdflib import RDF, XSD, Graph, Literal, URIRef

from src.adapters.outbound.ontology.release_compass_ontology import (
    RELEASE_COMPASS,
    RELEASE_COMPASS_DATA,
    new_graph,
)
from src.domain.history import generated_at
from src.domain.report import Report


def report_iri(report_id: UUID) -> URIRef:
    return RELEASE_COMPASS_DATA[f"report/{report_id}"]


def report_triples(report: Report) -> Graph:
    """Return the ingested facts of one report; derived links come from rules.

    Strings are plain literals: in RDF 1.1 they are xsd:string, and SPARQL
    bindings of Python strings match them.
    """
    graph = new_graph()
    report_node = report_iri(report.report_id)
    graph.add((report_node, RDF.type, RELEASE_COMPASS.Report))
    graph.add(
        (
            report_node,
            RELEASE_COMPASS.generated_at,
            Literal(generated_at(report), datatype=XSD.dateTime),
        )
    )
    if report.ingestion_sequence is not None:
        graph.add(
            (
                report_node,
                RELEASE_COMPASS.ingestion_sequence,
                Literal(report.ingestion_sequence, datatype=XSD.integer),
            )
        )
    if report.source_fingerprint is not None:
        graph.add(
            (
                report_node,
                RELEASE_COMPASS.source_fingerprint,
                Literal(report.source_fingerprint),
            )
        )
    for path in dict.fromkeys([report.source_path, *report.source_paths]):
        if path is not None:
            graph.add(
                (
                    report_node,
                    RELEASE_COMPASS.source_path,
                    Literal(path),
                )
            )
    return graph
