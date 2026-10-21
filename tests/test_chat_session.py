import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

from src.chat_session import build_chat_session
from src.configs.application.local import LocalConfig

EXAMPLE_REPORT = Path("data/raw/reports/example_reports/report.html")


class BuildChatSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / "reports.sqlite3"
        self.llm = Mock()
        self.llm.bind_tools.return_value = FakeMessagesListChatModel(
            responses=[AIMessage(content="Hello")]
        )

    def local_config(self, reports):
        return LocalConfig.model_validate(
            {"system": {"db_path": self.db_path}, "data": {"reports": reports}}
        )

    def build(self, reports):
        with (
            patch(
                "src.chat_session.load_local_config",
                return_value=self.local_config(reports),
            ),
            patch("src.chat_session.init_llm", return_value=self.llm),
        ):
            return build_chat_session()

    def test_builds_a_graph_ready_to_chat_about_the_latest_report(self):
        session = self.build(
            [
                {
                    "path": EXAMPLE_REPORT,
                    "generated_at_date": "2026-09-02",
                    "generated_at_time": "08:44:22",
                }
            ]
        )

        report_id = session.trace_metadata["current_report_id"]
        self.assertIn(report_id, session.system_prompt)
        tool_names = {tool.name for tool in self.llm.bind_tools.call_args.args[0]}
        self.assertIn("cicd_tool", tool_names)

        response = session.graph.invoke(
            {
                "messages": [
                    SystemMessage(content=session.system_prompt),
                    HumanMessage(content="Hi"),
                ]
            },
            config={"configurable": {"thread_id": "session-test"}},
        )
        self.assertEqual(response["messages"][-1].content, "Hello")

    def test_requires_a_stored_report(self):
        with self.assertRaisesRegex(ValueError, "At least one stored report"):
            self.build([])
        self.llm.bind_tools.assert_not_called()


if __name__ == "__main__":
    unittest.main()
