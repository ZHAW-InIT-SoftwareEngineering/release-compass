import copy
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from langchain_core.tools import ToolException

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.ontology.turtle_knowledge_base import TurtleKnowledgeBase
from src.adapters.outbound.sqlite.sqlite_report_repository import SQLiteReportRepository
from src.application.performance_assessment import build_performance_assessment_service
from src.application.use_cases.assess_reports import (
    AssessmentService,
    EvidenceUnavailableError,
)
from src.application.use_cases.compare_gate import ReportNotFoundError
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.ingestion.html_mapping import load_html_mapping
from src.domain.assessment import GateAcceptance, GateDefinition
from src.domain.deltas.performance_comparison import compare_performance_values
from src.domain.gates.gate import Gate
from src.domain.gates.performance.performance_gate import (
    PerformanceGate,
    RequestOutcomes,
    ResponseTimeMetric,
    ThroughputMetric,
    TransactionPerformance,
)
from src.domain.gates.performance.serialization import PERFORMANCE_DOMAIN_TYPES
from src.domain.report import Report
from src.domain.scoring import POLICY_VERSION
from src.domain.targets import MetricTarget, TargetRange
from src.harness.tools.build_tools import build_tools


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


def repository_for(test, path=":memory:"):
    repository = SQLiteReportRepository(path, domain_types=PERFORMANCE_DOMAIN_TYPES)
    test.addCleanup(repository.close)
    return repository


def assessment_service(repository, gate_targets=None, gate_definitions=None):
    selected_targets = gate_targets or targets()
    if gate_definitions is None:
        return build_performance_assessment_service(repository, selected_targets)
    return AssessmentService(
        repository,
        gate_definitions,
        {
            "performance": {
                name: asdict(target) for name, target in selected_targets.items()
            },
            "policy_version": POLICY_VERSION,
        },
    )


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


