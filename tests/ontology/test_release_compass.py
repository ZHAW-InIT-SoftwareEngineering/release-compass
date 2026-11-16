import unittest
from pathlib import Path

from rdflib import OWL, RDF, RDFS, XSD, Graph, Namespace, URIRef

VOCABULARY = Path(__file__).resolve().parents[2] / "ontology/release-compass.ttl"
RC = Namespace(
    "https://github.com/ZHAW-InIT-SoftwareEngineering/release-compass/ontology#"
)

OBJECT_PROPERTIES = {RC.previous_report: RC.Report}
DATATYPE_PROPERTIES = {
    RC.generated_at: XSD.dateTime,
    RC.ingestion_sequence: XSD.integer,
    RC.source_fingerprint: XSD.string,
    RC.source_path: XSD.string,
    RC.is_root: XSD.boolean,
}
NOT_FUNCTIONAL = {RC.source_path}


class ReleaseCompassVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = Graph().parse(VOCABULARY, format="turtle")

    def test_declares_the_ontology(self):
        ontology = URIRef(str(RC).removesuffix("#"))
        self.assertEqual(set(self.graph.subjects(RDF.type, OWL.Ontology)), {ontology})

    def test_declares_report_as_class_without_property_axioms(self):
        self.assertIn((RC.Report, RDF.type, OWL.Class), self.graph)
        self.assertIsNone(self.graph.value(RC.Report, RDFS.domain))
        self.assertIsNone(self.graph.value(RC.Report, RDFS.range))
        self.assertIsNotNone(self.graph.value(RC.Report, RDFS.comment))

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
        self.assertEqual(set(self.graph.objects(prop, RDFS.domain)), {RC.Report})
        self.assertEqual(set(self.graph.objects(prop, RDFS.range)), {range_})


if __name__ == "__main__":
    unittest.main()
