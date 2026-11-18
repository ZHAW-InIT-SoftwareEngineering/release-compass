"""Map a scored gate (src/domain/scoring.py) to MetricAssessment triples."""

from collections.abc import Mapping
from uuid import UUID

from rdflib import RDF, Graph, Literal, URIRef

from src.adapters.outbound.ontology.metric_triples import decimal_literal
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    assessment_iri,
    gate_iri,
    metric_iri,
    new_graph,
    target_iri,
)
from src.adapters.outbound.ontology.target_triples import target_triples
from src.domain.assessment import GateAcceptance, MetricAcceptance, Outcome
from src.domain.targets import MetricTarget

OUTCOMES: dict[Outcome, URIRef] = {
    "pass": RELEASE_COMPASS["pass"],
    "fail": RELEASE_COMPASS.fail,
    "unknown": RELEASE_COMPASS.unknown,
}


def assessment_triples(
    report_id: UUID,
    gate_type: str,
    acceptance: GateAcceptance,
    targets: Mapping[str, MetricTarget],
    version: str,
    policy_version: str,
) -> Graph:
    """Results of one assessment version; they never go into the report facts.

    The gate outcome is written as scored in Python (combine_outcomes).
    """
    graph = new_graph()
    gate = gate_iri(report_id, gate_type)
    graph.add((gate, RELEASE_COMPASS.outcome, OUTCOMES[acceptance.outcome]))
    for name, result in acceptance.metrics.items():
        target = targets[name]
        graph += target_triples(name, target, version)
        graph.add((gate, AI2CORE.evaluated_by_requirement, target_iri(version, name)))
        graph += _metric_assessment(gate, name, target, result, version, policy_version)
    return graph


def _metric_assessment(
    gate: URIRef,
    name: str,
    target: MetricTarget,
    result: MetricAcceptance,
    version: str,
    policy_version: str,
) -> Graph:
    graph = new_graph()
    node = assessment_iri(gate, version, name)
    graph.add((gate, RELEASE_COMPASS.has_assessment, node))
    graph.add((node, RDF.type, RELEASE_COMPASS.MetricAssessment))
    graph.add((node, RELEASE_COMPASS.assesses, target_iri(version, name)))
    graph.add((node, RELEASE_COMPASS.outcome, OUTCOMES[result.outcome]))
    graph.add((node, RELEASE_COMPASS.policy_version, Literal(policy_version)))
    if result.score is not None:
        graph.add((node, RELEASE_COMPASS.score, decimal_literal(result.score)))
    if result.reason is not None:
        graph.add((node, RELEASE_COMPASS.reason, Literal(result.reason)))
    for source in result.sources:
        metric = metric_iri(gate, source.name, target.metric, target.aggregation)
        graph.add((node, RELEASE_COMPASS.based_on, metric))
        if source.excluded:
            graph.add(
                (metric, RELEASE_COMPASS.excluded_reason, Literal(source.reason or ""))
            )
        elif source.penalty is None:
            if source.reason is not None:
                graph.add((metric, RELEASE_COMPASS.reason, Literal(source.reason)))
        else:
            graph.add(
                (metric, RELEASE_COMPASS.meets_target, Literal(source.penalty == 0))
            )
    return graph
