import unittest
from unittest.mock import Mock, patch

from src.harness.conversation import ApprovalRequest, TurnResult
from src.main import run_chat

REQUEST = ApprovalRequest(
    interrupt_id="pending",
    question="Do you approve triggering the CI/CD workflow? (yes/no)",
    tool="cicd_tool",
    arguments={},
)


class RunChatTests(unittest.TestCase):
    def run_inputs(self, conversation, inputs):
        with (
            patch("builtins.input", side_effect=[*inputs, KeyboardInterrupt()]),
            patch("builtins.print") as output,
        ):
            run_chat(conversation)
        return [str(call.args[0]) for call in output.call_args_list]

    def test_prints_reply_and_skips_empty_input(self):
        conversation = Mock()
        conversation.send.return_value = TurnResult(reply="Hello")

        output = self.run_inputs(conversation, ["  ", " Hi "])

        conversation.send.assert_called_once_with("Hi")
        self.assertEqual(output, ["Assistant: Hello"])

    def test_invalid_answer_retries_before_resuming(self):
        conversation = Mock()
        conversation.send.return_value = TurnResult(approvals=(REQUEST,))
        conversation.resume.return_value = TurnResult(reply="Deployed")

        output = self.run_inputs(conversation, ["Deploy", "nonsense", " YES "])

        conversation.resume.assert_called_once_with({"pending": True})
        self.assertEqual(
            output,
            [
                "Do you approve triggering the CI/CD workflow? (yes/no)\n",
                'Please answer "yes" or "no".',
                "Assistant: Deployed",
            ],
        )

    def test_asks_again_when_resume_pauses_again(self):
        conversation = Mock()
        conversation.send.return_value = TurnResult(approvals=(REQUEST,))
        conversation.resume.side_effect = [
            TurnResult(approvals=(REQUEST,)),
            TurnResult(reply="Deployed"),
        ]

        output = self.run_inputs(conversation, ["Deploy", "no", "yes"])

        self.assertEqual(
            [call.args[0] for call in conversation.resume.call_args_list],
            [{"pending": False}, {"pending": True}],
        )
        self.assertEqual(output[-1], "Assistant: Deployed")


if __name__ == "__main__":
    unittest.main()
