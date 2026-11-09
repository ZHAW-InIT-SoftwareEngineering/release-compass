from collections.abc import Sequence
from typing import Literal

from langchain.messages import AIMessage, ToolMessage
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import ToolCall
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, ToolException
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from src.harness.state import HarnessState

CICD_TOOL_NAME = "cicd_tool"


def _handle_tool_error(error: ToolException) -> str:
    """Return expected tool failures to the model; other exceptions propagate."""
    return str(error)


def _last_ai_message(state: HarnessState) -> AIMessage:
    """Return the AI message whose tool calls await approval."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        raise TypeError("The approval node requires a preceding AI tool call.")
    return last_message


def _cicd_call(message: AIMessage) -> ToolCall:
    """Return the CI/CD tool call that routed to approval."""
    for call in message.tool_calls:
        if call["name"] == CICD_TOOL_NAME:
            return call
    raise ValueError("The approval node requires a cicd_tool call.")


def _cicd_refusal(state: HarnessState, message: AIMessage) -> str | None:
    """Return why the CI/CD request is refused without asking, or None."""
    if state.get("cicd_triggered", False):
        return "CI/CD was already triggered in this conversation. Only once possible per session."
    if len(message.tool_calls) != 1:
        return "Request one tool at a time. The CI/CD request was not run."
    return None


def _ask_cicd_approval(call: ToolCall) -> bool:
    """Pause for the human decision; True only on explicit approval."""
    approved = interrupt(
        {
            "kind": "cicd_approval",
            "question": "Do you approve triggering the CI/CD workflow? (yes/no)",
            "tool": call["name"],
            "arguments": call["args"],
        }
    )
    return approved is True


def _answer_calls(calls: Sequence[ToolCall], content: str) -> Command[Literal["llm"]]:
    """Answer tool calls without running them and return to the model."""
    return Command(
        goto="llm",
        update={
            "messages": [
                ToolMessage(content=content, tool_call_id=call["id"]) for call in calls
            ]
        },
    )


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

    def request_cicd_approval(state: HarnessState) -> Command[Literal["tools", "llm"]]:
        message = _last_ai_message(state)
        call = _cicd_call(message)

        refusal = _cicd_refusal(state, message)
        if refusal is not None:
            return _answer_calls(message.tool_calls, refusal)

        # The decision routes this step only; nothing is persisted that could
        # authorize a later CI/CD call.
        if _ask_cicd_approval(call):
            return Command(goto="tools")
        return _answer_calls([call], "The user rejected the CI/CD trigger.")

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
    graph.add_edge("tools", "llm")

    return graph.compile(checkpointer=checkpointer)
