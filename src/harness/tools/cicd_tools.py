from collections.abc import Callable, Mapping

from langchain.tools import BaseTool, tool
from langchain_core.tools import ToolException

from src.application.ports.outbound.deployment_trigger import (
    DeploymentTrigger,
    DeploymentTriggerError,
)


def build_cicd_tool(
    trigger: DeploymentTrigger, payload: Callable[[], Mapping[str, str]]
) -> BaseTool:
    """``payload`` is built by the application, never by the model."""

    @tool
    def cicd_tool() -> str:
        """Trigger the CI/CD deployment workflow for the current report."""
        try:
            trigger.trigger(payload())
        except DeploymentTriggerError as error:
            raise ToolException(f"CI/CD was not triggered: {error}") from error
        return (
            "CI/CD workflow dispatched; GitHub accepted the request. "
            "The run's result is not tracked here."
        )

    return cicd_tool
