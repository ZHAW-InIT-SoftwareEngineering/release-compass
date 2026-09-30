import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.configs.llm.llm_config import LLMConfig
from src.llm import llm as llm_module


class LLMConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = LLMConfig(
            model_name="example/model",
            base_url="https://example.com/api",
            api_key_env="OPENROUTER_API_KEY",
            max_completion_tokens=128,
            max_retries=3,
        )

    def test_reads_api_key_from_env_file_even_when_shell_value_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text('OPENROUTER_API_KEY="file-key"\n', encoding="utf-8")
            with (
                patch.object(llm_module, "_ENV_FILE", env_file),
                patch.dict(os.environ, {"OPENROUTER_API_KEY": "shell-key"}),
                patch.object(llm_module, "ChatOpenAI") as chat_openai,
            ):
                llm_module.init_llm(self.config)

            self.assertEqual(chat_openai.call_args.kwargs["api_key"], "file-key")

    def test_missing_env_file_rejects_shell_value(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            with (
                patch.object(llm_module, "_ENV_FILE", env_file),
                patch.dict(os.environ, {"OPENROUTER_API_KEY": "shell-key"}),
            ):
                with self.assertRaisesRegex(RuntimeError, "Missing OPENROUTER_API_KEY"):
                    llm_module.init_llm(self.config)


if __name__ == "__main__":
    unittest.main()
