"""Competency questions, answered identically by both stores."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from src.adapters.outbound.ontology.turtle_knowledge_base import TurtleKnowledgeBase
from src.adapters.outbound.sqlite.sqlite_report_repository import SQLiteReportRepository
from src.application.performance_assessment import build_performance_assessment_service
from src.application.use_cases.answer_report_questions import (
    ReportNotFoundError,
    ReportQuestionService,
)
from src.domain.report import Report
from src.domain.scoring import POLICY_VERSION
from tests.application.use_cases.test_assess_reports import scored_gate, targets


class QuestionContract(unittest.TestCase):
    """Three reports: passing root, failing, passing current."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.store = self.open_store()
        self.sequence = 0
        self.first = self.add(scored_gate(), time="08:00:00")
        self.failed = self.add(scored_gate(0.7), time="09:00:00")
        current = scored_gate()
        response_time = current.transactions["fast"].response_time
        assert response_time is not None
        response_time.p90 = 150
        self.current = self.add(current, time="10:00:00")
        self.service = self.assess()

    def open_store(self):
        raise NotImplementedError

    def add(self, *gates, time) -> UUID:
        self.sequence += 1
        report = Report(
            report_id=UUID(int=self.sequence),
            generated_at_date="2026-09-02",
            generated_at_time=time,
            source_fingerprint=str(self.sequence),
            ingestion_sequence=self.sequence,
            source_paths=[f"report-{self.sequence}.html"],
            gates=list(gates),
        )
        self.store.save_import_batch([report], {})
        return report.report_id

    def assess(self) -> ReportQuestionService:
        assessment = build_performance_assessment_service(self.store, targets())
        assessment.prepare()
        return ReportQuestionService(self.store, assessment.gates)

    def test_describe_report(self):
        summary = self.service.describe_report(self.current)
        self.assertEqual(summary.generated_at, datetime(2026, 9, 2, 10, tzinfo=UTC))
        self.assertEqual(summary.ingestion_sequence, 3)
        self.assertEqual(summary.source_paths, ["report-3.html"])
        self.assertEqual(summary.gate_types, ["performance"])
        self.assertEqual(summary.outcome, "pass")
        self.assertFalse(summary.is_root)
        self.assertEqual(summary.previous_report_id, self.failed)

    def test_unknown_report_is_not_found(self):
        unknown = UUID(int=99)
        for question in (
            self.service.describe_report,
            self.service.previous_report,
            self.service.baselines,
            self.service.explain_outcome,
        ):
            with (
                self.subTest(question=question.__name__),
                self.assertRaisesRegex(ReportNotFoundError, "was not found"),
            ):
                question(unknown)
        with self.assertRaisesRegex(ReportNotFoundError, "Baseline report"):
            self.service.compare_gate(
                self.current, unknown, "performance", "response_time", "p90"
            )

    def test_unassessed_report_has_no_outcome(self):
        later = self.add(scored_gate(), time="11:00:00")
        summary = self.service.describe_report(later)
        self.assertIsNone(summary.outcome)
        self.assertIsNone(summary.is_root)
        self.assertEqual(self.service.explain_outcome(later).gates[0].metrics, [])

    def test_previous_report_includes_failed_and_ends_at_root(self):
        previous = self.service.previous_report(self.current)
        assert previous is not None
        self.assertEqual(previous.report_id, self.failed)
        self.assertEqual(previous.outcome, "fail")
        self.assertIsNone(self.service.previous_report(self.first))
        self.assertTrue(self.service.describe_report(self.first).is_root)

    def test_baselines_skip_the_failed_report(self):
        result = self.service.baselines(self.current)
        self.assertEqual(result.baseline_report_id, self.first)
        (gate,) = result.gates
        self.assertEqual(gate.gate_type, "performance")
        self.assertEqual(gate.baseline_report_id, self.first)
        self.assertEqual(gate.policy_version, POLICY_VERSION)
        self.assertIsNone(self.service.baselines(self.first).baseline_report_id)

    def test_compare_gate_matches_sources(self):
        changes = self.service.compare_gate(
            self.current, self.first, "performance", "response_time", "p90"
        )
        self.assertEqual([change.source for change in changes], ["fast", "slow"])
        fast = changes[0]
        self.assertEqual((fast.unit, fast.baseline_unit), ("ms", "ms"))
        self.assertEqual((fast.current, fast.baseline, fast.delta), (150, 100, 50))
        self.assertEqual(changes[1].delta, 0)

    def test_explain_failed_outcome(self):
        result = self.service.explain_outcome(self.failed)
        self.assertEqual(result.report.outcome, "fail")
        self.assertEqual(result.missing_gates, [])
        (gate,) = result.gates
        self.assertEqual(gate.outcome, "fail")
        metrics = {metric.metric: metric for metric in gate.metrics}
        self.assertEqual(
            sorted(metrics), ["request_outcomes", "response_time", "throughput"]
        )
        response_time = metrics["response_time"]
        self.assertEqual(response_time.outcome, "fail")
        self.assertEqual((response_time.statistic, response_time.unit), ("p90", "ms"))
        self.assertEqual((response_time.min, response_time.max), (None, 3000))
        self.assertAlmostEqual(response_time.min_score, 0.8)
        assert response_time.score is not None
        self.assertAlmostEqual(response_time.score, 0.7)
        self.assertEqual(response_time.policy_version, POLICY_VERSION)
        fast, slow = response_time.sources
        self.assertEqual(
            (fast.source, fast.value, fast.meets_target), ("fast", 100, True)
        )
        self.assertEqual(
            (slow.source, slow.value, slow.meets_target), ("slow", 5000, False)
        )
        self.assertFalse(slow.excluded)

    def test_report_without_required_gate_names_it(self):
        empty = self.add(time="11:00:00")
        result = self.assess().explain_outcome(empty)
        self.assertEqual(result.report.outcome, "unknown")
        self.assertEqual(result.missing_gates, ["performance"])
        self.assertEqual(result.gates, [])


class KnowledgeBaseQuestionTests(QuestionContract):
    def open_store(self):
        return TurtleKnowledgeBase(self.directory / "kb")


class SQLiteQuestionTests(QuestionContract):
    def open_store(self):
        store = SQLiteReportRepository(self.directory / "reports.sqlite3")
        self.addCleanup(store.close)
        return store


def load_tests(loader, tests, pattern):
    """Run the contract only through the store-specific subclasses."""
    suite = unittest.TestSuite()
    for case in (KnowledgeBaseQuestionTests, SQLiteQuestionTests):
        suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


if __name__ == "__main__":
    unittest.main()
