import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.ontology.turtle_knowledge_base import TurtleKnowledgeBase
from src.adapters.outbound.sqlite.sqlite_report_repository import SQLiteReportRepository
from src.adapters.outbound.yaml_target_source import YamlTargetSource
from src.application.performance_assessment import build_performance_assessment_service
from src.application.use_cases.answer_report_questions import ReportQuestionService
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.ingestion.html_mapping import load_html_mapping
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.harness.tools.build_tools import build_tools

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT
    / "data/raw/reports/example_reports/TeaStoreReports/Locust"
    / "Locust_TeaStore_Report_Original.html"
)
TARGETS_PATH = ROOT / "configs/gates/performance/performance_gate.yaml"

KB_OUTCOME = """
SELECT ?generated_at ?path ?outcome WHERE {
    ?report ai2core:has_id ?id ;
            release-compass:generated_at ?generated_at ;
            release-compass:source_path ?path ;
            release-compass:outcome ?outcome .
}
"""


class RealReportFlowTests(unittest.TestCase):
    """The real Locust report, imported and assessed in each store."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.ingestion = HTMLReport(
            {"locust": load_html_mapping(ROOT / "configs/ingestion/locust.yaml")}
        )

    def import_and_assess(self, repository):
        (imported,) = import_reports(
            [ReportInput(REPORT_PATH, source="locust")], self.ingestion, repository
        )
        gate = imported.gates[0]
        assert isinstance(gate, PerformanceGate)
        assert gate.response_time is not None
        self.assertEqual(gate.response_time.observation_count, 194700)
        self.assertEqual(len(gate.transactions), 1129)
        service = build_performance_assessment_service(
            repository, YamlTargetSource(TARGETS_PATH).targets()
        )
        service.prepare()
        return imported.report_id, service.version

    def test_knowledge_base_flow(self):
        report_id, version = self.import_and_assess(TurtleKnowledgeBase(self.directory))
        reopened = TurtleKnowledgeBase(self.directory)
        reopened.open_assessment(version)
        (stored,) = reopened.select(KB_OUTCOME, {"id": str(report_id)})
        self.assertEqual(
            stored["generated_at"], datetime(2026, 11, 10, 10, 2, 29, tzinfo=UTC)
        )
        self.assertEqual(stored["path"], str(REPORT_PATH))
        self.assertTrue(str(stored["outcome"]).endswith("#pass"))

    def test_sqlite_flow(self):
        path = self.directory / "reports.sqlite3"
        repository = SQLiteReportRepository(path)
        self.addCleanup(repository.close)
        report_id, version = self.import_and_assess(repository)
        connection = sqlite3.connect(path)
        self.addCleanup(connection.close)
        row = connection.execute(
            """SELECT r.generated_at, p.path, a.outcome FROM reports r
               JOIN source_paths p USING (report_id)
               JOIN report_assessments a USING (report_id)
               WHERE r.report_id = ? AND a.version = ?""",
            (str(report_id), version),
        ).fetchone()
        self.assertEqual(row, ("2026-11-10T10:02:29+00:00", str(REPORT_PATH), "pass"))

    def test_both_stores_give_the_same_tool_answers(self):
        """The real report's tool answers are equal and short enough for the LLM."""
        sqlite_store = SQLiteReportRepository(self.directory / "reports.sqlite3")
        self.addCleanup(sqlite_store.close)
        answers = []
        for store in (TurtleKnowledgeBase(self.directory / "kb"), sqlite_store):
            report_id, _ = self.import_and_assess(store)
            tools = {
                tool.name: tool
                for tool in build_tools(ReportQuestionService(store, ["performance"]))
            }
            arguments = {"report_id": str(report_id)}

            def answer(name, extra=None, tools=tools, report_id=report_id):
                # Each import assigns a new UUID; compare everything else.
                arguments = {"report_id": str(report_id)} | (extra or {})
                text = tools[name].invoke(arguments)
                return json.loads(text.replace(str(report_id), "<report>"))

            answers.append(
                {
                    name: answer(name)
                    for name in ("describe_report", "get_baseline", "explain_outcome")
                }
                | {
                    "compare_gate": answer(
                        "compare_gate", {"baseline_report_id": str(report_id)}
                    )
                }
            )
            self.assertLess(len(tools["explain_outcome"].invoke(arguments)), 10_000)
        knowledge_base, sqlite = answers
        self.assertEqual(knowledge_base, sqlite)
        self.assertEqual(knowledge_base["explain_outcome"]["outcome"], "pass")
        self.assertEqual(knowledge_base["compare_gate"]["matched_sources"], 1129)


if __name__ == "__main__":
    unittest.main()
