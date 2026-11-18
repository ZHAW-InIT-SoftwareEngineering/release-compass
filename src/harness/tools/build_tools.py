"""Compose the competency-question tools with the CI/CD tool."""

from langchain.tools import BaseTool

from src.application.use_cases.answer_report_questions import ReportQuestionService
from src.domain.gates.registry import GATE_KINDS
from src.harness.tools.cicd_tools import cicd_tool
from src.harness.tools.report_tools import build_report_tools


def build_tools(service: ReportQuestionService) -> list[BaseTool]:
    comparable = {kind.name: kind.supported for kind in GATE_KINDS.values()}
    return [*build_report_tools(service, comparable), cicd_tool]
