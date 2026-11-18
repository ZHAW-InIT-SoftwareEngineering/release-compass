"""Assessment and derivation rules, run against both ReportRepository adapters."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from src.adapters.outbound.ontology.turtle_knowledge_base import TurtleKnowledgeBase
from src.adapters.outbound.sqlite.sqlite_report_repository import SQLiteReportRepository
from src.application.performance_assessment import build_performance_assessment_service
from src.application.use_cases.assess_reports import AssessmentService
from src.domain.assessment import GateDefinition
from src.domain.gates.performance.performance_gate import (
    PerformanceGate,
    RequestOutcomes,
    ResponseTimeMetric,
    ThroughputMetric,
    TransactionPerformance,
)
from src.domain.report import Report
from src.domain.scoring import POLICY_VERSION
from src.domain.targets import MetricTarget, TargetRange

KB_DERIVED = """
SELECT ?outcome ?is_root ?previous ?baseline ?gate_outcome ?gate_baseline
WHERE {
    ?report ai2core:has_id ?id ;
            release-compass:outcome ?outcome ;
            release-compass:is_root ?is_root .
    OPTIONAL { ?report release-compass:previous_report/ai2core:has_id ?previous }
    OPTIONAL { ?report release-compass:baseline_report/ai2core:has_id ?baseline }
    OPTIONAL {
        ?report release-compass:contains_gate ?gate .
        OPTIONAL { ?gate release-compass:outcome ?gate_outcome }
        OPTIONAL {
            ?gate release-compass:baseline_gate ?baseline_gate .
            ?baseline_report release-compass:contains_gate ?baseline_gate ;
                             ai2core:has_id ?gate_baseline .
        }
    }
}
"""

SQLITE_DERIVED = """
SELECT r.outcome, r.is_root, r.previous_report_id, r.baseline_report_id,
       g.outcome, g.baseline_report_id
FROM report_assessments r
LEFT JOIN gate_assessments g ON g.version = r.version AND g.report_id = r.report_id
WHERE r.version = ? AND r.report_id = ?
"""


def targets(score=0.8):
    return {
        "response_time": MetricTarget(
            "response_time", "p90", "ms", TargetRange(None, 3000), score
        ),
        "request_outcomes": MetricTarget(
            "request_outcomes", "failure_rate_percent", "%", TargetRange(None, 1), score
        ),
        "throughput": MetricTarget(
            "throughput", "tps", "req/s", TargetRange(40, None), score
        ),
    }


def scored_gate(score=0.9):
    """A gate whose response-time score is ``score``; other metrics pass."""
    fast_requests = round(score * 100)
    gate = PerformanceGate(throughput=ThroughputMetric("overall", "req/s", tps=100))
    for name, requests, p90 in (
        ("fast", fast_requests, 100),
        ("slow", 100 - fast_requests, 5000),
    ):
        gate.transactions[name] = TransactionPerformance(
            name,
            ResponseTimeMetric("test", "ms", requests, 10, p90=p90),
            RequestOutcomes(requests, 0, requests, 0),
        )
    return gate


class AssessmentContract(unittest.TestCase):
    """Scenarios every store must satisfy; subclasses open the store."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.sequence = 0
        self.store = self.open_store()

    def open_store(self):
        raise NotImplementedError

    def derived(self, version: str, report_id: UUID) -> dict:
        raise NotImplementedError

    def add(self, *gates, time="08:00:00") -> UUID:
        self.sequence += 1
        report = Report(
            report_id=UUID(int=self.sequence),
            generated_at_date="2026-09-02",
            generated_at_time=time,
            source_fingerprint=str(self.sequence),
            ingestion_sequence=self.sequence,
            gates=list(gates),
        )
        self.store.save_import_batch([report], {})
        return report.report_id

    def assess(self, gate_targets=None) -> AssessmentService:
        service = build_performance_assessment_service(
            self.store, gate_targets or targets()
        )
        service.prepare()
        return service

    def test_failed_report_stays_in_history_but_never_becomes_baseline(self):
        first = self.add(scored_gate())
        failed = self.add(scored_gate(0.7), time="09:00:00")
        current = self.add(scored_gate(), time="10:00:00")
        version = self.assess().version

        self.assertEqual(
            self.derived(version, first),
            {
                "outcome": "pass",
                "is_root": True,
                "previous": None,
                "baseline": None,
                "gate_outcome": "pass",
                "gate_baseline": None,
            },
        )
        self.assertEqual(self.derived(version, failed)["outcome"], "fail")
        self.assertEqual(
            self.derived(version, current),
            {
                "outcome": "pass",
                "is_root": False,
                "previous": failed,
                "baseline": first,
                "gate_outcome": "pass",
                "gate_baseline": first,
            },
        )

    def test_gate_baseline_advances_without_a_passing_report(self):
        # A required gate missing from every report keeps all reports unknown.
        first = self.add(scored_gate())
        current = self.add(scored_gate(), time="09:00:00")
        service = AssessmentService(
            self.store,
            [
                GateDefinition("performance", targets(), POLICY_VERSION),
                GateDefinition("security", targets(), "security-v1"),
            ],
        )
        service.prepare()

        result = self.derived(service.version, current)
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(result["gate_outcome"], "pass")
        self.assertIsNone(result["baseline"])
        self.assertEqual(result["gate_baseline"], first)

    def test_report_without_required_gate_is_unknown(self):
        current = self.add()
        result = self.derived(self.assess().version, current)
        self.assertEqual(result["outcome"], "unknown")
        self.assertIsNone(result["gate_outcome"])

    def test_missing_measured_value_makes_the_report_unknown(self):
        gate = scored_gate()
        response_time = gate.transactions["fast"].response_time
        assert response_time is not None
        response_time.p90 = None
        current = self.add(gate)
        self.assertEqual(
            self.derived(self.assess().version, current)["outcome"], "unknown"
        )

    def test_reports_are_assessed_once_per_version(self):
        first = self.add(scored_gate())
        version = self.assess().version
        current = self.add(scored_gate(0.7), time="09:00:00")
        self.store.open_assessment(version)
        self.assertEqual(self.store.unassessed_reports(), [current])

        self.assess()
        self.assertEqual(self.store.unassessed_reports(), [])
        self.assertEqual(self.derived(version, current)["previous"], first)

    def test_changed_configuration_is_a_new_version_and_keeps_the_old_one(self):
        first = self.add(scored_gate(0.85))
        current = self.add(scored_gate(0.95), time="09:00:00")
        original = self.assess().version
        changed = self.assess(targets(0.9)).version

        self.assertNotEqual(original, changed)
        self.assertEqual(self.derived(original, current)["baseline"], first)
        self.assertIsNone(self.derived(changed, current)["baseline"])
        self.assertEqual(self.derived(changed, first)["outcome"], "fail")

    def test_results_persist_only_after_save(self):
        current = self.add(scored_gate())
        version = self.assess().version
        self.store = self.open_store()
        self.assertEqual(self.derived(version, current)["outcome"], "pass")

        self.store.open_assessment("unsaved")
        self.store.apply_rules(current, ["performance"])
        self.store = self.open_store()
        self.store.open_assessment("unsaved")
        self.assertEqual(self.store.unassessed_reports(), [current])


