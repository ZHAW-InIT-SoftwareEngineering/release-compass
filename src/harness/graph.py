from collections.abc import Sequence

from langchain.messages import AIMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition


def _handle_tool_error(error: ToolException) -> str:
    """Return expected tool failures to the model; other exceptions propagate."""
    return str(error)


def build_graph(model_with_tools, tools: Sequence[BaseTool]) -> CompiledStateGraph[MessagesState, None, MessagesState, MessagesState]:
    """Build a minimal ReAct loop: model, optional tools, then model again."""
    graph = StateGraph(MessagesState)

    def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
        return {"messages": [model_with_tools.invoke(state["messages"])]}

    graph.add_node("llm", call_model)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=_handle_tool_error))
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")

    return graph.compile()
