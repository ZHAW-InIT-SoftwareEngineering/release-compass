from pathlib import Path

from langchain.messages import HumanMessage

from .adapters.outbound.html_report import HTMLReport
from .adapters.outbound.sqlite_report_repository import SQLiteReportRepository
from .application.ports.outbound.report_ingestion import ReportIngestionPort
from .configs.application.local import load_local_config
from .configs.llm.llm_config import load_llm_config
from .domain.gates.performance.performance_gate import PerformanceGate
from .harness.tools.compare_performance import build_compare_gate_tool
from .harness.graph import build_graph
from .llm.llm import init_llm


HTML_REPORT_PATH = Path("data/raw/reports/example_reports/report.html")
LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")


def main() -> None:
    local_config = load_local_config(LOCAL_CONFIG_PATH)
    report_repository = SQLiteReportRepository(local_config.db_path)

    report_ingestion: ReportIngestionPort = HTMLReport()
    current_report = report_ingestion.ingest(HTML_REPORT_PATH)
    report_repository.save(current_report)

    llm_config = load_llm_config(LLM_CONFIG_PATH)
    llm = init_llm(llm_config)
    compare_tool = build_compare_gate_tool(report_repository, PerformanceGate)
    tools = [compare_tool]
    model_with_tools = llm.bind_tools(tools)
    graph = build_graph(model_with_tools, tools)

    baseline_report_id = input("Baseline report UUID: ").strip()
    response = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        f"Compare current report {current_report.report_id} against "
                        f"baseline report {baseline_report_id}. Explain the metric changes."
                    )
                )
            ]
        }
    )
    print(response["messages"][-1].content)


if __name__ == "__main__":
    main()
