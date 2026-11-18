import unittest
from decimal import Decimal

from rdflib import RDF, XSD, Literal

from src.adapters.outbound.ontology.metric_triples import metric_triples
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    gate_iri,
    metric_iri,
    source_iri,
)
from src.domain.scoring import Measurement
from tests.adapters.outbound.ontology.examples import REPORT_ID

GATE = gate_iri(REPORT_ID, "performance")
LOGIN = Measurement(
    "Log in/out", "transactions[Log in/out].response_time.p90", 800.5, "ms", 300
)


class MetricTriplesTests(unittest.TestCase):
    def test_maps_a_measurement_with_its_source(self):
        graph = metric_triples(LOGIN, "response_time", "p90", GATE)
        node = metric_iri(GATE, "Log in/out", "response_time", "p90")
        source = source_iri("Log in/out")
        self.assertIn((GATE, RELEASE_COMPASS.produces_metric, node), graph)
        self.assertIn((node, RDF.type, AI2CORE.Metric), graph)
        self.assertIn((node, RELEASE_COMPASS.measured_from, source), graph)
        self.assertEqual(
            graph.value(source, RELEASE_COMPASS.source_name), Literal("Log in/out")
        )
        expected = {
            RELEASE_COMPASS.metric_name: Literal("response_time"),
            RELEASE_COMPASS.statistic: Literal("p90"),
            RELEASE_COMPASS.field_path: Literal(LOGIN.path),
            RELEASE_COMPASS.value: Literal(Decimal("800.5"), datatype=XSD.decimal),
            RELEASE_COMPASS.unit: Literal("ms"),
            RELEASE_COMPASS.request_count: Literal(Decimal(300), datatype=XSD.decimal),
        }
        for prop, value in expected.items():
            with self.subTest(prop=prop):
                self.assertEqual(graph.value(node, prop), value)

    def test_escapes_names_in_iris(self):
        node = metric_iri(GATE, "Log in/out", "response_time", "p90")
        self.assertTrue(str(node).endswith("/metric/Log%20in%2Fout/response_time/p90"))

    def test_leaves_out_missing_value_unit_and_weight(self):
        missing = Measurement("Logout", "transactions[Logout].x", None, None, None)
        graph = metric_triples(missing, "response_time", "p90", GATE)
        node = metric_iri(GATE, "Logout", "response_time", "p90")
        for prop in (
            RELEASE_COMPASS.value,
            RELEASE_COMPASS.unit,
            RELEASE_COMPASS.request_count,
        ):
            with self.subTest(prop=prop):
                self.assertIsNone(graph.value(node, prop))

    def test_rejects_non_finite_values(self):
        infinite = Measurement("Login", "path", float("inf"), "ms", 1)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            metric_triples(infinite, "response_time", "p90", GATE)


if __name__ == "__main__":
    unittest.main()
