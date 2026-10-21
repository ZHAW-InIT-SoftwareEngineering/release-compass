from pathlib import Path
from uuid import uuid4

from src.chat_session import build_chat_session
from src.configs.trace.trace_config import load_trace_config
from src.harness.conversation import ApprovalRequest, Conversation
from src.harness.interrupt_handler import InterruptHandler
from src.harness.trace.phoenix import phoenix_server
from src.harness.trace.trace import tracing

TRACE_CONFIG_PATH = Path("configs/trace/trace.yaml")


def main() -> None:
    trace_config = load_trace_config(TRACE_CONFIG_PATH)
    with phoenix_server(trace_config), tracing(trace_config):
        _run()


def _run() -> None:
    session = build_chat_session()
    run_chat(
        Conversation(
            session.graph,
            thread_id=str(uuid4()),
            system_prompt=session.system_prompt,
            trace_metadata=session.trace_metadata,
        )
    )


def run_chat(conversation: Conversation) -> None:
    """Run the terminal conversation, asking for approvals whenever the graph pauses."""
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            result = conversation.send(user_input)
            while result.approvals:
                result = conversation.resume(
                    {
                        request.interrupt_id: _ask_approval(request)
                        for request in result.approvals
                    }
                )
            print(f"Assistant: {result.reply}")
    except KeyboardInterrupt:
        pass


def _ask_approval(request: ApprovalRequest) -> bool:
    print(f"{request.question}\n")
    while True:
        try:
            return InterruptHandler.parse_cicd_approval(input("You: "))
        except ValueError as error:
            print(error)


if __name__ == "__main__":
    main()
