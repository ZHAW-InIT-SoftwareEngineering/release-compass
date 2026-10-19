import unittest

from src.harness.interrupt_handler import InterruptHandler


class InterruptHandlerTests(unittest.TestCase):
    def test_parses_normalized_approval(self):
        for answer, expected in [
            ("yes", True),
            (" YES ", True),
            ("no", False),
            ("No", False),
        ]:
            with self.subTest(answer=answer):
                self.assertIs(InterruptHandler.parse_cicd_approval(answer), expected)

    def test_rejects_invalid_input(self):
        for answer in ("", "maybe", "true", "y", "n"):
            with (
                self.subTest(answer=answer),
                self.assertRaisesRegex(ValueError, 'Please answer "yes" or "no"'),
            ):
                InterruptHandler.parse_cicd_approval(answer)


if __name__ == "__main__":
    unittest.main()
