import unittest
from unittest.mock import Mock
from uuid import uuid4

from langchain.messages import AIMessage, HumanMessage

from src.domain.gates.performance.performance_gate import PerformanceGate
from src.domain.report import Report
from src.harness.graph import build_graph
from src.harness.tools.compare_performance import build_compare_gate_tool


class ToolErrorTests(unittest.TestCase):
    def setUp(self):
        self.reader = Mock()
        self.current_id = uuid4()
        self.baseline_id = uuid4()
        self.arguments = {
            "report_id": str(self.current_id),
            "baseline_report_id": str(self.baseline_id),
        }

    def invoke_graph(self, arguments):
        model = Mock()
        model.invoke.side_effect = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "compare_gate",
                        "args": arguments,
                        "id": "comparison",
                    }
                ],
            ),
            AIMessage(content="Handled comparison result"),
        ]
        tool = build_compare_gate_tool(self.reader, PerformanceGate)
        result = build_graph(model, [tool]).invoke(
            {
                "messages": [HumanMessage(content="Compare the reports")],
            }
        )
        tool_message = result["messages"][-2]
        self.assertEqual(model.invoke.call_count, 2)
        self.assertEqual(model.invoke.call_args.args[0][-1], tool_message)
        return tool_message

    def test_invalid_uuid_returns_named_error_to_model(self):
        for argument in self.arguments:
            with self.subTest(argument=argument):
                message = self.invoke_graph({**self.arguments, argument: "report.html"})
                self.assertEqual(message.status, "error")
                self.assertIn(
                    f"{argument} must be a valid report UUID", message.content
                )
                self.assertIn("report.html", message.content)
        self.reader.get_by_id.assert_not_called()

    def test_missing_report_returns_error_to_model(self):
        for current_exists in (False, True):
            with self.subTest(current_exists=current_exists):
                self.reader.get_by_id.side_effect = (
                    [Report(report_id=self.current_id), None]
                    if current_exists
                    else [None]
                )
                message = self.invoke_graph(self.arguments)
                self.assertEqual(message.status, "error")
                self.assertIn(
                    "Baseline report" if current_exists else "Current report",
                    message.content,
                )
                self.assertIn("was not found", message.content)

    def test_unexpected_storage_error_propagates(self):
        for error in (RuntimeError("storage failed"), KeyError("corrupt record")):
            with self.subTest(error=type(error).__name__):
                self.reader.get_by_id.side_effect = error
                with self.assertRaises(type(error)):
                    self.invoke_graph(self.arguments)

    def test_valid_comparison_returns_success(self):
        self.reader.get_by_id.side_effect = [
            Report(report_id=report_id, gates=[PerformanceGate()])
            for report_id in (self.current_id, self.baseline_id)
        ]
        message = self.invoke_graph(self.arguments)
        self.assertEqual(message.status, "success")
        self.assertIn('"gate_type":"PerformanceGate"', message.content)


if __name__ == "__main__":
    unittest.main()
