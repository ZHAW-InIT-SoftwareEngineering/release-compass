import unittest
from decimal import Decimal

from rdflib import RDF, XSD, Literal

from src.adapters.outbound.ontology.assessment_triples import assessment_triples
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    assessment_iri,
    gate_iri,
    metric_iri,
    target_iri,
)
from tests.adapters.outbound.ontology.examples import (
    POLICY,
    REPORT_ID,
    TARGETS,
    VERSION,
    acceptance,
)

GATE = gate_iri(REPORT_ID, "performance")


def _metric(source: str):
    return metric_iri(GATE, source, "response_time", "p90")


class AssessmentTriplesTests(unittest.TestCase):
    def setUp(self):
        self.graph = assessment_triples(
            REPORT_ID, "performance", acceptance(), TARGETS, VERSION, POLICY
        )
        self.response_time = assessment_iri(GATE, VERSION, "response_time")

    def test_writes_the_gate_outcome_scored_in_python(self):
        self.assertEqual(
            self.graph.value(GATE, RELEASE_COMPASS.outcome), RELEASE_COMPASS.fail
        )

    def test_maps_each_metric_acceptance(self):
        node = self.response_time
        self.assertIn((GATE, RELEASE_COMPASS.has_assessment, node), self.graph)
        self.assertIn((node, RDF.type, RELEASE_COMPASS.MetricAssessment), self.graph)
        expected = {
            RELEASE_COMPASS.assesses: target_iri(VERSION, "response_time"),
            RELEASE_COMPASS.outcome: RELEASE_COMPASS.fail,
            RELEASE_COMPASS.score: Literal(Decimal("0.75"), datatype=XSD.decimal),
            RELEASE_COMPASS.policy_version: Literal(POLICY),
        }
        for prop, value in expected.items():
            with self.subTest(prop=prop):
                self.assertEqual(self.graph.value(node, prop), value)
        throughput = assessment_iri(GATE, VERSION, "throughput")
        self.assertEqual(
            self.graph.value(throughput, RELEASE_COMPASS.outcome),
            RELEASE_COMPASS["pass"],
        )

    def test_links_the_targets_of_this_version(self):
        for name in TARGETS:
            with self.subTest(target=name):
                target = target_iri(VERSION, name)
                self.assertIn(
                    (GATE, AI2CORE.evaluated_by_requirement, target), self.graph
                )
                self.assertIn((target, RDF.type, AI2CORE.Target), self.graph)

    def test_records_per_transaction_results_on_the_scored_metrics(self):
        self.assertEqual(
            set(self.graph.objects(self.response_time, RELEASE_COMPASS.based_on)),
            {_metric("Login"), _metric("Search"), _metric("Logout")},
        )
        self.assertEqual(
            self.graph.value(_metric("Login"), RELEASE_COMPASS.meets_target),
            Literal(True),
        )
        self.assertEqual(
            self.graph.value(_metric("Search"), RELEASE_COMPASS.meets_target),
            Literal(False),
        )
        self.assertEqual(
            self.graph.value(_metric("Logout"), RELEASE_COMPASS.excluded_reason),
            Literal("No observations"),
        )
        self.assertIsNone(
            self.graph.value(_metric("Logout"), RELEASE_COMPASS.meets_target)
        )

    def test_writes_no_report_facts(self):
        facts = {RELEASE_COMPASS.generated_at, RELEASE_COMPASS.produces_metric}
        self.assertEqual(set(self.graph.predicates()) & facts, set())


if __name__ == "__main__":
    unittest.main()
