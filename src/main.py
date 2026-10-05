from collections.abc import Sequence
from pathlib import Path

from langchain.messages import AnyMessage, HumanMessage, SystemMessage

from .adapters.outbound.html_report import HTMLReport
from .adapters.outbound.sqlite_report_repository import SQLiteReportRepository
from .application.ports.outbound.report_ingestion import ReportIngestionPort
from .application.ports.outbound.report_writer import ReportWriter
from .configs.application.local import ReportInputConfig, load_local_config
from .configs.llm.llm_config import load_llm_config
from .domain.gates.performance.performance_gate import PerformanceGate
from .domain.report import Report
from .harness.graph import build_graph
from .harness.system.system_prompt import system_prompt
from .harness.tools.compare_performance import build_compare_gate_tool
from .llm.llm import init_llm

LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")


def ingest_configured_reports(
    report_configs: Sequence[ReportInputConfig],
    report_ingestion: ReportIngestionPort,
    report_repository: ReportWriter,
) -> list[Report]:
    """Ingest configured reports, apply configured timestamps, and persist them."""
    reports = []
    for report_config in report_configs:
        report = report_ingestion.ingest(report_config.path)
        if report.generated_at_date is None and report.generated_at_time is None:
            report.generated_at_date = report_config.generated_at_date
            report.generated_at_time = report_config.generated_at_time
        elif report.generated_at_date is None or report.generated_at_time is None:
            raise ValueError(
                f"Report {report_config.path} must provide both generated-at fields"
            )
        report_repository.save(report)
        reports.append(report)

    if len(reports) < 2:
        raise ValueError("At least two configured reports are required for comparison")
    return reports


def main() -> None:
    local_config = load_local_config(LOCAL_CONFIG_PATH)
    report_repository = SQLiteReportRepository(local_config.system.db_path)

    report_ingestion: ReportIngestionPort = HTMLReport()
    reports = ingest_configured_reports(
        local_config.data.reports, report_ingestion, report_repository
    )
    last_report, current_report = reports[-2:]

    llm_config = load_llm_config(LLM_CONFIG_PATH)
    llm = init_llm(llm_config)
    compare_tool = build_compare_gate_tool(report_repository, PerformanceGate)
    tools = [compare_tool]
    model_with_tools = llm.bind_tools(tools)
    graph = build_graph(model_with_tools, tools)

    SYSTEM_PROMPT = system_prompt(current_report, last_report)
    messages: list[AnyMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            response = graph.invoke(
                {"messages": [*messages, HumanMessage(content=user_input)]}
            )
            messages = response["messages"]
            print(f"Assistant: {messages[-1].content}")
    except KeyboardInterrupt:
        print("\nGoodbye")


if __name__ == "__main__":
    main()
