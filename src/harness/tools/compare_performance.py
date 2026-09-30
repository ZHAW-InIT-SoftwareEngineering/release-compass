"""LangChain adapter for comparing a selected report gate."""

import json
from uuid import UUID

from langchain.tools import BaseTool, tool

from src.application.ports.outbound.report_reader import ReportReader
from src.application.use_cases.compare_gate import compare_gate
from src.domain.gates.gate import Gate


def build_compare_gate_tool(report_reader: ReportReader, gate_type: type[Gate]) -> BaseTool:
    """Build a model-facing tool with storage and gate selection supplied by the host."""

    @tool("compare_gate")
    def compare_gate_tool(report_id: str, baseline_report_id: str) -> str:
        """Compare one gate type in the current report with its baseline report."""
        result = compare_gate(
            UUID(report_id), UUID(baseline_report_id), report_reader, gate_type
        )
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
