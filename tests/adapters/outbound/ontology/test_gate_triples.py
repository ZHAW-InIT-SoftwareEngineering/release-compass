import unittest

from rdflib import RDF, Literal

from src.adapters.outbound.ontology.gate_triples import gate_triples, gate_type
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    gate_iri,
    report_iri,
)
from src.domain.gates.gate import Gate
from src.domain.gates.performance.measurements import SUPPORTED
from tests.adapters.outbound.ontology.examples import REPORT_ID, performance_gate


class GateTriplesTests(unittest.TestCase):
    def setUp(self):
        self.graph = gate_triples(performance_gate(), REPORT_ID)
        self.gate = gate_iri(REPORT_ID, "performance")

    def test_maps_the_gate_run_into_its_report(self):
        self.assertIn(
            (report_iri(REPORT_ID), RELEASE_COMPASS.contains_gate, self.gate),
            self.graph,
        )
        self.assertIn((self.gate, RDF.type, AI2CORE.QualityGate), self.graph)
        self.assertEqual(
            self.graph.value(self.gate, RELEASE_COMPASS.gate_type),
            Literal("performance"),
        )

    def test_stores_every_measurement_scoring_can_request(self):
        # Per transaction for each supported statistic; throughput once overall.
        transactions, statistics = (
            3,
            sum(len(SUPPORTED[name]) for name in ("response_time", "request_outcomes")),
        )
        metrics = set(self.graph.objects(self.gate, RELEASE_COMPASS.produces_metric))
        self.assertEqual(len(metrics), transactions * statistics + 1)

    def test_rejects_unknown_gate_types(self):
        with self.assertRaisesRegex(ValueError, "Unsupported gate type Gate"):
            gate_triples(Gate(), REPORT_ID)
        with self.assertRaisesRegex(ValueError, "Unsupported gate type"):
            gate_type(Gate())


if __name__ == "__main__":
    unittest.main()
