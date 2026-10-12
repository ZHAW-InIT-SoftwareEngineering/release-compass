from pathlib import Path

from langchain.messages import AnyMessage, HumanMessage, SystemMessage

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
from src.harness.tools.cicd_tools import cicd_tool
from src.llm.llm import init_llm

LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")
PERFORMANCE_CONFIG_PATH = Path("configs/gates/performance/performance_gate.yaml")


def main() -> None:
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
    tools = tools.append(cicd_tool)
    model_with_tools = llm.bind_tools(tools)
    graph = build_graph(model_with_tools, tools)

    SYSTEM_PROMPT = system_prompt(current_report)
    messages: list[AnyMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            response = graph.invoke(
                {
                    "messages": [*messages, HumanMessage(content=user_input)],
                    "approved_cicd": False,
                }
            )
            messages = response["messages"]
            print(f"Assistant: {messages[-1].content}")
    except KeyboardInterrupt:
        print("\nGoodbye")


if __name__ == "__main__":
    main()