def report(gate=None, time="08:00:00"):
    return Report(
        generated_at_date="2026-09-02",
        generated_at_time=time,
        gates=[gate or scored_gate()],
    )


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_for(self)
        self.service = assessment_service(self.repository)

    def add(self, score=0.9, time="08:00:00", extra_gate=False):
        result = report(scored_gate(score), time)
        if extra_gate:
            result.gates.append(Gate())
        self.repository.save(result)
        return result

    def test_generic_service_runs_without_performance_configuration(self):
        current = report(Gate())
        self.repository.save(current)
        assessor = Mock(return_value=GateAcceptance("pass"))
        service = AssessmentService(
            self.repository,
            [GateDefinition(Gate, assessor, lambda *_: {}, "generic-v1")],
            {"policy": "generic"},
        )

        service.prepare()

        pack = service.get_evidence(current.report_id)
        self.assertEqual(pack.outcome, "pass")
        self.assertEqual(pack.configuration["policy"], "generic")
        assessor.assert_called_once_with(current.gates[0])

    def test_first_pass_establishes_baseline_and_failed_report_does_not_advance_it(
        self,
    ):
        first = self.add()
        failed = self.add(0.7, "09:00:00")
        current = self.add(0.9, "10:00:00")
        self.service.prepare()
        first_pack = self.service.get_evidence(first.report_id)
        pack = self.service.get_evidence(current.report_id)
        self.assertEqual(first_pack.outcome, "pass")
        self.assertTrue(first_pack.is_root)
        self.assertIsNone(first_pack.baseline_report_id)
        self.assertEqual(pack.previous_report_id, failed.report_id)
        self.assertEqual(pack.baseline_report_id, first.report_id)
        self.assertEqual(
            pack.gates["PerformanceGate"].baseline_report_id, first.report_id
        )
        self.assertEqual(
            pack, self.repository.get_evidence(current.report_id, self.service.version)
        )

    def test_gate_baseline_can_advance_from_an_overall_nonpassing_report(self):
        first = self.add()
        gate_pass = self.add(time="09:00:00", extra_gate=True)
        current = self.add(time="10:00:00")
        self.service.prepare()
        self.assertEqual(
            self.service.get_evidence(gate_pass.report_id).outcome, "unknown"
        )
        pack = self.service.get_evidence(current.report_id)
        self.assertEqual(pack.baseline_report_id, first.report_id)
        self.assertEqual(
            pack.gates["PerformanceGate"].baseline_report_id, gate_pass.report_id
        )
        self.assertEqual(
            set(pack.snapshots),
            {str(item.report_id) for item in (first, gate_pass, current)},
        )

    def test_registered_gates_advance_independently_across_failed_reports(self):
        first = self.add(extra_gate=True)
        second = self.add(0.7, "09:00:00", extra_gate=True)
        current = self.add(time="10:00:00", extra_gate=True)
        base_definition = self.service.definitions["PerformanceGate"]
        other_assessor = Mock(
            side_effect=[
                GateAcceptance("fail"),
                GateAcceptance("pass"),
                GateAcceptance("pass"),
            ]
        )
        service = assessment_service(
            self.repository,
            gate_definitions=[
                base_definition,
                GateDefinition(Gate, other_assessor, lambda *_: {}, "test-gate-v1"),
            ],
        )
        service.prepare()
        pack = service.get_evidence(current.report_id)
        self.assertIsNone(pack.baseline_report_id)
        self.assertEqual(
            pack.gates["PerformanceGate"].baseline_report_id, first.report_id
        )
        self.assertEqual(pack.gates["Gate"].baseline_report_id, second.report_id)
        self.assertEqual(service.get_evidence(first.report_id).outcome, "fail")
        self.assertEqual(service.get_evidence(second.report_id).outcome, "fail")

    def test_file_repository_reopens_with_typed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reports.sqlite3"
            repository = repository_for(self, path)
            current = report()
            repository.save(current)
            service = assessment_service(repository)
            service.prepare()
            reopened = repository_for(self, path)
            self.assertEqual(
                service.get_evidence(current.report_id),
                reopened.get_evidence(current.report_id, service.version),
            )

    def test_missing_measured_value_persists_as_unknown(self):
        current = self.add()
        # The report has not been assessed yet, so update its legacy un-fingerprinted fixture.
        current.gates[0].transactions["fast"].response_time.p90 = None
        self.repository.save(current)
        self.service.prepare()
        self.assertEqual(
            self.service.get_evidence(current.report_id).outcome, "unknown"
        )

    def test_history_traverses_nonpassing_reports_to_root(self):
        first = self.add()
        second = self.add(0.7, "09:00:00")
        self.service.prepare()
        previous = self.service.get_previous_report(second.report_id)
        self.assertFalse(previous["history_end"])
        self.assertEqual(previous["previous_report"]["report_id"], str(first.report_id))
        self.assertTrue(
            self.service.get_previous_report(first.report_id)["history_end"]
        )

    def test_configuration_version_rebuild_preserves_previous_packs(self):
        first = self.add(0.85)
        current = self.add(0.95, "09:00:00")
        self.service.prepare()
        original = self.service.get_evidence(current.report_id)
        changed = assessment_service(self.repository, targets(0.9))
        changed.prepare()
        revised = changed.get_evidence(current.report_id)
        self.assertNotEqual(original.assessment_version, revised.assessment_version)
        self.assertIsNone(revised.baseline_report_id)
        self.assertEqual(original.baseline_report_id, first.report_id)
        self.assertEqual(original, self.service.get_evidence(current.report_id))
        score_comparison = original.gates["PerformanceGate"].comparisons[
            "acceptance_scores"
        ]["response_time"]
        self.assertAlmostEqual(score_comparison["absolute_delta"], 0.1)
        self.assertAlmostEqual(
            score_comparison["relative_delta_percent"], 0.1 / 0.85 * 100
        )

    def test_repeated_prepare_reuses_immutable_packs(self):
        current = self.add()
        self.service.prepare()
        pack = self.service.get_evidence(current.report_id)
        self.service.prepare()
        self.assertEqual(pack, self.service.get_evidence(current.report_id))
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.repository.save_evidence(replace(pack, outcome="fail"))
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.repository.save(current)

    def test_missing_duplicate_and_unsupported_gates_do_not_pass(self):
        for gates in ([], [Gate()], [scored_gate(), scored_gate()]):
            repository = repository_for(self)
            repository.save(
                Report(
                    generated_at_date="2026-09-02",
                    generated_at_time="08:00:00",
                    gates=gates,
                )
            )
            service = assessment_service(repository)
            service.prepare()
            self.assertEqual(
                service.get_evidence(repository.list_reports()[0].report_id).outcome,
                "unknown",
            )

    def test_not_found_and_unprepared_are_distinct(self):
        with self.assertRaises(ReportNotFoundError):
            self.service.get_evidence(uuid4())
        current = self.add()
        with self.assertRaises(EvidenceUnavailableError):
            self.service.get_evidence(current.report_id)


