from collections.abc import Mapping
from typing import Protocol


class DeploymentTriggerError(Exception):
    """The deployment could not be triggered; safe to report to the model."""


class DeploymentTrigger(Protocol):
    """Starts the external CI/CD deployment workflow."""

    def trigger(self, payload: Mapping[str, str]) -> None: ...
