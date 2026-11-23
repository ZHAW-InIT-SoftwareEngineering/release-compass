import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.adapters.outbound.ontology.turtle_kb import (
    FACTS_FILE,
    TurtleKB,
)
from src.chat_session import build_chat_session
from src.configs.application.local import LocalConfig

EXAMPLE_REPORT = Path(
    "data/raw/reports/example_reports/TeaStoreReports/Locust/Locust_TeaStore_Report_Original.html"
)
LOCUST_MAPPING = Path("configs/ingestion/locust.yaml")
OPENROUTER_CONFIG = Path("configs/llm/openrouter.yaml")
SGLANG_CONFIG = Path("configs/llm/sglang.yaml")


class BuildChatSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.kb_dir = Path(directory.name) / "kb"

    def build(self, reports, store="knowledge_base", llm=OPENROUTER_CONFIG):
        config = LocalConfig.model_validate(
            {
                "system": {
                    "store": store,
                    "kb_dir": self.kb_dir,
                    "db_path": self.kb_dir.parent / "reports.sqlite3",
                    "llm": llm,
                },
                "ingestion": {"mappings": {"locust": LOCUST_MAPPING}},
                "data": {"reports": reports},
            }
        )
        self.llm = Mock()
        with (
            patch("src.chat_session.load_local_config", return_value=config),
            patch("src.chat_session.init_llm", return_value=self.llm) as init_llm,
            patch("src.chat_session.GitHubDispatch") as dispatch,
        ):
            self.dispatch = dispatch.return_value
            session = build_chat_session()
            ((self.llm_config,), _) = init_llm.call_args
            return session

    def bound_tool(self, name):
        (tools,), _ = self.llm.bind_tools.call_args
        return next(tool for tool in tools if tool.name == name)

    def bound_tool_names(self):
        (tools,), _ = self.llm.bind_tools.call_args
        return [tool.name for tool in tools]

    def test_imports_assesses_and_wires_tools_on_knowledge_base(self):
        session = self.build([{"path": EXAMPLE_REPORT, "source": "locust"}])

        self.assertEqual(session.trace_metadata["store"], "knowledge_base")
        self.assertIn(
            session.trace_metadata["current_report_id"], session.system_prompt
        )
        self.assertEqual(
            self.bound_tool_names(),
            [
                "describe_report",
                "get_previous_report",
                "get_baseline",
                "compare_gate",
                "explain_outcome",
                "cicd_tool",
            ],
        )
        self.assertTrue((self.kb_dir / FACTS_FILE).exists())
        self.assertEqual(len(list(self.kb_dir.glob("assessment-*.ttl"))), 1)
        rows = TurtleKB(self.kb_dir).select(
            "SELECT ?report WHERE { ?report a release-compass:Report }"
        )
        self.assertEqual(len(rows), 1)

    def test_cicd_tool_dispatches_current_report_payload(self):
        session = self.build([{"path": EXAMPLE_REPORT, "source": "locust"}])

        self.bound_tool("cicd_tool").invoke({})

        self.dispatch.trigger.assert_called_once_with(
            {
                "report_id": session.trace_metadata["current_report_id"],
                "outcome": "pass",
            }
        )

    def test_imports_and_assesses_in_sqlite_when_configured(self):
        session = self.build([{"path": EXAMPLE_REPORT, "source": "locust"}], "sqlite")
        self.assertEqual(session.trace_metadata["store"], "sqlite")
        self.assertFalse(self.kb_dir.exists())
        connection = sqlite3.connect(self.kb_dir.parent / "reports.sqlite3")
        self.addCleanup(connection.close)
        self.assertEqual(
            connection.execute("SELECT outcome FROM report_assessments").fetchall(),
            [("pass",)],
        )

    def test_uses_llm_config_selected_in_local_config(self):
        self.build([{"path": EXAMPLE_REPORT, "source": "locust"}], llm=SGLANG_CONFIG)
        self.assertEqual(self.llm_config.api_key_env, "SGLANG_API_KEY")

        self.build([{"path": EXAMPLE_REPORT, "source": "locust"}])
        self.assertEqual(self.llm_config.api_key_env, "OPENROUTER_API_KEY")

    def test_requires_a_stored_report(self):
        with self.assertRaisesRegex(ValueError, "At least one stored report"):
            self.build([])


if __name__ == "__main__":
    unittest.main()
