from collections.abc import Sequence

from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, ToolException
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from src.harness.state import HarnessState

CICD_TOOL_NAME = "cicd_tool"


def _handle_tool_error(error: ToolException) -> str:
    """Return expected tool failures to the model; other exceptions propagate."""
    return str(error)


def build_graph(
    model_with_tools: Runnable[LanguageModelInput, AIMessage],
    tools: Sequence[BaseTool],
    checkpointer: MemorySaver,
) -> CompiledStateGraph[HarnessState, None, HarnessState, HarnessState]:
    """Build a ReAct loop that pauses before executing the CI/CD tool."""
    graph = StateGraph(HarnessState)
    tool_node = ToolNode(tools, handle_tool_errors=_handle_tool_error)

    def call_llm(state: HarnessState) -> dict[str, list[AIMessage]]:
        return {"messages": [model_with_tools.invoke(state["messages"])]}

    def route_after_llm(state: HarnessState) -> str:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return END

        if any(call["name"] == CICD_TOOL_NAME for call in last_message.tool_calls):
            return "approval"

        return "tools"

    def request_cicd_approval(state: HarnessState) -> dict[str, object]:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            raise TypeError("The approval node requires a preceding AI tool call.")

        cicd_calls = [
            call for call in last_message.tool_calls if call["name"] == CICD_TOOL_NAME
        ]
        if not cicd_calls:
            raise ValueError("The approval node requires a cicd_tool call.")

        if state.get("cicd_triggered", False):
            return {
                "messages": [
                    ToolMessage(
                        content="CI/CD was already triggered in this conversation. Only once possible per session.",
                        tool_call_id=call["id"],
                    )
                    for call in last_message.tool_calls
                ]
            }

        if len(last_message.tool_calls) != 1:
            return {
                "messages": [
                    ToolMessage(
                        content=(
                            "Request one tool at a time. The CI/CD request was not run."
                        ),
                        tool_call_id=call["id"],
                    )
                    for call in last_message.tool_calls
                ]
            }

        call = cicd_calls[0]
        approved = interrupt(
            {
                "question": "Do you approve triggering the CI/CD workflow? (yes/no)",
                "tool": call["name"],
                "arguments": call["args"],
            }
        )
        if approved is True:
            return {"user_approved_cicd": True}

        return {
            "user_approved_cicd": False,
            "messages": [
                ToolMessage(
                    content="The user rejected the CI/CD trigger.",
                    tool_call_id=call["id"],
                )
            ],
        }

    def route_after_approval(state: HarnessState) -> str:
        if state.get("user_approved_cicd", False):
            return "tools"
        return "llm"

    def execute_tools(state: HarnessState) -> dict[str, object]:
        result = tool_node.invoke(state)
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage):
            cicd_ids = {
                call["id"]
                for call in last_message.tool_calls
                if call["name"] == CICD_TOOL_NAME
            }
            executed_successfully = any(
                isinstance(message, ToolMessage)
                and message.tool_call_id in cicd_ids
                and message.status != "error"
                for message in result.get("messages", [])
            )
            if executed_successfully:
                result["cicd_triggered"] = True
                result["user_approved_cicd"] = False
        return result

    graph.add_node("llm", call_llm)
    graph.add_node("tools", execute_tools)
    graph.add_node("approval", request_cicd_approval)

    graph.add_edge(START, "llm")
    graph.add_conditional_edges(
        "llm",
        route_after_llm,
        {"approval": "approval", "tools": "tools", END: END},
    )
    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {"tools": "tools", "llm": "llm"},
    )
    graph.add_edge("tools", "llm")

    return graph.compile(checkpointer=checkpointer)
