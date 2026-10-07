"""Model-facing tools for gate-specific comparison and assessment evidence."""

import json

from langchain.tools import BaseTool, tool
from langchain_core.tools import ToolException

from src.application.ports.outbound.report_reader import ReportReader
from src.application.use_cases.assess_reports import (
    AssessmentService,
    EvidenceUnavailableError,
)
from src.application.use_cases.compare_gate import ReportNotFoundError, compare_gate
from src.domain.evidence import tool_evidence
from src.domain.gates.gate import Gate
from src.harness.tools.common import report_uuid


def build_compare_gate_tool(
    report_reader: ReportReader, gate_type: type[Gate]
) -> BaseTool:
    """Build a fixed-gate, explicit current/baseline comparison tool."""

    @tool("compare_gate")
    def compare_gate_tool(report_id: str, baseline_report_id: str) -> str:
        """Compare one gate type in the current report with its baseline report."""
        current_id = report_uuid(report_id)
        baseline_id = report_uuid(baseline_report_id, "baseline_report_id")
        try:
            result = compare_gate(current_id, baseline_id, report_reader, gate_type)
        except ReportNotFoundError as error:
            raise ToolException(
                f"{error}. Use the UUID of a report available in storage."
            ) from error
        payload = {
            "gate_type": result.gate_type,
            "numeric_deltas": {
                name: {
                    "baseline": delta.baseline,
                    "current": delta.current,
                    "delta": delta.delta,
                }
                for name, delta in result.numeric_deltas.items()
            },
        }
        return json.dumps(payload, separators=(",", ":"))

    return compare_gate_tool


def build_performance_evidence_tool(service: AssessmentService) -> BaseTool:
    """Build a tool serving assessed Performance evidence and selected baselines."""

    @tool("compare_performance")
    def compare_performance_tool(report_id: str) -> str:
        """Get assessed Performance evidence with automatically selected passing baselines."""
        current_id = report_uuid(report_id)
        try:
            result = tool_evidence(service.get_evidence(current_id))
        except (ReportNotFoundError, EvidenceUnavailableError) as error:
            raise ToolException(str(error)) from error
        return json.dumps(result, separators=(",", ":"), allow_nan=False)

    return compare_performance_tool
