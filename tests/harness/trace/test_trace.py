import json
import unittest
from unittest.mock import patch

from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.configs.trace.trace_config import TraceConfig
from src.harness.conversation import Conversation
from src.harness.graph import build_graph
from src.harness.trace.trace import tracing


class TracingTests(unittest.TestCase):
    def test_turn_and_resume_share_session_and_report_metadata(self):
        exporter = InMemorySpanExporter()
        tool = StructuredTool.from_function(
            func=lambda: "CI/CD triggered",
            name="cicd_tool",
            description="Trigger CI/CD",
        )
        model = FakeMessagesListChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "cicd_tool", "args": {}, "id": "deploy"}],
                ),
                AIMessage(content="Deployed"),
            ]
        )
        conversation = Conversation(
            build_graph(model, [tool], MemorySaver()),
            thread_id="trace-thread",
            system_prompt="System prompt",
            trace_metadata={"current_report_id": "report-1"},
        )
        with (
            patch("src.harness.trace.trace.OTLPSpanExporter", return_value=exporter),
            tracing(TraceConfig()),
        ):
            result = conversation.send("Deploy")
            conversation.resume(
                {request.interrupt_id: True for request in result.approvals}
            )

        spans = exporter.get_finished_spans()
        roots = [span for span in spans if span.parent is None]
        self.assertEqual(
            sorted(span.name for span in roots), ["harness.resume", "harness.turn"]
        )
        for span in spans:
            attributes = dict(span.attributes or {})
            self.assertEqual(attributes["session.id"], "trace-thread")
            metadata = json.loads(str(attributes["metadata"]))
            self.assertEqual(metadata["current_report_id"], "report-1")
            self.assertEqual(
                span.resource.attributes["openinference.project.name"],
                "release-compass",
            )
        kinds = [
            dict(span.attributes or {}).get("openinference.span.kind") for span in spans
        ]
        self.assertEqual(kinds.count("LLM"), 2)
        self.assertEqual(kinds.count("TOOL"), 1)

    def test_disabled_tracing_does_not_create_an_exporter(self):
        with (
            patch("src.harness.trace.trace.OTLPSpanExporter") as exporter,
            tracing(TraceConfig(enabled=False)),
        ):
            pass
        exporter.assert_not_called()

    def test_exporter_is_shutdown_when_startup_fails(self):
        exporter = InMemorySpanExporter()
        with (
            patch("src.harness.trace.trace.OTLPSpanExporter", return_value=exporter),
            patch.object(exporter, "shutdown", wraps=exporter.shutdown) as shutdown,
            self.assertRaisesRegex(RuntimeError, "Startup failed"),
            tracing(TraceConfig()),
        ):
            raise RuntimeError("Startup failed")
        shutdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()
