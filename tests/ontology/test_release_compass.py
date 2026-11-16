import unittest
from pathlib import Path

from rdflib import OWL, RDF, RDFS, XSD, Graph, URIRef

from src.adapters.outbound.ontology.release_compass_ontology import RELEASE_COMPASS

VOCABULARY = Path(__file__).resolve().parents[2] / "ontology/release-compass.ttl"

OBJECT_PROPERTIES = {RELEASE_COMPASS.previous_report: RELEASE_COMPASS.Report}
DATATYPE_PROPERTIES = {
    RELEASE_COMPASS.generated_at: XSD.dateTime,
    RELEASE_COMPASS.ingestion_sequence: XSD.integer,
    RELEASE_COMPASS.source_fingerprint: XSD.string,
    RELEASE_COMPASS.source_path: XSD.string,
    RELEASE_COMPASS.is_root: XSD.boolean,
}
NOT_FUNCTIONAL = {RELEASE_COMPASS.source_path}


class ReleaseCompassVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = Graph().parse(VOCABULARY, format="turtle")

    def test_declares_the_ontology(self):
        ontology = URIRef(str(RELEASE_COMPASS).removesuffix("#"))
        self.assertEqual(set(self.graph.subjects(RDF.type, OWL.Ontology)), {ontology})

    def test_declares_report_as_class_without_property_axioms(self):
        self.assertIn((RELEASE_COMPASS.Report, RDF.type, OWL.Class), self.graph)
        self.assertIsNone(self.graph.value(RELEASE_COMPASS.Report, RDFS.domain))
        self.assertIsNone(self.graph.value(RELEASE_COMPASS.Report, RDFS.range))
        self.assertIsNotNone(self.graph.value(RELEASE_COMPASS.Report, RDFS.comment))

    def test_declares_report_object_properties(self):
        for prop, range_ in OBJECT_PROPERTIES.items():
            with self.subTest(prop=prop):
                self._assert_property(prop, OWL.ObjectProperty, range_)

    def test_declares_report_datatype_properties(self):
        for prop, range_ in DATATYPE_PROPERTIES.items():
            with self.subTest(prop=prop):
                self._assert_property(prop, OWL.DatatypeProperty, range_)

    def test_only_alias_paths_have_several_values(self):
        for prop in OBJECT_PROPERTIES | DATATYPE_PROPERTIES:
            with self.subTest(prop=prop):
                functional = (prop, RDF.type, OWL.FunctionalProperty) in self.graph
                self.assertEqual(functional, prop not in NOT_FUNCTIONAL)

    def _assert_property(self, prop, kind, range_):
        self.assertIn((prop, RDF.type, kind), self.graph)
        self.assertEqual(
            set(self.graph.objects(prop, RDFS.domain)), {RELEASE_COMPASS.Report}
        )
        self.assertEqual(set(self.graph.objects(prop, RDFS.range)), {range_})


if __name__ == "__main__":
    unittest.main()
