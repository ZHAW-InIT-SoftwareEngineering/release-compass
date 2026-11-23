import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.adapters.outbound.ontology.turtle_kb import TurtleKB
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.domain.report import Report

STORED_REPORTS = """
SELECT ?id ?sequence ?path WHERE {
    ?report a release-compass:Report ;
            ai2core:has_id ?id ;
            release-compass:ingestion_sequence ?sequence .
    OPTIONAL { ?report release-compass:source_path ?path }
}
"""


class ImportReportsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.path = self.directory / "report.html"
        self.path.write_text("first")
        self.ingestion = Mock()
        self.ingestion.ingest.side_effect = lambda *_: Report()

    def inputs(self, time="08:00:00"):
        return [ReportInput(self.path, "2026-09-02", time, source="test")]

    def run_import(self, inputs):
        return import_reports(inputs, self.ingestion, self.open_store())

    def test_stores_new_report_with_sequence_fingerprint_and_path(self):
        (report,) = self.run_import(self.inputs())
        self.assertEqual(report.ingestion_sequence, 1)
        self.assertIsNotNone(report.source_fingerprint)
        self.assertEqual(self.stored(), {str(report.report_id): {str(self.path)}})

    def test_repeat_and_rename_reuse_uuid_timestamps_and_skip_parser(self):
        (first,) = self.run_import(self.inputs())
        renamed = self.path.with_name("renamed.html")
        renamed.write_bytes(self.path.read_bytes())
        (reused,) = self.run_import(
            [ReportInput(renamed, "2020-01-01", "00:00:00", source="test")]
        )
        self.assertEqual(reused.report_id, first.report_id)
        self.assertEqual(reused.generated_at_date, "2026-09-02")
        self.assertEqual(reused.generated_at_time, "08:00:00")
        self.assertEqual(reused.ingestion_sequence, first.ingestion_sequence)
        self.assertEqual(self.ingestion.ingest.call_count, 1)
        self.assertEqual(
            self.stored(), {str(first.report_id): {str(self.path), str(renamed)}}
        )

    def test_changed_content_is_new_report_and_ties_use_ingestion_order(self):
        (first,) = self.run_import(self.inputs())
        self.path.write_text("second")
        (second,) = self.run_import(self.inputs())
        self.assertNotEqual(first.report_id, second.report_id)
        self.assertLess(first.ingestion_sequence, second.ingestion_sequence)
        self.assertEqual(len(self.stored()), 2)

    def test_rejects_backdated_batch_without_partial_imports_or_aliases(self):
        (first,) = self.run_import(self.inputs())
        later = self.path.with_name("later.html")
        earlier = self.path.with_name("earlier.html")
        renamed = self.path.with_name("alias.html")
        later.write_text("later")
        earlier.write_text("earlier")
        renamed.write_text("first")
        with self.assertRaisesRegex(ValueError, "Backdated"):
            self.run_import(
                [
                    ReportInput(later, "2026-09-02", "09:00:00", source="test"),
                    ReportInput(renamed, source="test"),
                    ReportInput(earlier, "2026-09-01", "09:00:00", source="test"),
                ]
            )
        self.assertEqual(self.stored(), {str(first.report_id): {str(self.path)}})

    def test_html_timestamp_precedes_config(self):
        self.ingestion.ingest.side_effect = lambda *_: Report(
            generated_at_date="2026-09-02", generated_at_time="10:00:00"
        )
        (result,) = self.run_import(self.inputs())
        self.assertEqual(result.generated_at_time, "10:00:00")

    def test_missing_html_and_config_timestamp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no complete generated-at"):
            self.run_import([ReportInput(self.path, source="test")])
        self.assertEqual(self.stored(), {})

    def test_rejects_partial_source_or_config_timestamp(self):
        self.ingestion.ingest.side_effect = lambda *_: Report(
            generated_at_date="2026-09-02"
        )
        with self.assertRaisesRegex(ValueError, "both generated-at"):
            self.run_import(self.inputs())
        self.ingestion.ingest.side_effect = lambda *_: Report()
        with self.assertRaisesRegex(ValueError, "both generated-at"):
            self.run_import([ReportInput(self.path, "2026-09-02", source="test")])
        self.assertEqual(self.stored(), {})

    def open_store(self) -> TurtleKB:
        return TurtleKB(self.directory / "kb")

    def stored(self) -> dict[str, set[str]]:
        paths: dict[str, set[str]] = {}
        for row in TurtleKB(self.directory / "kb").select(STORED_REPORTS):
            report_paths = paths.setdefault(str(row["id"]), set())
            if "path" in row:
                report_paths.add(str(row["path"]))
        return paths


if __name__ == "__main__":
    unittest.main()
