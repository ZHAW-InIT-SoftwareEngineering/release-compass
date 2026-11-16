import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from src.adapters.outbound.ontology.release_compass_ontology import report_iri
from src.adapters.outbound.ontology.turtle_knowledge_base import (
    FACTS_FILE,
    TurtleKnowledgeBase,
    assessment_file,
)
from src.domain.gates.performance.measurements import SUPPORTED, performance_measure
from tests.adapters.outbound.ontology.examples import (
    POLICY,
    REPORT_ID,
    TARGETS,
    VERSION,
    acceptance,
    performance_gate,
    report,
)

OUTCOMES = """
SELECT ?name ?outcome WHERE {
    ?gate release-compass:has_assessment ?assessment .
    ?assessment release-compass:assesses/release-compass:metric_name ?name ;
                release-compass:outcome ?outcome .
}
ORDER BY ?name
"""


class TurtleKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name) / "kb"
        self.kb = TurtleKnowledgeBase(self.directory)

    def reopen(self) -> TurtleKnowledgeBase:
        return TurtleKnowledgeBase(self.directory)

    def store_example(self) -> None:
        self.kb.save_import_batch([report()], {})

    def test_starts_empty_without_files(self):
        self.assertEqual(self.kb.import_state(), (None, 0))
        self.assertIsNone(self.kb.get_by_fingerprint("9b1c"))
        self.assertFalse(self.directory.exists())

    def test_import_batch_is_saved_and_found_by_fingerprint(self):
        self.store_example()
        kb = self.reopen()
        self.assertEqual(
            kb.import_state(), (datetime(2026, 11, 9, 14, 3, tzinfo=UTC), 4)
        )
        stored = kb.get_by_fingerprint("9b1c")
        assert stored is not None
        self.assertEqual(stored.report_id, REPORT_ID)
        self.assertEqual(
            (
                stored.generated_at_date,
                stored.generated_at_time,
                stored.ingestion_sequence,
            ),
            ("2026-11-09", "14:03:00", 4),
        )
        self.assertEqual(
            stored.source_paths, ["data/raw/renamed.html", "data/raw/report.html"]
        )

    def test_aliases_extend_stored_reports_and_need_a_known_target(self):
        self.store_example()
        self.kb.save_import_batch([], {REPORT_ID: ["data/raw/copy.html"]})
        stored = self.reopen().get_by_fingerprint("9b1c")
        assert stored is not None
        self.assertIn("data/raw/copy.html", stored.source_paths)
        unknown = UUID(int=1)
        with self.assertRaisesRegex(ValueError, "Alias target"):
            self.kb.save_import_batch([], {unknown: ["x.html"]})

    def test_measurements_equal_what_scoring_reads_from_the_gate(self):
        self.store_example()
        kb = self.reopen()
        measure = performance_measure(performance_gate())
        for metric, statistics in SUPPORTED.items():
            for statistic in statistics:
                with self.subTest(metric=metric, statistic=statistic):
                    self.assertEqual(
                        kb.measurements(REPORT_ID, "performance", metric, statistic),
                        measure(metric, statistic),
                    )

    def test_assessment_needs_an_open_version(self):
        with self.assertRaisesRegex(RuntimeError, "Open an assessment version"):
            self.kb.add_gate_assessment(
                REPORT_ID, "performance", acceptance(), TARGETS, POLICY
            )

    def test_assessment_is_saved_per_version_and_leaves_facts_unchanged(self):
        self.store_example()
        facts = (self.directory / FACTS_FILE).read_bytes()
        self.kb.open_assessment(VERSION)
        self.kb.add_gate_assessment(
            REPORT_ID, "performance", acceptance(), TARGETS, POLICY
        )
        self.kb.save()

        self.assertEqual((self.directory / FACTS_FILE).read_bytes(), facts)
        self.assertTrue((self.directory / assessment_file(VERSION)).exists())
        kb = self.reopen()
        self.assertEqual(kb.select(OUTCOMES), [])
        kb.open_assessment(VERSION)
        self.assertEqual(
            [
                (row["name"], str(row["outcome"]).rsplit("#")[-1])
                for row in kb.select(OUTCOMES)
            ],
            [("response_time", "fail"), ("throughput", "pass")],
        )
        kb.open_assessment("other")
        self.assertEqual(kb.select(OUTCOMES), [])

    def test_select_sees_facts_with_plain_values(self):
        self.store_example()
        rows = self.reopen().select(
            "SELECT ?report WHERE { ?report ai2core:has_id ?id }",
            {"id": str(REPORT_ID)},
        )
        self.assertEqual(rows, [{"report": str(report_iri(REPORT_ID))}])
        self.assertFalse((self.directory / f"{FACTS_FILE}.tmp").exists())


if __name__ == "__main__":
    unittest.main()