class ComparisonTests(unittest.TestCase):
    def test_deltas_units_and_missing_values(self):
        baseline = scored_gate()
        baseline.response_time = ResponseTimeMetric(
            "overall", "ms", 10, 10, mean=100, p50=0
        )
        current = copy.deepcopy(baseline)
        current.response_time.mean = 110
        current.response_time.p50 = 2
        values = compare_performance_values(current, baseline)
        mean = values["numeric"]["response_time.mean"]
        self.assertEqual(mean["absolute_delta"], 10)
        self.assertEqual(mean["relative_delta_percent"], 10)
        self.assertEqual(
            values["numeric"]["response_time.p50"]["relative_unavailable_reason"],
            "Zero baseline",
        )
        current.response_time.unit = "seconds"
        self.assertEqual(
            compare_performance_values(current, baseline)["numeric"][
                "response_time.mean"
            ]["unavailable_reason"],
            "Incompatible units",
        )
        missing = compare_performance_values(current, None)["numeric"][
            "response_time.mean"
        ]
        self.assertIsNone(missing["absolute_delta"])
        self.assertEqual(missing["unavailable_reason"], "No prior passing baseline")


class EvidenceToolTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_for(self)
        self.current = report()
        self.repository.save(self.current)
        self.service = assessment_service(self.repository)
        self.service.prepare()
        tools = build_tools(self.service)
        self.assertEqual(
            [tool.name for tool in tools],
            ["compare_gate", "compare_performance", "get_previous_report", "cicd_tool"],
        )
        self.gate_compare, self.compare, self.previous, self.cicd = tools

    def test_tools_return_evidence_and_root_without_model_selected_baseline(self):
        arguments = {"report_id": str(self.current.report_id)}
        result = json.loads(self.compare.invoke(arguments))
        self.assertEqual(result["outcome"], "pass")
        self.assertIsNone(result["baseline_report_id"])
        self.assertTrue(json.loads(self.previous.invoke(arguments))["history_end"])

    def test_series_are_stored_fully_and_referenced_in_tool_output(self):
        repository = repository_for(self)
        gate = scored_gate()
        gate.response_time = ResponseTimeMetric(
            "overall",
            "ms",
            1,
            1,
            supporting_evidence={"timeseries": [{"timestamp": 1, "value": 2}]},
        )
        current = report(gate)
        repository.save(current)
        service = assessment_service(repository)
        service.prepare()
        tool = build_tools(service)[1]
        result = json.loads(tool.invoke({"report_id": str(current.report_id)}))
        series = result["snapshots"][str(current.report_id)]["report"]["gates"][0][
            "response_time"
        ]["supporting_evidence"]["timeseries"]
        self.assertEqual(series["item_count"], 1)
        self.assertEqual(
            series["evidence_reference"]["evidence_pack_id"], result["evidence_pack_id"]
        )
        stored = service.get_evidence(current.report_id)
        self.assertIsInstance(
            stored.snapshots[str(current.report_id)]["report"]["gates"][0][
                "response_time"
            ]["supporting_evidence"]["timeseries"],
            list,
        )

    def test_expected_errors_are_tool_exceptions(self):
        for tool in (self.compare, self.previous):
            for identifier in ("not-a-uuid", str(uuid4())):
                with (
                    self.subTest(tool=tool.name, identifier=identifier),
                    self.assertRaises(ToolException),
                ):
                    tool.invoke({"report_id": identifier})

    def test_unexpected_storage_errors_propagate(self):
        self.service.repository = Mock()
        self.service.repository.get_by_id.side_effect = RuntimeError("storage failed")
        with self.assertRaisesRegex(RuntimeError, "storage failed"):
            self.compare.invoke({"report_id": str(self.current.report_id)})


class RealReportFlowTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        self.report_path = (
            root
            / "data/raw/reports/example_reports/TeaStoreReports/Locust"
            / "Locust_TeaStore_Report_Original.html"
        )
        self.ingestion = HTMLReport(
            {"locust": load_html_mapping(root / "configs/ingestion/locust.yaml")}
        )

    def test_imports_configured_locust_report_into_knowledge_base(self):
        with tempfile.TemporaryDirectory() as directory:
            knowledge_base = TurtleKnowledgeBase(Path(directory))
            (imported,) = import_reports(
                [ReportInput(self.report_path, source="locust")],
                self.ingestion,
                knowledge_base,
            )
            (stored,) = TurtleKnowledgeBase(Path(directory)).select(
                """
                SELECT ?generated_at ?path WHERE {
                    ?report ai2core:has_id ?id ;
                            release-compass:generated_at ?generated_at ;
                            release-compass:source_path ?path .
                }
                """,
                {"id": str(imported.report_id)},
            )
        self.assertEqual(
            stored["generated_at"], datetime(2026, 11, 10, 10, 2, 29, tzinfo=UTC)
        )
        self.assertEqual(stored["path"], str(self.report_path))
        gate = imported.gates[0]
        assert isinstance(gate, PerformanceGate)
        assert gate.response_time is not None
        self.assertEqual(gate.response_time.observation_count, 194700)
        self.assertEqual(len(gate.transactions), 1129)


if __name__ == "__main__":
    unittest.main()
