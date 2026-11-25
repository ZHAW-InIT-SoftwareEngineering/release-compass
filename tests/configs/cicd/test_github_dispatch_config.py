import unittest
from pathlib import Path

from pydantic import ValidationError

from src.configs.cicd.github_dispatch_config import (
    GitHubDispatchConfig,
    load_github_dispatch_config,
)


class GitHubDispatchConfigTests(unittest.TestCase):
    def test_project_config_targets_the_teastore_dummy_workflow(self):
        config = load_github_dispatch_config(Path("configs/cicd/github_dispatch.yaml"))
        self.assertEqual(config.owner, "ZHAW-InIT-SoftwareEngineering")
        self.assertEqual(config.repo, "TeaStore_internal")
        self.assertEqual(config.event_type, "dummy-trigger")
        self.assertEqual(config.token_env, "GITHUB_DISPATCH_TOKEN")
        self.assertEqual(str(config.api_url), "https://api.github.com/")

    def test_rejects_empty_event_type(self):
        with self.assertRaises(ValidationError):
            GitHubDispatchConfig(owner="o", repo="r", event_type="", token_env="TOKEN")


if __name__ == "__main__":
    unittest.main()
