"""Model-facing tools, one per competency question (ADR 0013).

Each tool returns stored values only; long source lists are cut to the first
LIST_LIMIT entries with their full counts (ADR 0008).
"""

from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any

from langchain.tools import BaseTool, tool
from langchain_core.tools import ToolException

from src.application.ports.outbound.report_questions import (
    GateResult,
    MetricResult,
    ReportSummary,
)
from src.application.use_cases.answer_report_questions import (
    ReportNotFoundError,
    ReportQuestionService,
)
from src.domain.gates.registry import GATE_KINDS
from src.harness.tools.cicd_tools import cicd_tool
from src.harness.tools.common import report_uuid, to_json

LIST_LIMIT = 8
BASELINE_POLICY = (
    "Latest earlier report (or gate run of the same type) whose outcome is "
    "'pass' in this assessment version; failed and unknown reports are skipped."
)


def _expected_errors(function: Callable[..., str]) -> Callable[..., str]:
    """Missing reports go back to the model; other errors propagate."""

    @wraps(function)
    def wrapper(*args, **kwargs) -> str:
        try:
            return function(*args, **kwargs)
        except ReportNotFoundError as error:
            raise ToolException(
                f"{error}. Use the UUID of a report available in storage."
            ) from error

    return wrapper


def build_tools(service: ReportQuestionService) -> list[BaseTool]:
    """The competency-question tools plus the CI/CD tool."""
    comparable = {kind.name: kind.supported for kind in GATE_KINDS.values()}
    return [*build_report_tools(service, comparable), cicd_tool]


def build_report_tools(
    service: ReportQuestionService,
    comparable: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> list[BaseTool]:
    """``comparable`` maps gate type → metric → statistics compare_gate accepts."""

    @tool("describe_report")
    @_expected_errors
    def describe_report(report_id: str) -> str:
        """Describe a report: time, ingestion order, sources, gates, outcome, predecessor."""
        return to_json(_summary(service.describe_report(report_uuid(report_id))))

    @tool("get_previous_report")
    @_expected_errors
    def get_previous_report(report_id: str) -> str:
        """Get the chronologically previous report (failed and unknown included), or history_end."""
        current = report_uuid(report_id)
        previous = service.previous_report(current)
        return to_json(
            {
                "report_id": current,
                "history_end": previous is None,
                "previous_report": None if previous is None else _summary(previous),
            }
        )

    @tool("get_baseline")
    @_expected_errors
    def get_baseline(report_id: str) -> str:
        """Get the report baseline and each gate's baseline, with the selection policy."""
        result = service.baselines(report_uuid(report_id))
        return to_json(
            {
                "selection_policy": BASELINE_POLICY,
                "report_id": result.report_id,
                "baseline_report_id": result.baseline_report_id,
                "gates": [
                    {
                        "gate_type": gate.gate_type,
                        "baseline_report_id": gate.baseline_report_id,
                        "policy_version": gate.policy_version,
                    }
                    for gate in result.gates
                ],
            }
        )

    @tool("compare_gate")
    @_expected_errors
    def compare_gate(
        report_id: str,
        baseline_report_id: str,
        gate_type: str = "performance",
        metric: str = "response_time",
        statistic: str = "p90",
    ) -> str:
        """Compare one metric statistic of a gate between a report and a baseline report.

        Matches measurements by source; returns counts and the largest absolute deltas.
        """
        current = report_uuid(report_id)
        baseline = report_uuid(baseline_report_id, "baseline_report_id")
        statistics = comparable.get(gate_type, {}).get(metric)
        if statistics is None or statistic not in statistics:
            raise ToolException(
                f"Cannot compare {gate_type} {metric}.{statistic}; "
                f"supported: {_supported(comparable)}"
            )
        changes = service.compare_gate(current, baseline, gate_type, metric, statistic)
        with_delta = [change for change in changes if change.delta is not None]
        largest = sorted(
            with_delta, key=lambda change: (-abs(change.delta or 0), change.source)
        )
        return to_json(
            {
                "report_id": current,
                "baseline_report_id": baseline,
                "gate_type": gate_type,
                "metric": metric,
                "statistic": statistic,
                "matched_sources": len(changes),
                "compared_sources": len(with_delta),
                "largest_changes": [
                    {
                        "source": change.source,
                        "unit": change.unit,
                        "baseline": change.baseline,
                        "current": change.current,
                        "delta": change.delta,
                    }
                    for change in largest[:LIST_LIMIT]
                ],
            }
        )

    @tool("explain_outcome")
    @_expected_errors
    def explain_outcome(report_id: str) -> str:
        """Explain a report's outcome: gate and metric outcomes, targets, scores, failing sources."""
        result = service.explain_outcome(report_uuid(report_id))
        return to_json(
            {
                "report_id": result.report.report_id,
                "outcome": result.report.outcome,
                "missing_required_gates": result.missing_gates,
                "gates": [_gate(gate) for gate in result.gates],
            }
        )

    return [
        describe_report,
        get_previous_report,
        get_baseline,
        compare_gate,
        explain_outcome,
    ]


def _summary(report: ReportSummary) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "generated_at": report.generated_at.isoformat(),
        "ingestion_sequence": report.ingestion_sequence,
        "source_paths": report.source_paths,
        "gate_types": report.gate_types,
        "outcome": report.outcome,
        "is_root": report.is_root,
        "previous_report_id": report.previous_report_id,
    }


def _gate(gate: GateResult) -> dict[str, Any]:
    return {
        "gate_type": gate.gate_type,
        "outcome": gate.outcome,
        "metrics": [_metric(metric) for metric in gate.metrics],
    }


def _metric(metric: MetricResult) -> dict[str, Any]:
    missed = [s for s in metric.sources if s.meets_target is False]
    unevaluable = [
        s for s in metric.sources if not s.excluded and s.meets_target is None
    ]
    return {
        "metric": metric.metric,
        "statistic": metric.statistic,
        "target": {"min": metric.min, "max": metric.max, "unit": metric.unit},
        "min_score": metric.min_score,
        "score": metric.score,
        "outcome": metric.outcome,
        "reason": metric.reason,
        "policy_version": metric.policy_version,
        "sources": {
            "total": len(metric.sources),
            "meet_target": sum(s.meets_target is True for s in metric.sources),
            "miss_target": len(missed),
            "excluded": sum(s.excluded for s in metric.sources),
            "not_evaluable": len(unevaluable),
        },
        "missing_target": [
            {"source": s.source, "value": s.value} for s in missed[:LIST_LIMIT]
        ],
        "not_evaluable": [
            {"source": s.source, "reason": s.reason} for s in unevaluable[:LIST_LIMIT]
        ],
    }


def _supported(comparable: Mapping[str, Mapping[str, tuple[str, ...]]]) -> str:
    return "; ".join(
        f"{gate} {metric}.{statistic}"
        for gate, metrics in comparable.items()
        for metric, statistics in metrics.items()
        for statistic in statistics
    )
