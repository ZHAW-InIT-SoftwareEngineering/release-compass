"""LangChain adapter for comparing a selected report gate."""

import json
from uuid import UUID

from langchain.tools import BaseTool, tool
from langchain_core.tools import ToolException

from src.application.ports.outbound.report_reader import ReportReader
from src.application.use_cases.compare_gate import ReportNotFoundError, compare_gate
from src.domain.gates.gate import Gate


def _report_uuid(value: str, argument: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ToolException(
            f"{argument} must be a valid report UUID; received {value!r}. "
            "Use the UUID assigned to an ingested report."
        ) from error


def build_compare_gate_tool(report_reader: ReportReader, gate_type: type[Gate]) -> BaseTool:
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
