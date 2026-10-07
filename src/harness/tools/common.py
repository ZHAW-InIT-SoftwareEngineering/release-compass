"""Shared input validation for model-facing tools."""

from uuid import UUID

from langchain_core.tools import ToolException


def report_uuid(value: str, argument: str = "report_id") -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ToolException(
            f"{argument} must be a valid report UUID; received {value!r}. "
            "Use the UUID assigned to an ingested report."
        ) from error
