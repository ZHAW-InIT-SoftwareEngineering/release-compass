import copy
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from langchain_core.tools import ToolException

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.sqlite_report_repository import SQLiteReportRepository
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


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "report.html"
        self.path.write_text("first")
        self.repository = repository_for(self)
        self.ingestion = Mock()
        self.ingestion.ingest.side_effect = lambda *_: Report(gates=[scored_gate()])

    def inputs(self, time="08:00:00"):
        return [ReportInput(self.path, "2026-09-02", time, source="test")]

    def test_repeat_and_rename_reuse_uuid_timestamps_and_skip_parser(self):
        first = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        renamed = self.path.with_name("renamed.html")
        renamed.write_bytes(self.path.read_bytes())
        reused = import_reports(
            [ReportInput(renamed, "2020-01-01", "00:00:00", source="test")],
            self.ingestion,
            self.repository,
        )[0]
        self.assertEqual(reused.report_id, first.report_id)
        self.assertEqual(reused.generated_at_date, "2026-09-02")
        self.assertEqual(reused.ingestion_sequence, first.ingestion_sequence)
        self.assertEqual(self.ingestion.ingest.call_count, 1)
        stored = self.repository.get_by_id(first.report_id)
        self.assertEqual(stored.source_paths, [str(self.path), str(renamed)])

    def test_changed_content_is_new_report_and_ties_use_ingestion_order(self):
        first = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        self.path.write_text("second")
        second = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        self.assertNotEqual(first.report_id, second.report_id)
        self.assertLess(first.ingestion_sequence, second.ingestion_sequence)
        self.assertEqual(len(self.repository.list_reports()), 2)

    def test_rejects_backdated_batch_without_partial_imports_or_aliases(self):
        first = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        later = self.path.with_name("later.html")
        earlier = self.path.with_name("earlier.html")
        renamed = self.path.with_name("alias.html")
        later.write_text("later")
        earlier.write_text("earlier")
        renamed.write_text("first")
        with self.assertRaisesRegex(ValueError, "Backdated"):
            import_reports(
                [
                    ReportInput(later, "2026-09-02", "09:00:00", source="test"),
                    ReportInput(renamed, source="test"),
                    ReportInput(earlier, "2026-09-01", "09:00:00", source="test"),
                ],
                self.ingestion,
                self.repository,
            )
        self.assertEqual(len(self.repository.list_reports()), 1)
        self.assertEqual(
            self.repository.get_by_id(first.report_id).source_paths, [str(self.path)]
        )

    def test_html_timestamp_precedes_config(self):
        self.ingestion.ingest.side_effect = None
        self.ingestion.ingest.return_value = report(time="10:00:00")
        result = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        self.assertEqual(result.generated_at_time, "10:00:00")

    def test_missing_html_and_config_timestamp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no complete generated-at"):
            import_reports(
                [ReportInput(self.path, source="test")], self.ingestion, self.repository
            )
        self.assertEqual(self.repository.list_reports(), [])

    def test_rejects_partial_source_or_config_timestamp(self):
        self.ingestion.ingest.side_effect = lambda *_: Report(
            generated_at_date="2026-09-02"
        )
        with self.assertRaisesRegex(ValueError, "both generated-at"):
            import_reports(self.inputs(), self.ingestion, self.repository)
        self.ingestion.ingest.side_effect = lambda *_: Report()
        with self.assertRaisesRegex(ValueError, "both generated-at"):
            import_reports(
                [ReportInput(self.path, "2026-09-02", source="test")],
                self.ingestion,
                self.repository,
            )
        self.assertEqual(self.repository.list_reports(), [])

    def test_initial_batch_is_assessed_in_timestamp_order(self):
        older = self.path.with_name("older.html")
        older.write_text("older")
        import_reports(
            [
                *self.inputs("09:00:00"),
                ReportInput(older, "2026-09-02", "08:00:00", source="test"),
            ],
            self.ingestion,
            self.repository,
        )
        service = assessment_service(self.repository)
        service.prepare()
        stored = self.repository.list_reports()
        newer, older_report = stored
        self.assertEqual(
            service.get_evidence(newer.report_id).previous_report_id,
            older_report.report_id,
        )

    def test_source_reports_cannot_be_overwritten(self):
        stored = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.repository.save(stored)


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
    def test_imports_configured_locust_report(self):
        repository = repository_for(self)
        root = Path(__file__).resolve().parents[2]
        report_path = (
            root
            / "data/raw/reports/example_reports/TeaStoreReports/Locust"
            / "Locust_TeaStore_Report_Original.html"
        )
        ingestion = HTMLReport(
            {"locust": load_html_mapping(root / "configs/ingestion/locust.yaml")}
        )
        (imported,) = import_reports(
            [ReportInput(report_path, source="locust")], ingestion, repository
        )
        stored = repository.get_by_id(imported.report_id)
        self.assertEqual(stored.generated_at_date, "2026-11-10")
        self.assertEqual(stored.generated_at_time, "10:02:29")
        self.assertEqual(stored.source_paths, [str(report_path)])
        gate = stored.gates[0]
        assert isinstance(gate, PerformanceGate)
        assert gate.response_time is not None
        self.assertEqual(gate.response_time.observation_count, 194700)
        self.assertEqual(len(gate.transactions), 1129)

        service = assessment_service(repository)
        service.prepare()
        pack = service.get_evidence(imported.report_id)
        metrics = pack.gates["PerformanceGate"].acceptance.metrics
        self.assertEqual(pack.outcome, "pass")
        self.assertEqual(metrics["response_time"].outcome, "pass")
        self.assertEqual(metrics["request_outcomes"].outcome, "pass")
        self.assertEqual(metrics["throughput"].outcome, "pass")
        # No request failed, so every transaction stays below 1 % failures.
        self.assertAlmostEqual(metrics["request_outcomes"].score, 1)


if __name__ == "__main__":
    unittest.main()
