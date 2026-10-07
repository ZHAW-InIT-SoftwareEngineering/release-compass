"""Model-facing tools for general report history access."""

import json

from langchain.tools import BaseTool, tool
from langchain_core.tools import ToolException

from src.application.use_cases.assess_reports import (
    AssessmentService,
    EvidenceUnavailableError,
)
from src.application.use_cases.compare_gate import ReportNotFoundError
from src.domain.evidence import tool_evidence
from src.harness.tools.common import report_uuid


def build_report_history_tools(service: AssessmentService) -> list[BaseTool]:
    """Build tools for navigating report history, independent of gate type."""

    @tool("get_previous_report")
    def get_previous_report_tool(report_id: str) -> str:
        """Get the immediately previous report's evidence, or the history-end result."""
        current_id = report_uuid(report_id)
        try:
            current = service.get_evidence(current_id)
            result = {
                "report_id": str(current_id),
                "history_end": current.is_root,
                "previous_report": (
                    tool_evidence(service.get_evidence(current.previous_report_id))
                    if current.previous_report_id
                    else None
                ),
            }
        except (ReportNotFoundError, EvidenceUnavailableError) as error:
            raise ToolException(str(error)) from error
        return json.dumps(result, separators=(",", ":"), allow_nan=False)

    return [get_previous_report_tool]
