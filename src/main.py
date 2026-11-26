import argparse
import tempfile
from pathlib import Path
from uuid import uuid4

from src.chat_session import build_chat_session
from src.configs.trace.trace_config import load_trace_config
from src.harness.conversation import ApprovalRequest, Conversation
from src.harness.interrupt_handler import InterruptHandler
from src.harness.trace.phoenix import phoenix_server
from src.harness.trace.trace import tracing
from src.evaluation.conversation_asker import ConversationAsker
from src.evaluation.generate import generate_answers
from src.eval_worker import DEFAULT_DATA_DIR, run_eval_worker

TRACE_CONFIG_PATH = Path("configs/trace/trace.yaml")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="Run evaluation instead of chat")
    parser.add_argument("--config", type=Path, default=Path("configs/application/local.yaml"), help="Path to the specific configuration file")
    parser.add_argument("--eval-data", type=Path, default=DEFAULT_DATA_DIR, help="Path to the evaluation data directory")
    parser.add_argument("--answers-dir", type=Path, default=Path("answers"), help="Directory to store evaluation answers")
    parser.add_argument("--approve", action="store_true", help="Automatically approve all interruptions during evaluation" )    
    args = parser.parse_args()
    
    trace_config = load_trace_config(TRACE_CONFIG_PATH)
    with phoenix_server(trace_config), tracing(trace_config):
        _run(args)


def _run(args: argparse.Namespace) -> None:
    if args.eval:
        _run_evaluation(args)
        return

    session = build_chat_session(args.config)
    run_chat(
        Conversation(
            session.graph,
            thread_id=str(uuid4()),
            system_prompt=session.system_prompt,
            trace_metadata=session.trace_metadata,
        )
    )

def _run_evaluation(args: argparse.Namespace) -> None:
    # Stage 1: one chat session per scenario folder, opened and closed by the worker.
    answer_files = run_eval_worker(
        data_dir=args.eval_data,
        answers_dir=args.answers_dir,
        build_session=build_chat_session,
        approve=args.approve,
    )
    # Stage 2: independent of the chatbot; can also be run on its own (see score.py).
    # Score the answers against the gold answers and generate a report.

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
