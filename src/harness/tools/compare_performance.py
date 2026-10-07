"""LangChain adapter for comparing a selected report gate."""

import json
from uuid import UUID

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


def _report_uuid(value: str, argument: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ToolException(
            f"{argument} must be a valid report UUID; received {value!r}. "
            "Use the UUID assigned to an ingested report."
        ) from error


def build_compare_gate_tool(
    report_reader: ReportReader, gate_type: type[Gate]
) -> BaseTool:
    """Build a model-facing tool with storage and gate selection supplied by the host."""

    @tool("compare_gate")
    def compare_gate_tool(report_id: str, baseline_report_id: str) -> str:
        """Compare one gate type in the current report with its baseline report."""
        current_id = _report_uuid(report_id, "report_id")
        baseline_id = _report_uuid(baseline_report_id, "baseline_report_id")
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


def build_performance_tools(service: AssessmentService) -> list[BaseTool]:
    """Bind deterministic evidence and history to one assessment version."""

    def evidence_id(value: str) -> UUID:
        return _report_uuid(value, "report_id")

    @tool("compare_performance")
    def compare_performance_tool(report_id: str) -> str:
        """Get assessed Performance evidence with automatically selected passing baselines."""
        current_id = evidence_id(report_id)
        try:
            result = tool_evidence(service.get_evidence(current_id))
        except (ReportNotFoundError, EvidenceUnavailableError) as error:
            raise ToolException(str(error)) from error
        return json.dumps(result, separators=(",", ":"), allow_nan=False)

    @tool("get_previous_report")
    def get_previous_report_tool(report_id: str) -> str:
        """Get the immediately previous report's enriched evidence, or the history-end result."""
        current_id = evidence_id(report_id)
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

    return [compare_performance_tool, get_previous_report_tool]
