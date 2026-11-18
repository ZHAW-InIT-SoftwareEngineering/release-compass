import unittest
from decimal import Decimal

from rdflib import RDF, XSD, Literal

from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    target_iri,
)
from src.adapters.outbound.ontology.target_triples import target_triples
from tests.adapters.outbound.ontology.examples import TARGETS, VERSION


def _decimal(value: str) -> Literal:
    return Literal(Decimal(value), datatype=XSD.decimal)


class TargetTriplesTests(unittest.TestCase):
    def test_maps_an_upper_bounded_target(self):
        graph = target_triples("response_time", TARGETS["response_time"], VERSION)
        node = target_iri(VERSION, "response_time")
        self.assertIn((node, RDF.type, AI2CORE.Target), graph)
        expected = {
            RELEASE_COMPASS.metric_name: Literal("response_time"),
            AI2CORE.aggregation: Literal("p90"),
            RELEASE_COMPASS.unit: Literal("ms"),
            RELEASE_COMPASS.max: _decimal("1000"),
            RELEASE_COMPASS.min_score: _decimal("0.8"),
        }
        for prop, value in expected.items():
            with self.subTest(prop=prop):
                self.assertEqual(graph.value(node, prop), value)
        self.assertIsNone(graph.value(node, RELEASE_COMPASS.min))

    def test_maps_a_lower_bounded_target(self):
        graph = target_triples("throughput", TARGETS["throughput"], VERSION)
        node = target_iri(VERSION, "throughput")
        self.assertEqual(graph.value(node, RELEASE_COMPASS.min), _decimal("40"))
        self.assertIsNone(graph.value(node, RELEASE_COMPASS.max))

    def test_targets_of_different_versions_are_different_nodes(self):
        self.assertNotEqual(
            target_iri("v1", "response_time"), target_iri("v2", "response_time")
        )


if __name__ == "__main__":
    unittest.main()
