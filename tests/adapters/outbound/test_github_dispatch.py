import io
import json
import unittest
import urllib.error
from email.message import Message
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from src.adapters.outbound.github_dispatch import GitHubDispatch
from src.application.ports.outbound.deployment_trigger import DeploymentTriggerError
from src.configs.cicd.github_dispatch_config import GitHubDispatchConfig

URLOPEN = "src.adapters.outbound.github_dispatch.urllib.request.urlopen"
PAYLOAD = {"report_id": "abc", "outcome": "pass"}


def response(status):
    context = MagicMock()
    context.__enter__.return_value.status = status
    return context


class GitHubDispatchTests(unittest.TestCase):
    def setUp(self):
        self.config = GitHubDispatchConfig(
            owner="owner",
            repo="repo",
            event_type="dummy-trigger",
            token_env="GITHUB_DISPATCH_TOKEN",
            timeout_seconds=5,
        )
        self.dispatch = GitHubDispatch(self.config, SecretStr("secret"))

    def test_posts_repository_dispatch_with_client_payload(self):
        with patch(URLOPEN, return_value=response(204)) as urlopen:
            self.dispatch.trigger(PAYLOAD)

        (request,), kwargs = urlopen.call_args
        self.assertEqual(
            request.full_url, "https://api.github.com/repos/owner/repo/dispatches"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(
            json.loads(request.data),
            {"event_type": "dummy-trigger", "client_payload": PAYLOAD},
        )
        self.assertEqual(kwargs["timeout"], 5)

    def test_missing_token_fails_without_request(self):
        with (
            patch(URLOPEN) as urlopen,
            self.assertRaisesRegex(
                DeploymentTriggerError, "Missing GITHUB_DISPATCH_TOKEN"
            ),
        ):
            GitHubDispatch(self.config, None).trigger(PAYLOAD)
        urlopen.assert_not_called()

    def test_http_error_is_reported(self):
        error = urllib.error.HTTPError(
            "url",
            404,
            "Not Found",
            Message(),
            io.BytesIO(b"{}"),
        )
        self.addCleanup(error.close)
        with (
            patch(URLOPEN, side_effect=error),
            self.assertRaisesRegex(DeploymentTriggerError, "HTTP 404 Not Found"),
        ):
            self.dispatch.trigger(PAYLOAD)

    def test_network_error_is_reported(self):
        with (
            patch(URLOPEN, side_effect=urllib.error.URLError("no route")),
            self.assertRaisesRegex(DeploymentTriggerError, "unreachable: no route"),
        ):
            self.dispatch.trigger(PAYLOAD)

    def test_unexpected_success_status_is_rejected(self):
        with (
            patch(URLOPEN, return_value=response(200)),
            self.assertRaisesRegex(DeploymentTriggerError, "HTTP 200"),
        ):
            self.dispatch.trigger(PAYLOAD)


if __name__ == "__main__":
    unittest.main()
