import unittest
from unittest.mock import Mock

from langchain.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.application.ports.outbound.deployment_trigger import DeploymentTriggerError
from src.harness.graph import build_graph
from src.harness.tools.cicd_tools import build_cicd_tool

PAYLOAD = {"report_id": "abc", "outcome": "pass"}


class CICDToolTests(unittest.TestCase):
    def setUp(self):
        self.trigger = Mock()
        self.tool = build_cicd_tool(self.trigger, lambda: PAYLOAD)

    def test_takes_no_model_arguments(self):
        self.assertEqual(self.tool.name, "cicd_tool")
        self.assertEqual(self.tool.args, {})

    def test_dispatches_application_payload(self):
        result = self.tool.invoke({})
        self.trigger.trigger.assert_called_once_with(PAYLOAD)
        self.assertIn("dispatched", result)

    def test_failed_dispatch_returns_error_and_allows_retry(self):
        self.trigger.trigger.side_effect = DeploymentTriggerError("HTTP 401")
        model = Mock()
        model.invoke.side_effect = [
            AIMessage(
                content="",
                tool_calls=[{"name": "cicd_tool", "args": {}, "id": "deploy"}],
            ),
            AIMessage(content="Failed"),
        ]
        graph = build_graph(model, [self.tool], MemorySaver(), lambda: "pass")
        config: RunnableConfig = {"configurable": {"thread_id": "t"}}
        graph.invoke({"messages": []}, config)

        state = graph.invoke(Command(resume=True), config)
        tool_message = state["messages"][-2]
        self.assertEqual(tool_message.status, "error")
        self.assertIn("CI/CD was not triggered: HTTP 401", tool_message.content)
        self.assertFalse(state.get("cicd_triggered", False))


if __name__ == "__main__":
    unittest.main()
