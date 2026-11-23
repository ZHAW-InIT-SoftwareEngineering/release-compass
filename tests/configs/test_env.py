import tempfile
import unittest
from pathlib import Path

from src.configs.env import read_env_file


class ReadEnvFileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.env_file = Path(directory.name) / ".env"

    def test_reads_quoted_and_exported_values(self):
        self.env_file.write_text(
            "# comment\nexport GITHUB_DISPATCH_TOKEN='token'\nOTHER=x\n",
            encoding="utf-8",
        )
        value = read_env_file("GITHUB_DISPATCH_TOKEN", self.env_file)
        assert value is not None
        self.assertEqual(value.get_secret_value(), "token")

    def test_missing_key_or_file_is_none(self):
        self.assertIsNone(read_env_file("GITHUB_DISPATCH_TOKEN", self.env_file))
        self.env_file.write_text("OTHER=x\n", encoding="utf-8")
        self.assertIsNone(read_env_file("GITHUB_DISPATCH_TOKEN", self.env_file))


if __name__ == "__main__":
    unittest.main()
