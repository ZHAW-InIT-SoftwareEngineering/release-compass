import unittest
from pathlib import Path

from rdflib import OWL, RDF, RDFS, XSD, Graph, URIRef

from src.adapters.outbound.ontology.assessment_triples import assessment_triples
from src.adapters.outbound.ontology.release_compass_ontology import (
    AI2CORE,
    RELEASE_COMPASS,
)
from src.adapters.outbound.ontology.report_triples import report_triples
from tests.adapters.outbound.ontology.examples import (
    POLICY,
    REPORT_ID,
    TARGETS,
    VERSION,
    acceptance,
    report,
)

ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = ROOT / "ontology/release-compass.ttl"
AI_SQUARE = ROOT / "docs/implementation/ai_sqaure_ontology/ai-square-extended.ttl"

RC = RELEASE_COMPASS
CLASSES = {RC.Report, RC.MetricAssessment, RC.Outcome}
# Property -> (domain or None when shared, range). Mirrors the ontology diagram.
OBJECT_PROPERTIES = {
    RC.previous_report: (RC.Report, RC.Report),
    RC.baseline_report: (RC.Report, RC.Report),
    RC.contains_gate: (RC.Report, AI2CORE.QualityGate),
    RC.baseline_gate: (AI2CORE.QualityGate, AI2CORE.QualityGate),
    RC.produces_metric: (AI2CORE.QualityGate, AI2CORE.Metric),
    RC.measured_from: (AI2CORE.Metric, AI2CORE.Source),
    RC.has_assessment: (AI2CORE.QualityGate, RC.MetricAssessment),
    RC.assesses: (RC.MetricAssessment, AI2CORE.Target),
    RC.based_on: (RC.MetricAssessment, AI2CORE.Metric),
    RC.outcome: (None, RC.Outcome),
}
DATATYPE_PROPERTIES = {
    RC.generated_at: (RC.Report, XSD.dateTime),
    RC.ingestion_sequence: (RC.Report, XSD.integer),
    RC.source_fingerprint: (RC.Report, XSD.string),
    RC.source_path: (RC.Report, XSD.string),
    RC.is_root: (RC.Report, XSD.boolean),
    RC.gate_type: (AI2CORE.QualityGate, XSD.string),
    RC.executed_at: (AI2CORE.QualityGate, XSD.dateTime),
    RC.source_name: (AI2CORE.Source, XSD.string),
    RC.metric_name: (None, XSD.string),
    RC.unit: (None, XSD.string),
    RC.statistic: (AI2CORE.Metric, XSD.string),
    RC.value: (AI2CORE.Metric, XSD.decimal),
    RC.request_count: (AI2CORE.Metric, XSD.decimal),
    RC.field_path: (AI2CORE.Metric, XSD.string),
    RC.meets_target: (AI2CORE.Metric, XSD.boolean),
    RC.excluded_reason: (AI2CORE.Metric, XSD.string),
    RC.description: (AI2CORE.Target, XSD.string),
    RC.min: (AI2CORE.Target, XSD.decimal),
    RC.max: (AI2CORE.Target, XSD.decimal),
    RC.min_score: (AI2CORE.Target, XSD.decimal),
    RC.score: (RC.MetricAssessment, XSD.decimal),
    RC.reason: (None, XSD.string),
    RC.policy_version: (RC.MetricAssessment, XSD.string),
}
# Several values per subject: aliases, one result per assessment version,
# several metrics per assessment.
NOT_FUNCTIONAL = {
    RC.source_path,
    RC.baseline_report,
    RC.contains_gate,
    RC.baseline_gate,
    RC.produces_metric,
    RC.has_assessment,
    RC.based_on,
    RC.outcome,
    RC.meets_target,
    RC.excluded_reason,
    RC.reason,
}


def _mapped_graph() -> Graph:
    """Everything the ontology mappers write for the example report."""
    graph = report_triples(report())
    graph += assessment_triples(
        REPORT_ID, "performance", acceptance(), TARGETS, VERSION, POLICY
    )
    return graph


class ReleaseCompassVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = Graph().parse(VOCABULARY, format="turtle")
        cls.ai_square = Graph().parse(AI_SQUARE, format="turtle")

    def test_declares_the_ontology(self):
        ontology = URIRef(str(RC).removesuffix("#"))
        self.assertEqual(set(self.graph.subjects(RDF.type, OWL.Ontology)), {ontology})

    def test_declares_classes_without_property_axioms(self):
        for cls in CLASSES:
            with self.subTest(cls=cls):
                self.assertIn((cls, RDF.type, OWL.Class), self.graph)
                self.assertIsNone(self.graph.value(cls, RDFS.domain))
                self.assertIsNotNone(self.graph.value(cls, RDFS.comment))

    def test_declares_the_three_outcomes(self):
        outcomes = set(self.graph.subjects(RDF.type, RC.Outcome))
        self.assertEqual(outcomes, {RC["pass"], RC.fail, RC.unknown})

    def test_declares_object_properties(self):
        for prop, (domain, range_) in OBJECT_PROPERTIES.items():
            with self.subTest(prop=prop):
                self._assert_property(prop, OWL.ObjectProperty, domain, range_)

    def test_declares_datatype_properties(self):
        for prop, (domain, range_) in DATATYPE_PROPERTIES.items():
            with self.subTest(prop=prop):
                self._assert_property(prop, OWL.DatatypeProperty, domain, range_)

    def test_functional_unless_several_values_are_expected(self):
        for prop in OBJECT_PROPERTIES | DATATYPE_PROPERTIES:
            with self.subTest(prop=prop):
                functional = (prop, RDF.type, OWL.FunctionalProperty) in self.graph
                self.assertEqual(functional, prop not in NOT_FUNCTIONAL)

    def test_declares_no_terms_beyond_the_tested_ones(self):
        declared = {
            term
            for kind in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty)
            for term in self.graph.subjects(RDF.type, kind)
        }
        self.assertEqual(
            declared, CLASSES | set(OBJECT_PROPERTIES) | set(DATATYPE_PROPERTIES)
        )

    def test_mappers_use_only_declared_terms(self):
        used = _used_terms(_mapped_graph())
        own = {term for term in used if term.startswith(str(RC))}
        self.assertEqual(own - _declared(self.graph), set())
        reused = {term for term in used if term.startswith(str(AI2CORE))}
        self.assertEqual(reused - _declared(self.ai_square), set())

    def _assert_property(self, prop, kind, domain, range_):
        self.assertIn((prop, RDF.type, kind), self.graph)
        self.assertIsNotNone(self.graph.value(prop, RDFS.comment))
        domains = set(self.graph.objects(prop, RDFS.domain))
        self.assertEqual(domains, set() if domain is None else {domain})
        self.assertEqual(set(self.graph.objects(prop, RDFS.range)), {range_})


def _used_terms(graph: Graph) -> set[URIRef]:
    predicates = {p for p in graph.predicates() if isinstance(p, URIRef)}
    classes = {o for o in graph.objects(None, RDF.type) if isinstance(o, URIRef)}
    # Outcome values are individuals of the vocabulary as well.
    outcomes = {o for o in graph.objects(None, RC.outcome) if isinstance(o, URIRef)}
    return predicates | classes | outcomes


def _declared(vocabulary: Graph) -> set[URIRef]:
    return {s for s in vocabulary.subjects() if isinstance(s, URIRef)}


if __name__ == "__main__":
    unittest.main()
