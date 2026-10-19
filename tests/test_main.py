import unittest
from unittest.mock import Mock, patch

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, Interrupt

from src.harness.graph import build_graph
from src.main import run_chat


class ChatInterruptTests(unittest.TestCase):
    def setUp(self):
        self.dispatch = Mock(return_value="CI/CD triggered")
        tool = StructuredTool.from_function(
            func=lambda: self.dispatch(),
            name="cicd_tool",
            description="Trigger CI/CD",
        )
        self.model = Mock()
        self.graph = build_graph(self.model, [tool], MemorySaver())
        self.config = {"configurable": {"thread_id": "test-chat"}}

    def cicd_request(self, call_id="deploy"):
        return AIMessage(
            content="",
            tool_calls=[{"name": "cicd_tool", "args": {}, "id": call_id}],
        )

    def run_inputs(self, inputs):
        with (
            patch("builtins.input", side_effect=[*inputs, KeyboardInterrupt()]),
            patch("builtins.print") as output,
        ):
            run_chat(self.graph, self.config, "System prompt")
        return [call.args[0] for call in output.call_args_list]

    def test_invalid_answer_retries_before_approval_and_history_is_retained(self):
        self.model.invoke.side_effect = [
            self.cicd_request(),
            AIMessage(content="Deployed"),
            AIMessage(content="Follow-up"),
        ]

        def user_input(_prompt):
            value = next(inputs)
            if value in ("nonsense", " YES "):
                self.dispatch.assert_not_called()
            if isinstance(value, BaseException):
                raise value
            return value

        inputs = iter(
            ["Deploy", "nonsense", " YES ", "What happened?", KeyboardInterrupt()]
        )
        with (
            patch("builtins.input", side_effect=user_input),
            patch("builtins.print") as output,
            patch.object(self.graph, "invoke", wraps=self.graph.invoke) as invoke,
        ):
            run_chat(self.graph, self.config, "System prompt")

        self.dispatch.assert_called_once()
        calls = invoke.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIsInstance(calls[1].args[0], Command)
        self.assertEqual(list(calls[1].args[0].resume.values()), [True])
        self.assertEqual(len(calls[2].args[0]["messages"]), 1)
        for call in calls:
            self.assertEqual(
                call.kwargs["config"]["configurable"], self.config["configurable"]
            )
        self.assertEqual(
            [call.kwargs["config"]["run_name"] for call in calls],
            ["harness.turn", "harness.resume", "harness.turn"],
        )
        history = self.model.invoke.call_args.args[0]
        self.assertEqual(sum(isinstance(m, SystemMessage) for m in history), 1)
        self.assertEqual(sum(isinstance(m, HumanMessage) for m in history), 2)
        self.assertIn(
            'Please answer "yes" or "no".',
            [str(call.args[0]) for call in output.call_args_list],
        )
        output.assert_any_call("Tool: cicd_tool")
        output.assert_any_call("Arguments: {}")
        output.assert_any_call("Assistant: Follow-up")

    def test_rejection_returns_to_model_without_dispatch(self):
        self.model.invoke.side_effect = [
            self.cicd_request(),
            AIMessage(content="Cancelled"),
        ]
        output = self.run_inputs(["Deploy", " NO "])
        self.dispatch.assert_not_called()
        self.assertIn("Assistant: Cancelled", output)
        history = self.model.invoke.call_args.args[0]
        self.assertEqual(history[-1].content, "The user rejected the CI/CD trigger.")

    def test_resume_handles_another_interrupt_and_blocks_second_dispatch(self):
        self.model.invoke.side_effect = [
            self.cicd_request("first"),
            self.cicd_request("second"),
            AIMessage(content="Deployed"),
            self.cicd_request("third"),
            AIMessage(content="Already deployed"),
        ]
        output = self.run_inputs(["Deploy", "no", "yes", "Deploy again"])
        self.dispatch.assert_called_once()
        question = "Do you approve triggering the CI/CD workflow? (yes/no)"
        self.assertEqual(output.count(question), 2)
        self.assertIn("Assistant: Already deployed", output)

    def test_unknown_interrupt_kind_does_not_resume(self):
        graph = Mock()
        graph.invoke.return_value = {
            "__interrupt__": (Interrupt(value={"kind": "unknown"}, id="pending"),)
        }
        with (
            patch("builtins.input", return_value="Deploy"),
            self.assertRaisesRegex(ValueError, "Unknown interrupt kind"),
        ):
            run_chat(graph, self.config, "System prompt")
        graph.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
