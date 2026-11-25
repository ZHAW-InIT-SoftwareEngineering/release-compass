import unittest
from datetime import UTC, datetime

from rdflib import RDF, XSD, Literal

from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
    gate_iri,
    report_iri,
)
from src.adapters.outbound.ontology.report_triples import report_triples
from tests.adapters.outbound.ontology.examples import REPORT_ID
from tests.adapters.outbound.ontology.examples import report as _report


class ReportTriplesTests(unittest.TestCase):
    def test_report_iri_uses_the_report_id(self):
        self.assertEqual(
            str(report_iri(REPORT_ID)),
            "https://github.com/ZHAW-InIT-SoftwareEngineering/release-compass/"
            f"data/report/{REPORT_ID}",
        )

    def test_maps_report_fields_to_typed_literals(self):
        graph = report_triples(_report())
        node = report_iri(REPORT_ID)
        self.assertIn((node, RDF.type, RELEASE_COMPASS.Report), graph)
        self.assertEqual(graph.value(node, AI2CORE.has_id), Literal(str(REPORT_ID)))
        self.assertEqual(
            graph.value(node, RELEASE_COMPASS.generated_at),
            Literal(datetime(2026, 11, 9, 14, 3, tzinfo=UTC), datatype=XSD.dateTime),
        )
        self.assertEqual(
            graph.value(node, RELEASE_COMPASS.ingestion_sequence),
            Literal(4, datatype=XSD.integer),
        )
        self.assertEqual(
            graph.value(node, RELEASE_COMPASS.source_fingerprint),
            Literal("9b1c"),
        )

    def test_maps_each_alias_path_once(self):
        graph = report_triples(_report())
        self.assertEqual(
            {str(path) for path in graph.objects(None, RELEASE_COMPASS.source_path)},
            {"data/raw/report.html", "data/raw/renamed.html"},
        )
        self.assertEqual(len(list(graph.objects(None, RELEASE_COMPASS.source_path))), 2)

    def test_leaves_out_unassigned_fields_and_derived_links(self):
        graph = report_triples(
            _report(
                source_path=None,
                source_paths=[],
                source_fingerprint=None,
                ingestion_sequence=None,
                gates=[],
            )
        )
        self.assertEqual(
            set(graph.predicates()),
            {RDF.type, AI2CORE.has_id, RELEASE_COMPASS.generated_at},
        )

    def test_includes_its_gates(self):
        graph = report_triples(_report())
        gate = gate_iri(REPORT_ID, "performance")
        self.assertIn(
            (report_iri(REPORT_ID), RELEASE_COMPASS.contains_gate, gate), graph
        )
        self.assertIn((gate, RDF.type, AI2CORE.QualityGate), graph)

    def test_requires_a_complete_timestamp(self):
        with self.assertRaisesRegex(ValueError, "complete generated-at"):
            report_triples(_report(generated_at_time=None))

    def test_binds_the_release_compass_prefix(self):
        turtle = report_triples(_report()).serialize(format="turtle")
        self.assertIn("@prefix release-compass:", turtle)
        self.assertIn("release-compass:Report", turtle)


if __name__ == "__main__":
    unittest.main()
