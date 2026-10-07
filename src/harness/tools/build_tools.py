"""Compose all configured gate-specific and general-purpose harness tools."""

from langchain.tools import BaseTool

from src.application.use_cases.assess_reports import AssessmentService
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.harness.tools.gate_tools import (
    build_compare_gate_tool,
    build_performance_evidence_tool,
)
from src.harness.tools.report_tools import build_report_history_tools


def build_tools(service: AssessmentService) -> list[BaseTool]:
    """Build the complete tool set for the currently configured gate set."""
    return [
        build_compare_gate_tool(service.repository, PerformanceGate),
        build_performance_evidence_tool(service),
        *build_report_history_tools(service),
    ]
