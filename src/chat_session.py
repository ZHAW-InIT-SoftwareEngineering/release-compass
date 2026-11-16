from dataclasses import dataclass
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.ontology.turtle_knowledge_base import TurtleKnowledgeBase
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.application.local import load_local_config
from src.configs.ingestion.html_mapping import load_html_mapping

LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")


@dataclass(frozen=True)
class ChatSession:
    """A ready-to-chat agent, independent of the user interface driving it."""

    graph: CompiledStateGraph
    system_prompt: str
    trace_metadata: dict[str, str]


def build_chat_session() -> ChatSession | None:
    """Import reports into the knowledge base.

    For now the chain stops here and returns None: assessment, tools and the
    LLM are wired again once they read from the knowledge base
    (PLAN_ontology_knowledge_base.md, steps 4-5).
    """
    local_config = load_local_config(LOCAL_CONFIG_PATH)
    reports = import_reports(
        [
            ReportInput(
                item.path,
                item.generated_at_date,
                item.generated_at_time,
                source=item.source,
            )
            for item in local_config.data.reports
        ],
        HTMLReport(
            {
                source: load_html_mapping(path)
                for source, path in local_config.ingestion.mappings.items()
            }
        ),
        TurtleKnowledgeBase(local_config.system.kb_dir),
    )
    if not reports:
        raise ValueError("At least one stored report is required for chat")
    return None
