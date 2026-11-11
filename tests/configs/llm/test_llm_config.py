import unittest
from pathlib import Path

from pydantic import ValidationError

from src.configs.llm.llm_config import LLMConfig, load_llm_config

_BASE = {
    "model_name": "example/model",
    "base_url": "https://example.com/api",
    "api_key_env": "OPENROUTER_API_KEY",
    "max_retries": 3,
}


class LLMConfigTokenCapTests(unittest.TestCase):
    def test_accepts_max_completion_tokens_up_to_8000(self):
        config = LLMConfig(**_BASE, max_completion_tokens=8000)
        self.assertEqual(config.max_completion_tokens, 8000)

    def test_rejects_max_completion_tokens_above_8000(self):
        with self.assertRaises(ValidationError):
            LLMConfig(**_BASE, max_completion_tokens=8001)

    def test_openrouter_config_loads_with_8000_tokens(self):
        config = load_llm_config(Path("configs/llm/openrouter.yaml"))
        self.assertEqual(config.max_completion_tokens, 8000)


if __name__ == "__main__":
    unittest.main()
