"""Adapter between the evaluation runner and the chatbot (src.harness.conversation.Conversation)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import AnyMessage, HumanMessage, ToolMessage

from src.harness.conversation import Conversation

if TYPE_CHECKING:
    from src.chat_session import ChatSession


def _tool_outputs(messages: list[AnyMessage]) -> list[str]:
    """Tool results since the last human message = what the answer was based on."""
    out: list[str] = []
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, ToolMessage):
            out.append(str(message.content))
    return out[::-1]


class ConversationAsker:
    """One fresh graph thread per case; CI/CD approval interrupts are answered automatically.

    approve=False (default) denies every approval, so evaluation never triggers a real action.
    """

    def __init__(self, session: ChatSession, approve: bool = False) -> None:
        self._session = session
        self._approve = approve

    def __call__(self, question: str, case: Mapping[str, Any]) -> dict[str, Any]:
        thread_id = f"eval-{case['case_id']}-{uuid4().hex[:8]}"
        conversation = Conversation(
            self._session.graph,
            thread_id=thread_id,
            system_prompt=self._session.system_prompt,
            trace_metadata={**self._session.trace_metadata, "eval_case_id": str(case["case_id"])},
        )
        approvals: list[dict[str, Any]] = []
        result = conversation.send(question)
        while result.approvals:
            answers = {}
            for request in result.approvals:
                answers[request.interrupt_id] = self._approve
                approvals.append({"tool": request.tool, "arguments": request.arguments,
                                  "approved": self._approve})
            result = conversation.resume(answers)

        state = self._session.graph.get_state({"configurable": {"thread_id": thread_id}})
        return {
            "answer": result.reply,
            "context": _tool_outputs(state.values["messages"]) or None,
            "approvals": approvals,
        }
