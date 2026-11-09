import unittest
from unittest.mock import Mock, patch

from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool, ToolException
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, Interrupt

from src.harness.conversation import ApprovalRequest, Conversation
from src.harness.graph import build_graph


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.dispatch = Mock(return_value="CI/CD triggered")
        tool = StructuredTool.from_function(
            func=lambda: self.dispatch(),
            name="cicd_tool",
            description="Trigger CI/CD",
        )
        self.model = Mock()
        self.graph = build_graph(self.model, [tool], MemorySaver())
        self.conversation = Conversation(
            self.graph, thread_id="test-chat", system_prompt="System prompt"
        )

    def cicd_request(self, call_id="deploy"):
        return AIMessage(
            content="",
            tool_calls=[{"name": "cicd_tool", "args": {}, "id": call_id}],
        )

    def approve(self, result, answer):
        return self.conversation.resume(
            {request.interrupt_id: answer for request in result.approvals}
        )

    def test_reply_without_tools(self):
        self.model.invoke.return_value = AIMessage(content="Hello")
        result = self.conversation.send("Hi")
        self.assertEqual(result.reply, "Hello")
        self.assertEqual(result.approvals, ())

    def test_cicd_call_pauses_with_approval_request(self):
        self.model.invoke.return_value = self.cicd_request()
        result = self.conversation.send("Deploy")

        self.assertIsNone(result.reply)
        [request] = result.approvals
        self.assertIsInstance(request, ApprovalRequest)
        self.assertEqual(
            request.question,
            "Do you approve triggering the CI/CD workflow? (yes/no)",
        )
        self.assertEqual(request.tool, "cicd_tool")
        self.assertEqual(request.arguments, {})
        self.dispatch.assert_not_called()

    def test_approval_dispatches_and_history_is_retained(self):
        self.model.invoke.side_effect = [
            self.cicd_request(),
            AIMessage(content="Deployed"),
            AIMessage(content="Follow-up"),
        ]
        with patch.object(self.graph, "invoke", wraps=self.graph.invoke) as invoke:
            result = self.approve(self.conversation.send("Deploy"), True)
            self.assertEqual(result.reply, "Deployed")
            self.assertEqual(
                self.conversation.send("What happened?").reply, "Follow-up"
            )

        self.dispatch.assert_called_once()
        calls = invoke.call_args_list
        self.assertIsInstance(calls[1].args[0], Command)
        self.assertEqual(list(calls[1].args[0].resume.values()), [True])
        self.assertEqual(len(calls[2].args[0]["messages"]), 1)
        for call in calls:
            self.assertEqual(
                call.kwargs["config"]["configurable"], {"thread_id": "test-chat"}
            )
        self.assertEqual(
            [call.kwargs["config"]["run_name"] for call in calls],
            ["harness.turn", "harness.resume", "harness.turn"],
        )
        history = self.model.invoke.call_args.args[0]
        self.assertEqual(sum(isinstance(m, SystemMessage) for m in history), 1)
        self.assertEqual(sum(isinstance(m, HumanMessage) for m in history), 2)

    def test_rejection_returns_to_model_without_dispatch(self):
        self.model.invoke.side_effect = [
            self.cicd_request(),
            AIMessage(content="Cancelled"),
        ]
        result = self.approve(self.conversation.send("Deploy"), False)

        self.assertEqual(result.reply, "Cancelled")
        self.dispatch.assert_not_called()
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
        result = self.approve(self.conversation.send("Deploy"), False)
        self.assertEqual(len(result.approvals), 1)
        self.assertEqual(self.approve(result, True).reply, "Deployed")

        result = self.conversation.send("Deploy again")
        self.assertEqual(result.reply, "Already deployed")
        self.dispatch.assert_called_once()

    def test_failed_approved_dispatch_does_not_authorize_later_request(self):
        self.dispatch.side_effect = [ToolException("runner down"), "CI/CD triggered"]
        self.model.invoke.side_effect = [
            self.cicd_request("first"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "cicd_tool", "args": {}, "id": "second"},
                    {"name": "cicd_tool", "args": {}, "id": "third"},
                ],
            ),
            AIMessage(content="Not deployed"),
        ]
        result = self.approve(self.conversation.send("Deploy"), True)

        self.assertEqual(result.reply, "Not deployed")
        self.dispatch.assert_called_once()
        state = self.graph.get_state(
            {"configurable": {"thread_id": "test-chat"}}
        ).values
        self.assertFalse(state.get("cicd_triggered", False))
        tool_call_ids = [
            m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage)
        ]
        self.assertEqual(tool_call_ids, ["first", "second", "third"])

    def test_send_is_refused_while_approval_is_pending(self):
        self.model.invoke.return_value = self.cicd_request()
        self.conversation.send("Deploy")
        with self.assertRaisesRegex(RuntimeError, "Resolve pending approvals"):
            self.conversation.send("Something else")

    def test_resume_requires_answers_for_exactly_the_pending_requests(self):
        self.model.invoke.return_value = self.cicd_request()
        result = self.conversation.send("Deploy")
        for answers in ({}, {"other": True}):
            with (
                self.subTest(answers=answers),
                self.assertRaisesRegex(ValueError, "pending approval requests"),
            ):
                self.conversation.resume(answers)
        self.assertEqual(len(result.approvals), 1)
        self.dispatch.assert_not_called()

    def test_unknown_interrupt_kind_is_rejected(self):
        graph = Mock()
        graph.invoke.return_value = {
            "__interrupt__": (Interrupt(value={"kind": "unknown"}, id="pending"),)
        }
        conversation = Conversation(graph, thread_id="t", system_prompt="System")
        with self.assertRaisesRegex(ValueError, "Unknown interrupt kind"):
            conversation.send("Deploy")
        graph.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
