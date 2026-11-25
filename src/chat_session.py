from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from src.adapters.outbound.github_dispatch import GitHubDispatch
from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.ontology.turtle_kb import TurtleKB
from src.adapters.outbound.sqlite.sqlite_db import SQLiteDB
from src.adapters.outbound.yaml_target_source import YamlTargetSource
from src.application.performance_assessment import build_performance_assessment_service
from src.application.ports.outbound.report_questions import ReportQuestions
from src.application.ports.outbound.report_repository import ReportRepository
from src.application.use_cases.answer_report_questions import (
    ReportNotFoundError,
    ReportQuestionService,
)
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.application.local import SystemConfig, load_local_config
from src.configs.cicd.github_dispatch_config import load_github_dispatch_config
from src.configs.env import read_env_file
from src.configs.ingestion.html_mapping import load_html_mapping
from src.configs.llm.llm_config import load_llm_config
from src.domain.assessment import Outcome
from src.domain.history import report_order
from src.harness.graph import build_graph
from src.harness.system.system_prompt import system_prompt
from src.harness.tools.cicd_tools import build_cicd_tool
from src.harness.tools.report_tools import build_tools
from src.llm.llm import init_llm

CICD_CONFIG_PATH = Path("configs/cicd/github_dispatch.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")
PERFORMANCE_CONFIG_PATH = Path("configs/gates/performance/performance_gate.yaml")


@dataclass(frozen=True)
class ChatSession:
    """A ready-to-chat agent, independent of the user interface driving it."""

    graph: CompiledStateGraph
    system_prompt: str
    trace_metadata: dict[str, str]


class Store(ReportRepository, ReportQuestions, Protocol):
    """Import, assessment and question answering in one store."""


def open_repository(system: SystemConfig) -> Store:
    """The configured store; every store implements the same port (ADR 0013)."""
    match system.store:
        case "knowledge_base":
            return _open_knowledge_base(system)
        case "sqlite":
            return _open_sqlite(system)
        case unknown:
            raise ValueError(f"Unsupported store: {unknown!r}")


def _open_knowledge_base(system: SystemConfig) -> TurtleKB:
    assert system.kb_dir is not None
    return TurtleKB(system.kb_dir)


def _open_sqlite(system: SystemConfig) -> SQLiteDB:
    assert system.db_path is not None
    return SQLiteDB(system.db_path)


def build_chat_session() -> ChatSession:
    """Import and assess reports, then wire the LLM, tools and graph."""
    local_config = load_local_config(LOCAL_CONFIG_PATH)
    repository = open_repository(local_config.system)
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
        repository,
    )
    if not reports:
        raise ValueError("At least one stored report is required for chat")
    current_report = max(reports, key=report_order)
    assessment = build_performance_assessment_service(
        repository, YamlTargetSource(PERFORMANCE_CONFIG_PATH).targets()
    )

    assessment.prepare()
    questions = ReportQuestionService(repository, assessment.gates)

    def current_outcome() -> Outcome | None:
        """The current report's outcome; None when it is missing."""
        try:
            return questions.describe_report(current_report.report_id).outcome
        except ReportNotFoundError:
            return None

    def deployment_payload() -> dict[str, str]:
        """The dispatch's client payload; the graph only lets 'pass' through."""
        return {
            "report_id": str(current_report.report_id),
            "outcome": current_outcome() or "missing",
        }

    cicd_config = load_github_dispatch_config(CICD_CONFIG_PATH)
    # A missing token only fails the CI/CD call, so report questions still work.
    dispatch = GitHubDispatch(cicd_config, read_env_file(cicd_config.token_env))
    tools = [*build_tools(questions), build_cicd_tool(dispatch, deployment_payload)]
    model_with_tools = init_llm(load_llm_config(local_config.system.llm)).bind_tools(
        tools
    )

    # One checkpointer for the process; conversations are separated by thread_id.
    graph = build_graph(model_with_tools, tools, MemorySaver(), current_outcome)
    return ChatSession(
        graph=graph,
        system_prompt=system_prompt(current_report),
        trace_metadata={
            "current_report_id": str(current_report.report_id),
            "assessment_version": assessment.version,
            "store": local_config.system.store,
        },
    )
