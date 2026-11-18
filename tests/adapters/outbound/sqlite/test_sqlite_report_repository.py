import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from src.adapters.outbound.sqlite.sqlite_report_repository import SQLiteReportRepository
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


class SQLiteReportRepositoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "db" / "reports.sqlite3"
        self.repository = self.reopen()

    def reopen(self) -> SQLiteReportRepository:
        repository = SQLiteReportRepository(self.path)
        self.addCleanup(repository.close)
        return repository

    def store_example(self) -> None:
        self.repository.save_import_batch([report()], {})

    def test_starts_empty(self):
        self.assertEqual(self.repository.import_state(), (None, 0))
        self.assertIsNone(self.repository.get_by_fingerprint("9b1c"))

    def test_import_batch_is_saved_and_found_by_fingerprint(self):
        self.store_example()
        repository = self.reopen()
        self.assertEqual(
            repository.import_state(), (datetime(2026, 11, 9, 14, 3, tzinfo=UTC), 4)
        )
        stored = repository.get_by_fingerprint("9b1c")
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
        self.assertEqual(repository.gate_types(REPORT_ID), {"performance"})

    def test_aliases_extend_stored_reports_and_need_a_known_target(self):
        self.store_example()
        self.repository.save_import_batch([], {REPORT_ID: ["data/raw/copy.html"]})
        stored = self.reopen().get_by_fingerprint("9b1c")
        assert stored is not None
        self.assertIn("data/raw/copy.html", stored.source_paths)
        with self.assertRaisesRegex(ValueError, "Alias target"):
            self.repository.save_import_batch([], {UUID(int=1): ["x.html"]})

    def test_failed_batch_stores_nothing(self):
        duplicate = report(report_id=UUID(int=2))
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_import_batch([report(), duplicate], {})
        self.assertEqual(self.reopen().import_state(), (None, 0))

    def test_measurements_equal_what_scoring_reads_from_the_gate(self):
        self.store_example()
        repository = self.reopen()
        measure = performance_measure(performance_gate())
        for metric, statistics in SUPPORTED.items():
            for statistic in statistics:
                with self.subTest(metric=metric, statistic=statistic):
                    self.assertEqual(
                        repository.measurements(
                            REPORT_ID, "performance", metric, statistic
                        ),
                        measure(metric, statistic),
                    )

    def test_assessment_needs_an_open_version(self):
        with self.assertRaisesRegex(RuntimeError, "Open an assessment version"):
            self.repository.add_gate_assessment(
                REPORT_ID, "performance", acceptance(), TARGETS, POLICY
            )

    def test_assessment_stores_metric_and_source_results(self):
        self.store_example()
        self.repository.open_assessment(VERSION)
        self.repository.add_gate_assessment(
            REPORT_ID, "performance", acceptance(), TARGETS, POLICY
        )
        self.repository.save()
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        self.assertEqual(
            connection.execute(
                "SELECT name, outcome FROM metric_assessments ORDER BY name"
            ).fetchall(),
            [("response_time", "fail"), ("throughput", "pass")],
        )
        self.assertEqual(
            connection.execute(
                """SELECT source, excluded, meets_target FROM source_assessments
                   WHERE name = 'response_time' ORDER BY source"""
            ).fetchall(),
            [("Login", 0, 1), ("Logout", 1, None), ("Search", 0, 0)],
        )

    def test_worker_threads_read_unsaved_results(self):
        # LangGraph's ToolNode calls tools from worker threads (ADR 0015).
        self.store_example()
        self.repository.open_assessment(VERSION)
        self.repository.add_gate_assessment(
            REPORT_ID, "performance", acceptance(), TARGETS, POLICY
        )
        self.repository.apply_rules(REPORT_ID, {"performance"})
        with ThreadPoolExecutor(max_workers=4) as pool:
            summaries = list(pool.map(self.repository.describe_report, [REPORT_ID] * 8))
        self.assertEqual(
            {summary.outcome for summary in summaries if summary is not None},
            {acceptance().outcome},
        )

    def test_rejects_a_file_with_an_older_schema(self):
        legacy = self.path.with_name("legacy.sqlite3")
        with sqlite3.connect(legacy) as connection:
            connection.execute("CREATE TABLE reports (report_id TEXT)")
        connection.close()
        with self.assertRaisesRegex(ValueError, "older schema"):
            SQLiteReportRepository(legacy)


if __name__ == "__main__":
    unittest.main()
