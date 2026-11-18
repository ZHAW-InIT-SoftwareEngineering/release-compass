"""Answer the competency questions from the store (ADR 0013).

Nothing is calculated here: values, outcomes and baselines come from the
store; this service only checks reports exist and adds the required gates.
"""

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from src.application.ports.outbound.report_questions import (
    Baselines,
    GateResult,
    MeasurementChange,
    ReportQuestions,
    ReportSummary,
)


class ReportNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class OutcomeExplanation:
    report: ReportSummary
    gates: list[GateResult]
    # Required gate types the report does not contain; they make it unknown.
    missing_gates: list[str]


class ReportQuestionService:
    def __init__(
        self, questions: ReportQuestions, required_gate_types: Collection[str]
    ):
        self.questions = questions
        self.required_gate_types = sorted(set(required_gate_types))

    def describe_report(self, report_id: UUID, label: str = "Report") -> ReportSummary:
        summary = self.questions.describe_report(report_id)
        if summary is None:
            raise ReportNotFoundError(f"{label} {report_id} was not found")
        return summary

    def previous_report(self, report_id: UUID) -> ReportSummary | None:
        """The chronological predecessor, None at the start of history."""
        current = self.describe_report(report_id)
        if current.previous_report_id is None:
            return None
        return self.describe_report(current.previous_report_id)

    def baselines(self, report_id: UUID) -> Baselines:
        result = self.questions.baselines(report_id)
        if result is None:
            raise ReportNotFoundError(f"Report {report_id} was not found")
        return result

    def compare_gate(
        self,
        report_id: UUID,
        baseline_report_id: UUID,
        gate_type: str,
        metric: str,
        statistic: str,
    ) -> list[MeasurementChange]:
        self.describe_report(report_id, "Current report")
        self.describe_report(baseline_report_id, "Baseline report")
        return self.questions.compare_measurements(
            report_id, baseline_report_id, gate_type, metric, statistic
        )

    def explain_outcome(self, report_id: UUID) -> OutcomeExplanation:
        report = self.describe_report(report_id)
        return OutcomeExplanation(
            report,
            self.questions.gate_results(report_id),
            [
                gate
                for gate in self.required_gate_types
                if gate not in report.gate_types
            ],
        )
