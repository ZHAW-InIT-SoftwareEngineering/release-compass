from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.sqlite_report_repository import SQLiteReportRepository
from src.application.performance_assessment import build_performance_assessment_service
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.application.local import load_local_config
from src.configs.gates.performance.performance_gate import load_performance_gate_config
from src.configs.llm.llm_config import load_llm_config
from src.domain.gates.performance.serialization import PERFORMANCE_DOMAIN_TYPES
from src.domain.history import report_order
from src.harness.graph import build_graph
from src.harness.system.system_prompt import system_prompt
from src.harness.tools.build_tools import build_tools
from src.llm.llm import init_llm

LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")
PERFORMANCE_CONFIG_PATH = Path("configs/gates/performance/performance_gate.yaml")


@dataclass(frozen=True)
class ChatSession:
    """A ready-to-chat agent, independent of the user interface driving it."""

    graph: CompiledStateGraph
    system_prompt: str
    trace_metadata: dict[str, str]


def build_chat_session() -> ChatSession:
    """Import reports, prepare assessments, and wire the LLM, tools, and graph."""
    local_config = load_local_config(LOCAL_CONFIG_PATH)
    report_repository = SQLiteReportRepository(
        local_config.system.db_path,
        domain_types=PERFORMANCE_DOMAIN_TYPES,
    )

    import_reports(
        [
            ReportInput(item.path, item.generated_at_date, item.generated_at_time)
            for item in local_config.data.reports
        ],
        HTMLReport(),
        report_repository,
    )
    reports = report_repository.list_reports()
    if not reports:
        raise ValueError("At least one stored report is required for chat")
    current_report = max(reports, key=report_order)
    assessments = build_performance_assessment_service(
        report_repository,
        load_performance_gate_config(PERFORMANCE_CONFIG_PATH),
    )
    assessments.prepare()

    llm_config = load_llm_config(LLM_CONFIG_PATH)
    llm = init_llm(llm_config)
    tools = build_tools(assessments)
    model_with_tools = llm.bind_tools(tools)

    # One checkpointer for the process; conversations are separated by thread_id.
    graph = build_graph(model_with_tools, tools, MemorySaver())

    return ChatSession(
        graph=graph,
        system_prompt=system_prompt(current_report),
        trace_metadata={"current_report_id": str(current_report.report_id)},
    )
