import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from src.adapters.outbound.ontology.report_triples import report_iri
from src.adapters.outbound.ontology.turtle_knowledge_base import (
    FACTS_FILE,
    TurtleKnowledgeBase,
)
from src.domain.report import Report

FIRST_ID = UUID("3f2a6c1e-0000-4000-8000-000000000001")
SECOND_ID = UUID("3f2a6c1e-0000-4000-8000-000000000002")

REPORTS_BY_TIME = """
SELECT ?report ?generated_at WHERE {
    ?report a release-compass:Report ;
            release-compass:generated_at ?generated_at .
} ORDER BY ?generated_at
"""


def _report(report_id: UUID, time: str, sequence: int) -> Report:
    return Report(
        report_id=report_id,
        source_path=f"data/raw/{sequence}.html",
        generated_at_date="2026-11-09",
        generated_at_time=time,
        source_fingerprint=f"hash-{sequence}",
        ingestion_sequence=sequence,
    )


class TurtleKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.kb = TurtleKnowledgeBase(self.directory / "kb")

    def test_starts_empty_without_facts_file(self):
        self.assertEqual(self.kb.select(REPORTS_BY_TIME), [])
        self.assertFalse((self.directory / "kb" / FACTS_FILE).exists())

    def test_save_and_reload_round_trip(self):
        self.kb.add_report(_report(FIRST_ID, "14:03:00", 1))
        self.kb.save()

        reloaded = TurtleKnowledgeBase(self.directory / "kb")
        self.assertEqual(
            reloaded.select(REPORTS_BY_TIME), self.kb.select(REPORTS_BY_TIME)
        )
        self.assertTrue((self.directory / "kb" / FACTS_FILE).exists())
        self.assertFalse((self.directory / "kb" / f"{FACTS_FILE}.tmp").exists())

    def test_adding_the_same_report_twice_stores_it_once(self):
        report = _report(FIRST_ID, "14:03:00", 1)
        self.kb.add_report(report)
        self.kb.add_report(report)
        self.assertEqual(len(self.kb.select(REPORTS_BY_TIME)), 1)

    def test_select_returns_plain_values_in_query_order(self):
        self.kb.add_report(_report(SECOND_ID, "15:00:00", 2))
        self.kb.add_report(_report(FIRST_ID, "14:03:00", 1))

        self.assertEqual(
            self.kb.select(REPORTS_BY_TIME),
            [
                {
                    "report": str(report_iri(FIRST_ID)),
                    "generated_at": datetime(2026, 11, 9, 14, 3, tzinfo=UTC),
                },
                {
                    "report": str(report_iri(SECOND_ID)),
                    "generated_at": datetime(2026, 11, 9, 15, 0, tzinfo=UTC),
                },
            ],
        )

    def test_select_binds_python_values(self):
        self.kb.add_report(_report(FIRST_ID, "14:03:00", 1))
        self.kb.add_report(_report(SECOND_ID, "15:00:00", 2))

        rows = self.kb.select(
            """
            SELECT ?report WHERE {
                ?report release-compass:source_fingerprint ?fingerprint .
            }
            """,
            {"fingerprint": "hash-2"},
        )
        self.assertEqual(rows, [{"report": str(report_iri(SECOND_ID))}])


if __name__ == "__main__":
    unittest.main()
