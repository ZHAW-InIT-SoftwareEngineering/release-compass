"""Trigger a GitHub Actions workflow via repository_dispatch.

API: https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event
"""

import json
import urllib.error
import urllib.request
from collections.abc import Mapping

from pydantic import SecretStr

from src.application.ports.outbound.deployment_trigger import DeploymentTriggerError
from src.configs.cicd.github_dispatch_config import GitHubDispatchConfig

API_VERSION = "2022-11-28"


class GitHubDispatch:
    def __init__(self, config: GitHubDispatchConfig, token: SecretStr | None):
        self.config = config
        self.token = token

    @property
    def url(self) -> str:
        base = str(self.config.api_url).rstrip("/")
        return f"{base}/repos/{self.config.owner}/{self.config.repo}/dispatches"

    def trigger(self, payload: Mapping[str, str]) -> None:
        if not self.token:
            raise DeploymentTriggerError(f"Missing {self.config.token_env} in .env")

        body = {"event_type": self.config.event_type, "client_payload": dict(payload)}
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token.get_secret_value()}",
                "Content-Type": "application/json",
                "User-Agent": "release-compass",
                "X-GitHub-Api-Version": API_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.timeout_seconds
            ) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            raise DeploymentTriggerError(
                f"GitHub rejected the dispatch: HTTP {error.code} {error.reason}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise DeploymentTriggerError(f"GitHub is unreachable: {reason}") from error

        if status != 204:
            raise DeploymentTriggerError(f"Unexpected GitHub response: HTTP {status}")
