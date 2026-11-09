from dataclasses import dataclass, field
from typing import Any

from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from openinference.instrumentation import using_attributes

CICD_APPROVAL_KIND = "cicd_approval"


@dataclass(frozen=True)
class ApprovalRequest:
    interrupt_id: str
    question: str
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class TurnResult:
    """Either the assistant's reply or the approvals the paused graph awaits."""

    reply: str | None = None
    approvals: tuple[ApprovalRequest, ...] = field(default_factory=tuple)


class Conversation:
    """Drive one graph thread, independent of the user interface asking the user."""

    def __init__(
        self,
        graph: CompiledStateGraph,
        thread_id: str,
        system_prompt: str,
        trace_metadata: dict[str, str] | None = None,
    ) -> None:
        self._graph = graph
        self._config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        self._system_prompt: str | None = system_prompt
        # One trace session per checkpointer thread; each invoke is a root trace.
        self._trace_attributes = {
            "session_id": thread_id,
            "metadata": trace_metadata or {},
        }
        self._pending_ids: set[str] = set()

    def send(self, text: str) -> TurnResult:
        if self._pending_ids:
            raise RuntimeError("Resolve pending approvals before sending a message.")

        messages: list[AnyMessage] = [HumanMessage(content=text)]
        if self._system_prompt is not None:
            # The checkpointer retains history, so the prompt is sent only once.
            messages.insert(0, SystemMessage(content=self._system_prompt))
            self._system_prompt = None
        return self._invoke({"messages": messages}, "harness.turn")

    def resume(self, answers: dict[str, bool]) -> TurnResult:
        if set(answers) != self._pending_ids:
            raise ValueError("Answer exactly the pending approval requests.")
        return self._invoke(Command(resume=answers), "harness.resume")

    def _invoke(self, graph_input: object, run_name: str) -> TurnResult:
        with using_attributes(**self._trace_attributes):
            response = self._graph.invoke(
                graph_input, config={**self._config, "run_name": run_name}
            )

        approvals = tuple(
            _approval_request(request) for request in response.get("__interrupt__", ())
        )
        self._pending_ids = {approval.interrupt_id for approval in approvals}
        if approvals:
            return TurnResult(approvals=approvals)
        return TurnResult(reply=response["messages"][-1].text)


def _approval_request(request: Any) -> ApprovalRequest:
    payload = request.value
    if payload["kind"] != CICD_APPROVAL_KIND:
        raise ValueError(f"Unknown interrupt kind: {payload['kind']}")
    return ApprovalRequest(
        interrupt_id=request.id,
        question=payload["question"],
        tool=payload["tool"],
        arguments=payload["arguments"],
    )
