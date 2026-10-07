from pathlib import Path

from langchain.messages import AnyMessage, HumanMessage, SystemMessage

from .adapters.outbound.html_report import HTMLReport
from .adapters.outbound.sqlite_report_repository import SQLiteReportRepository
from .application.use_cases.assess_reports import AssessmentService
from .application.use_cases.import_reports import ReportInput, import_reports
from .configs.application.local import load_local_config
from .configs.gates.performance.performance_gate import load_performance_gate_config
from .configs.llm.llm_config import load_llm_config
from .domain.history import report_order
from .harness.graph import build_graph
from .harness.system.system_prompt import system_prompt
from .harness.tools.build_tools import build_tools
from .llm.llm import init_llm

LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")
PERFORMANCE_CONFIG_PATH = Path("configs/gates/performance/performance_gate.yaml")


def main() -> None:
    local_config = load_local_config(LOCAL_CONFIG_PATH)
    report_repository = SQLiteReportRepository(local_config.system.db_path)

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
    assessments = AssessmentService(
        report_repository, load_performance_gate_config(PERFORMANCE_CONFIG_PATH)
    )
    assessments.prepare()

    llm_config = load_llm_config(LLM_CONFIG_PATH)
    llm = init_llm(llm_config)
    tools = build_tools(assessments)
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
                {"messages": [*messages, HumanMessage(content=user_input)]}
            )
            messages = response["messages"]
            print(f"Assistant: {messages[-1].content}")
    except KeyboardInterrupt:
        print("\nGoodbye")


if __name__ == "__main__":
    main()
