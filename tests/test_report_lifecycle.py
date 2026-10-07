import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from langchain_core.tools import ToolException

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.sqlite_report_repository import SQLiteReportRepository
from src.application.use_cases.assess_reports import (
    AssessmentService,
    EvidenceUnavailableError,
)
from src.application.use_cases.compare_gate import ReportNotFoundError
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.gates.performance.performance_gate import PerformanceGateConfig
from src.domain.assessment import (
    METRICS,
    GateAcceptance,
    GateDefinition,
    assess_performance,
    combine_outcomes,
)
from src.domain.deltas.performance_comparison import compare_performance_values
from src.domain.gates.gate import Gate
from src.domain.gates.performance.performance_gate import (
    MetricSummary,
    PerformanceGate,
    RequestOutcomes,
    ResourceMetric,
    ResponseTimeMetric,
    ThroughputMetric,
    TransactionPerformance,
)
from src.domain.report import Report
from src.harness.tools.compare_performance import build_performance_tools


def config(threshold=0.8):
    return PerformanceGateConfig.model_validate(
        {
            "metrics": {
                name: {"operator": ">=", "score": threshold} for name in METRICS
            },
        }
    )


def repository_for(test, path=":memory:"):
    repository = SQLiteReportRepository(path)
    test.addCleanup(repository.close)
    return repository


def explicit_gate(score=0.9):
    return PerformanceGate(
        provider_assessments={
            "performance_gate": {
                "passing": False,
                "metrics": {
                    name: {"score": score, "threshold": 0.99, "passing": False}
                    for name in METRICS
                },
            },
        }
    )


def report(gate=None, time="08:00:00"):
    return Report(
        generated_at_date="2026-09-02",
        generated_at_time=time,
        gates=[gate or explicit_gate()],
    )


