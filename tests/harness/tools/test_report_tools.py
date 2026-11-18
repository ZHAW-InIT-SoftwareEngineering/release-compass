import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from langchain.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from src.application.ports.outbound.report_questions import (
    Baselines,
    GateResult,
    MeasurementChange,
    MetricResult,
    ReportSummary,
    SourceResult,
)
from src.application.use_cases.answer_report_questions import ReportQuestionService
from src.domain.gates.performance.measurements import SUPPORTED
from src.harness.graph import build_graph
from src.harness.tools.report_tools import LIST_LIMIT, build_report_tools


def summary(report_id, previous=None):
    return ReportSummary(
        report_id,
        datetime(2026, 9, 2, 8, tzinfo=UTC),
        1,
        ["report.html"],
        ["performance"],
        "pass",
        previous is None,
        previous,
    )


class ReportToolTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.current_id = uuid4()
        self.baseline_id = uuid4()
        self.tools = build_report_tools(
            ReportQuestionService(self.store, ["performance"]),
            {"performance": SUPPORTED},
        )

    def invoke_graph(self, name, arguments):
        """Run one tool call through the harness graph; return its message."""
        model = Mock()
        model.invoke.side_effect = [
            AIMessage(
                content="",
                tool_calls=[{"name": name, "args": arguments, "id": "call"}],
            ),
            AIMessage(content="Handled"),
        ]
        result = build_graph(model, self.tools, MemorySaver(), lambda: "pass").invoke(
            {"messages": [HumanMessage(content="Question")]},
            {"configurable": {"thread_id": "tools"}},
        )
        message = result["messages"][-2]
        self.assertEqual(model.invoke.call_args.args[0][-1], message)
        return message

    def compare_arguments(self):
        return {
            "report_id": str(self.current_id),
            "baseline_report_id": str(self.baseline_id),
        }

    def test_invalid_uuid_returns_named_error_to_model(self):
        for argument in ("report_id", "baseline_report_id"):
            with self.subTest(argument=argument):
                message = self.invoke_graph(
                    "compare_gate", {**self.compare_arguments(), argument: "a.html"}
                )
                self.assertEqual(message.status, "error")
                self.assertIn(
                    f"{argument} must be a valid report UUID", message.content
                )
                self.assertIn("a.html", message.content)
        self.store.describe_report.assert_not_called()

    def test_missing_report_returns_error_to_model(self):
        for current_exists in (False, True):
            with self.subTest(current_exists=current_exists):
                self.store.describe_report.side_effect = (
                    [summary(self.current_id), None] if current_exists else [None]
                )
                message = self.invoke_graph("compare_gate", self.compare_arguments())
                self.assertEqual(message.status, "error")
                self.assertIn(
                    "Baseline report" if current_exists else "Current report",
                    message.content,
                )
                self.assertIn("was not found", message.content)

    def test_unsupported_statistic_returns_error_to_model(self):
        message = self.invoke_graph(
            "compare_gate", {**self.compare_arguments(), "statistic": "p99"}
        )
        self.assertEqual(message.status, "error")
        self.assertIn("performance response_time.p90", message.content)

    def test_unexpected_storage_error_propagates(self):
        for error in (RuntimeError("storage failed"), KeyError("corrupt record")):
            with self.subTest(error=type(error).__name__):
                self.store.describe_report.side_effect = error
                with self.assertRaises(type(error)):
                    self.invoke_graph(
                        "describe_report", {"report_id": str(self.current_id)}
                    )

    def test_compare_returns_largest_deltas_first(self):
        self.store.describe_report.side_effect = lambda report_id: summary(report_id)
        self.store.compare_measurements.return_value = [
            MeasurementChange(f"t{index}", "ms", "ms", index, 0, index)
            for index in range(LIST_LIMIT + 2)
        ] + [MeasurementChange("no-value", "ms", "ms", None, 1, None)]
        message = self.invoke_graph("compare_gate", self.compare_arguments())
        self.assertEqual(message.status, "success")
        payload = json.loads(message.content)
        self.assertEqual(payload["matched_sources"], LIST_LIMIT + 3)
        self.assertEqual(payload["compared_sources"], LIST_LIMIT + 2)
        self.assertEqual(len(payload["largest_changes"]), LIST_LIMIT)
        self.assertEqual(payload["largest_changes"][0]["source"], f"t{LIST_LIMIT + 1}")

    def test_previous_report_of_root_ends_history(self):
        self.store.describe_report.return_value = summary(self.current_id)
        payload = json.loads(
            self.invoke_graph(
                "get_previous_report", {"report_id": str(self.current_id)}
            ).content
        )
        self.assertEqual(
            payload,
            {
                "report_id": str(self.current_id),
                "history_end": True,
                "previous_report": None,
            },
        )

    def test_baseline_includes_selection_policy(self):
        self.store.baselines.return_value = Baselines(self.current_id, None, [])
        payload = json.loads(
            self.invoke_graph(
                "get_baseline", {"report_id": str(self.current_id)}
            ).content
        )
        self.assertIsNone(payload["baseline_report_id"])
        self.assertIn("pass", payload["selection_policy"])

    def test_explain_outcome_counts_and_limits_sources(self):
        self.store.describe_report.return_value = summary(self.current_id)
        sources = [
            SourceResult(f"t{index}", 5000, False, False, None)
            for index in range(LIST_LIMIT + 1)
        ] + [SourceResult("idle", None, None, True, "No observations")]
        self.store.gate_results.return_value = [
            GateResult(
                "performance",
                "fail",
                [
                    MetricResult(
                        "response_time",
                        "p90",
                        "ms",
                        None,
                        3000,
                        0.8,
                        0.1,
                        "fail",
                        None,
                        "target-ranges-v1",
                        sources,
                    )
                ],
            )
        ]
        payload = json.loads(
            self.invoke_graph(
                "explain_outcome", {"report_id": str(self.current_id)}
            ).content
        )
        (metric,) = payload["gates"][0]["metrics"]
        self.assertEqual(
            metric["sources"],
            {
                "total": LIST_LIMIT + 2,
                "meet_target": 0,
                "miss_target": LIST_LIMIT + 1,
                "excluded": 1,
                "not_evaluable": 0,
            },
        )
        self.assertEqual(len(metric["missing_target"]), LIST_LIMIT)
        self.assertEqual(payload["missing_required_gates"], [])


if __name__ == "__main__":
    unittest.main()
