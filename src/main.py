from pathlib import Path
from uuid import uuid4

from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from openinference.instrumentation import using_attributes

from src.adapters.outbound.html_report import HTMLReport
from src.adapters.outbound.sqlite_report_repository import SQLiteReportRepository
from src.application.performance_assessment import build_performance_assessment_service
from src.application.use_cases.import_reports import ReportInput, import_reports
from src.configs.application.local import load_local_config
from src.configs.gates.performance.performance_gate import load_performance_gate_config
from src.configs.llm.llm_config import load_llm_config
from src.configs.trace.trace_config import load_trace_config
from src.domain.gates.performance.serialization import PERFORMANCE_DOMAIN_TYPES
from src.domain.history import report_order
from src.harness.graph import build_graph
from src.harness.interrupt_handler import InterruptHandler
from src.harness.system.system_prompt import system_prompt
from src.harness.tools.build_tools import build_tools
from src.harness.trace.phoenix import phoenix_server
from src.harness.trace.trace import tracing
from src.llm.llm import init_llm

LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
LOCAL_CONFIG_PATH = Path("configs/application/local.yaml")
PERFORMANCE_CONFIG_PATH = Path("configs/gates/performance/performance_gate.yaml")
TRACE_CONFIG_PATH = Path("configs/trace/trace.yaml")


def main() -> None:
    trace_config = load_trace_config(TRACE_CONFIG_PATH)
    with phoenix_server(trace_config), tracing(trace_config):
        _run()


def _run() -> None:
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

    checkpointer = MemorySaver()

    graph = build_graph(model_with_tools, tools, checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid4())}}

    run_chat(
        graph,
        config,
        system_prompt(current_report),
        trace_metadata={"current_report_id": str(current_report.report_id)},
    )


def run_chat(
    graph: CompiledStateGraph,
    config: RunnableConfig,
    prompt: str,
    trace_metadata: dict[str, str] | None = None,
) -> None:
    """Run the CLI conversation and resolve approval interrupts before continuing."""
    messages: list[AnyMessage] = [SystemMessage(content=prompt)]
    # One trace session per checkpointer thread; each invoke is a root trace.
    session_id = str(config.get("configurable", {}).get("thread_id", ""))
    metadata = trace_metadata or {}

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            with using_attributes(session_id=session_id, metadata=metadata):
                response = graph.invoke(
                    {"messages": [*messages, HumanMessage(content=user_input)]},
                    config={**config, "run_name": "harness.turn"},
                )

            pending = response.get("__interrupt__")
            while pending:
                answers: dict[str, bool] = {}
                for request in pending:
                    payload = request.value
                    if payload["kind"] != "cicd_approval":
                        raise ValueError(f"Unknown interrupt kind: {payload['kind']}")

                    print(payload["question"])
                    print(f"Tool: {payload['tool']}")
                    print(f"Arguments: {payload['arguments']}")
                    while True:
                        try:
                            answer = InterruptHandler.parse_cicd_approval(
                                input("You: ")
                            )
                            break
                        except ValueError as error:
                            print(error)
                    answers[request.id] = answer

                with using_attributes(session_id=session_id, metadata=metadata):
                    response = graph.invoke(
                        Command(resume=answers),
                        config={**config, "run_name": "harness.resume"},
                    )
                pending = response.get("__interrupt__")

            print(f"Assistant: {response['messages'][-1].content}")
            # The checkpointer retains history, including the initial system prompt.
            messages = []
    except KeyboardInterrupt:
        print("\nGoodbye")


if __name__ == "__main__":
    main()
