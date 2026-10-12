from collections.abc import Sequence

from langchain.messages import AIMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.harness.state import HarnessState


def _handle_tool_error(error: ToolException) -> str:
    """Return expected tool failures to the model; other exceptions propagate."""
    return str(error)


def build_graph(
    model_with_tools, tools: Sequence[BaseTool]
) -> CompiledStateGraph[HarnessState, None, HarnessState, HarnessState]:
    """Build a minimal ReAct loop: model, optional tools, then model again."""
    graph = StateGraph(HarnessState)

    def call_llm(state: HarnessState) -> dict[str, list[AIMessage]]:
        return {"messages": [model_with_tools.invoke(state["messages"])]}

  
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=_handle_tool_error))
    graph.add_node("llm", call_llm)

    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")

    return graph.compile()