class KnowledgeBaseAssessmentTests(AssessmentContract):
    def open_store(self):
        return TurtleKnowledgeBase(self.directory / "kb")

    def derived(self, version, report_id):
        self.store.open_assessment(version)
        (row,) = self.store.select(KB_DERIVED, {"id": str(report_id)})

        def name(key):
            value = row.get(key)
            return None if value is None else str(value).rsplit("#")[-1]

        def identifier(key):
            value = row.get(key)
            return None if value is None else UUID(str(value))

        return {
            "outcome": name("outcome"),
            "is_root": row["is_root"],
            "previous": identifier("previous"),
            "baseline": identifier("baseline"),
            "gate_outcome": name("gate_outcome"),
            "gate_baseline": identifier("gate_baseline"),
        }


class SQLiteAssessmentTests(AssessmentContract):
    def open_store(self):
        store = SQLiteReportRepository(self.directory / "reports.sqlite3")
        self.addCleanup(store.close)
        return store

    def derived(self, version, report_id):
        connection = sqlite3.connect(self.directory / "reports.sqlite3")
        self.addCleanup(connection.close)
        (row,) = connection.execute(SQLITE_DERIVED, (version, str(report_id)))
        outcome, is_root, previous, baseline, gate_outcome, gate_baseline = row

        def identifier(value):
            return None if value is None else UUID(value)

        return {
            "outcome": outcome,
            "is_root": bool(is_root),
            "previous": identifier(previous),
            "baseline": identifier(baseline),
            "gate_outcome": gate_outcome,
            "gate_baseline": identifier(gate_baseline),
        }


def load_tests(loader, tests, pattern):
    """Run the contract only through the store-specific subclasses."""
    suite = unittest.TestSuite()
    for case in (KnowledgeBaseAssessmentTests, SQLiteAssessmentTests):
        suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


if __name__ == "__main__":
    unittest.main()