def weighted_gate():
    gate = PerformanceGate()
    for name in ("A", "B"):
        gate.transactions[name] = TransactionPerformance(
            name,
            ResponseTimeMetric("test", "ms", 10, 10),
            RequestOutcomes(10, 0, 10, 0),
            throughput=ThroughputMetric(name, "req/s"),
        )
        gate.transactions[name].throughput.assessment.status = 2
    gate.provider_assessments = {
        "statuses": {"red": 0, "amber": 1, "green": 2},
        "nfr_compliance": {
            "score_nfr": 0.1,
            "weights": {"red": 1, "amber": 0.5, "green": 0},
        },
        "transaction_health": {
            "per_transaction": {
                "A": {
                    "transaction_weight": 3,
                    "components": {"local_nfr": 0, "failure_transactions_rate": 0},
                },
                "B": {
                    "transaction_weight": 1,
                    "components": {"local_nfr": 1, "failure_transactions_rate": 1},
                },
            },
        },
        "infrastructure_health": {"per_node": {}},
    }
    return gate


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "report.html"
        self.path.write_text("first")
        self.repository = repository_for(self)
        self.ingestion = Mock()
        self.ingestion.ingest.side_effect = lambda _: Report(gates=[explicit_gate()])

    def inputs(self, time="08:00:00"):
        return [ReportInput(self.path, "2026-09-02", time)]

    def test_repeat_and_rename_reuse_uuid_timestamps_and_skip_parser(self):
        first = import_reports(self.inputs(), self.ingestion, self.repository)[0]
        renamed = self.path.with_name("renamed.html")
        renamed.write_bytes(self.path.read_bytes())
        reused = import_reports(
            [ReportInput(renamed, "2020-01-01", "00:00:00")],
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
                    ReportInput(later, "2026-09-02", "09:00:00"),
                    ReportInput(renamed),
                    ReportInput(earlier, "2026-09-01", "09:00:00"),
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

    def test_timestamp_fallback_is_complete_and_stable(self):
        result = import_reports(
            [ReportInput(self.path)], self.ingestion, self.repository
        )[0]
        self.assertIsNotNone(result.generated_at_date)
        self.assertIsNotNone(result.generated_at_time)
        again = import_reports(
            [ReportInput(self.path)], self.ingestion, self.repository
        )[0]
        self.assertEqual(again.generated_at_time, result.generated_at_time)

    def test_rejects_partial_source_or_config_timestamp(self):
        self.ingestion.ingest.side_effect = lambda _: Report(
            generated_at_date="2026-09-02"
        )
        with self.assertRaisesRegex(ValueError, "both generated-at"):
            import_reports(self.inputs(), self.ingestion, self.repository)
        self.ingestion.ingest.side_effect = lambda _: Report()
        with self.assertRaisesRegex(ValueError, "both generated-at"):
            import_reports(
                [ReportInput(self.path, "2026-09-02")], self.ingestion, self.repository
            )
        self.assertEqual(self.repository.list_reports(), [])

    def test_initial_batch_is_assessed_in_timestamp_order(self):
        older = self.path.with_name("older.html")
        older.write_text("older")
        import_reports(
            [
                *self.inputs("09:00:00"),
                ReportInput(older, "2026-09-02", "08:00:00"),
            ],
            self.ingestion,
            self.repository,
        )
        service = AssessmentService(self.repository, config())
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


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.thresholds = {name: 0.8 for name in METRICS}

    def test_explicit_scores_take_precedence_and_config_controls_outcome(self):
        gate = explicit_gate(0.8)
        gate.provider_assessments["nfr_compliance"] = {"score_nfr": 1}
        acceptance = assess_performance(gate, self.thresholds)
        self.assertEqual(acceptance.outcome, "pass")
        self.assertEqual(acceptance.metrics["cpu"].provider_evidence["threshold"], 0.99)
        gate.provider_assessments["performance_gate"]["metrics"]["cpu"]["score"] = 0.79
        self.assertEqual(assess_performance(gate, self.thresholds).outcome, "fail")

    def test_invalid_or_missing_explicit_score_is_unknown_without_fallback(self):
        for invalid in (None, True, -0.1, 1.1, float("nan"), float("inf"), "0.9"):
            with self.subTest(invalid=invalid):
                gate = explicit_gate()
                gate.provider_assessments["performance_gate"]["metrics"]["cpu"][
                    "score"
                ] = invalid
                self.assertEqual(
                    assess_performance(gate, self.thresholds).metrics["cpu"].outcome,
                    "unknown",
                )

    def test_weighted_penalties_and_nfr_aggregate_use_provider_values(self):
        result = assess_performance(weighted_gate(), self.thresholds)
        self.assertEqual(result.metrics["response_time"].score, 0.75)
        self.assertEqual(result.metrics["request_outcomes"].score, 0.75)
        self.assertEqual(result.metrics["throughput"].score, 1)
        self.assertEqual(result.metrics["transaction_nfr_status"].score, 0.9)
        self.assertEqual(result.metrics["cpu"].outcome, "unknown")

    def test_throughput_status_weights_and_unevaluable_source(self):
        gate = weighted_gate()
        gate.transactions["B"].throughput.assessment.status = 1
        result = assess_performance(gate, self.thresholds)
        self.assertEqual(result.metrics["throughput"].score, 0.875)
        gate.transactions["B"].throughput.supporting_evidence["load_nfr_details"] = {
            "not_evaluable": True
        }
        self.assertEqual(
            assess_performance(gate, self.thresholds).metrics["throughput"].outcome,
            "unknown",
        )

    def test_missing_weights_are_unknown_and_zero_weight_is_excluded(self):
        gate = weighted_gate()
        del gate.provider_assessments["transaction_health"]["per_transaction"]["B"][
            "transaction_weight"
        ]
        self.assertEqual(
            assess_performance(gate, self.thresholds).metrics["response_time"].outcome,
            "unknown",
        )
        gate.provider_assessments["transaction_health"]["per_transaction"]["B"][
            "transaction_weight"
        ] = 0
        gate.transactions["B"].throughput.supporting_evidence["load_nfr_details"] = {
            "not_evaluable": True
        }
        result = assess_performance(gate, self.thresholds)
        self.assertEqual(result.metrics["response_time"].score, 1)
        self.assertEqual(result.metrics["throughput"].score, 1)
        self.assertTrue(result.metrics["response_time"].sources[1].excluded)

    def test_explicit_equal_weight_policy_and_empty_set(self):
        gate = weighted_gate()
        for item in gate.provider_assessments["transaction_health"][
            "per_transaction"
        ].values():
            del item["transaction_weight"]
        gate.provider_assessments["transaction_health"]["weights"] = {
            "transaction_aggregation": {"mode": "equal"}
        }
        self.assertEqual(
            assess_performance(gate, self.thresholds).metrics["response_time"].score,
            0.5,
        )
        for item in gate.provider_assessments["transaction_health"][
            "per_transaction"
        ].values():
            item["zero_observation"] = True
        self.assertEqual(
            assess_performance(gate, self.thresholds).metrics["response_time"].outcome,
            "unknown",
        )

    def test_fail_and_unknown_never_satisfy_release_acceptance(self):
        self.assertEqual(combine_outcomes(["pass", "unknown"]), "unknown")
        self.assertEqual(combine_outcomes(["unknown", "fail"]), "fail")
        self.assertEqual(combine_outcomes([]), "unknown")

    def test_provider_no_data_flag_does_not_become_zero_penalty_pass(self):
        gate = weighted_gate()
        gate.provider_assessments["nfr_compliance"].update(
            {"score_nfr": 0, "has_data": False}
        )
        result = assess_performance(gate, self.thresholds)
        self.assertEqual(result.metrics["transaction_nfr_status"].outcome, "unknown")

    def test_resource_penalties_follow_provider_node_weights(self):
        gate = weighted_gate()
        for metric, unit in (("cpu", "cores"), ("memory", "bytes")):
            setattr(
                gate,
                f"{metric}_components",
                {
                    name: ResourceMetric(MetricSummary(name, unit, 10, 10))
                    for name in ("X", "Y")
                },
            )
        gate.provider_assessments["infrastructure_health"]["per_node"] = {
            "X": {
                "node_weight": 0.75,
                "metrics_components": {
                    "cpu": {"local_nfr": 0},
                    "memory": {"local_nfr": 0},
                },
            },
            "Y": {
                "node_weight": 0.25,
                "metrics_components": {
                    "cpu": {"local_nfr": 0.6},
                    "memory": {"local_nfr": 0.2},
                },
            },
        }
        result = assess_performance(gate, self.thresholds)
        self.assertAlmostEqual(result.metrics["cpu"].score, 0.85)
        self.assertAlmostEqual(result.metrics["memory"].score, 0.95)
        self.assertEqual(result.metrics["cpu"].outcome, "pass")

    def test_zero_observations_cannot_pass_with_positive_weight(self):
        gate = weighted_gate()
        gate.transactions["A"].response_time.observation_count = 0
        gate.transactions["A"].request_outcomes.total_requests = 0
        result = assess_performance(gate, self.thresholds)
        self.assertEqual(result.metrics["response_time"].outcome, "unknown")
        self.assertEqual(result.metrics["request_outcomes"].outcome, "unknown")


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_for(self)
        self.service = AssessmentService(self.repository, config())

    def add(self, score=0.9, time="08:00:00", extra_gate=False):
        result = report(explicit_gate(score), time)
        if extra_gate:
            result.gates.append(Gate())
        self.repository.save(result)
        return result

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
        service = AssessmentService(
            self.repository,
            config(),
            [
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
            service = AssessmentService(repository, config())
            service.prepare()
            reopened = repository_for(self, path)
            self.assertEqual(
                service.get_evidence(current.report_id),
                reopened.get_evidence(current.report_id, service.version),
            )

    def test_nonfinite_provider_score_persists_as_unknown(self):
        current = self.add()
        # The report has not been assessed yet, so update its legacy un-fingerprinted fixture.
        current.gates[0].provider_assessments["performance_gate"]["metrics"]["cpu"][
            "score"
        ] = float("nan")
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
        changed = AssessmentService(self.repository, config(0.9))
        changed.prepare()
        revised = changed.get_evidence(current.report_id)
        self.assertNotEqual(original.assessment_version, revised.assessment_version)
        self.assertIsNone(revised.baseline_report_id)
        self.assertEqual(original.baseline_report_id, first.report_id)
        self.assertEqual(original, self.service.get_evidence(current.report_id))
        score_comparison = original.gates["PerformanceGate"].comparisons[
            "acceptance_scores"
        ]["cpu"]
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
        for gates in ([], [Gate()], [explicit_gate(), explicit_gate()]):
            repository = repository_for(self)
            repository.save(
                Report(
                    generated_at_date="2026-09-02",
                    generated_at_time="08:00:00",
                    gates=gates,
                )
            )
            service = AssessmentService(repository, config())
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
    def test_deltas_units_missing_values_and_categorical_statuses(self):
        baseline = weighted_gate()
        baseline.response_time = ResponseTimeMetric(
            "overall", "ms", 10, 10, mean=100, p50=0
        )
        current = copy.deepcopy(baseline)
        current.response_time.mean = 110
        current.response_time.p50 = 2
        current.transactions["A"].nfr_status = 2
        values = compare_performance_values(current, baseline)
        mean = values["numeric"]["response_time.mean"]
        self.assertEqual(mean["absolute_delta"], 10)
        self.assertEqual(mean["relative_delta_percent"], 10)
        self.assertEqual(
            values["numeric"]["response_time.p50"]["relative_unavailable_reason"],
            "Zero baseline",
        )
        self.assertEqual(values["transaction_nfr_status"]["A"]["current"], 2)
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
        self.service = AssessmentService(self.repository, config())
        self.service.prepare()
        self.compare, self.previous = build_performance_tools(self.service)

    def test_tools_return_evidence_and_root_without_model_selected_baseline(self):
        arguments = {"report_id": str(self.current.report_id)}
        result = json.loads(self.compare.invoke(arguments))
        self.assertEqual(result["outcome"], "pass")
        self.assertIsNone(result["baseline_report_id"])
        self.assertTrue(json.loads(self.previous.invoke(arguments))["history_end"])

    def test_series_are_stored_fully_and_referenced_in_tool_output(self):
        repository = repository_for(self)
        gate = explicit_gate()
        gate.response_time = ResponseTimeMetric(
            "overall",
            "ms",
            1,
            1,
            supporting_evidence={"timeseries": [{"timestamp": 1, "value": 2}]},
        )
        current = report(gate)
        repository.save(current)
        service = AssessmentService(repository, config())
        service.prepare()
        tool = build_performance_tools(service)[0]
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
    def test_configured_synthetic_pass_and_real_report_baseline(self):
        repository = repository_for(self)
        root = Path(__file__).resolve().parents[1]
        inputs = [
            ReportInput(
                root / "data/raw/reports/example_reports/synthetic_report.html",
                "2026-09-02",
                "08:44:21",
            ),
            ReportInput(
                root / "data/raw/reports/example_reports/report.html",
                "2026-09-02",
                "08:44:22",
            ),
        ]
        first, current = import_reports(inputs, HTMLReport(), repository)
        service = AssessmentService(repository, config())
        service.prepare()
        self.assertEqual(service.get_evidence(first.report_id).outcome, "pass")
        pack = service.get_evidence(current.report_id)
        self.assertEqual(pack.outcome, "fail")
        self.assertEqual(pack.baseline_report_id, first.report_id)
        self.assertEqual(
            pack.gates["PerformanceGate"].acceptance.metrics["cpu"].score, 0
        )
        nfr = pack.gates["PerformanceGate"].acceptance.metrics["transaction_nfr_status"]
        self.assertAlmostEqual(nfr.score, 1 - 0.7804878048780488)


if __name__ == "__main__":
    unittest.main()
