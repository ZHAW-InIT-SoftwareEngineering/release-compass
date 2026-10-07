"""Interpret provider assessments without recreating upstream calculations."""

from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Literal

from src.domain.gates.gate import Gate
from src.domain.gates.performance.performance_gate import PerformanceGate

Outcome = Literal["pass", "fail", "unknown"]
POLICY_VERSION = "provider-assessments-v1"
METRICS = (
    "response_time",
    "throughput",
    "request_outcomes",
    "transaction_nfr_status",
    "cpu",
    "memory",
)


@dataclass(frozen=True)
class SourceAssessment:
    name: str
    source: str
    penalty: float | None
    weight: float | None
    excluded: bool = False
    reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricAcceptance:
    outcome: Outcome
    score: float | None
    threshold: float
    source: str
    reason: str | None = None
    sources: list[SourceAssessment] = field(default_factory=list)
    provider_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateAcceptance:
    outcome: Outcome
    metrics: dict[str, MetricAcceptance] = field(default_factory=dict)
    reason: str | None = None


@dataclass(frozen=True)
class GateDefinition:
    gate_type: type[Gate]
    assess: Callable[[Gate], GateAcceptance]
    compare: Callable[[Gate, Gate | None], dict[str, Any]]
    policy_version: str


def combine_outcomes(outcomes: list[Outcome]) -> Outcome:
    if "fail" in outcomes:
        return "fail"
    return (
        "pass" if outcomes and all(value == "pass" for value in outcomes) else "unknown"
    )


def compare_acceptance_scores(
    current: GateAcceptance,
    baseline: GateAcceptance | None,
) -> dict[str, Any]:
    values = {}
    for name, metric in current.metrics.items():
        prior = baseline.metrics.get(name) if baseline else None
        delta = (
            metric.score - prior.score
            if metric.score is not None
            and prior is not None
            and prior.score is not None
            else None
        )
        reason = (
            "No prior passing baseline"
            if baseline is None
            else "Missing current or baseline score"
            if delta is None
            else None
        )
        values[name] = {
            "current": metric.score,
            "baseline": prior.score if prior else None,
            "unit": "score_0_to_1",
            "absolute_delta": delta,
            "relative_delta_percent": (
                delta / abs(prior.score) * 100
                if delta is not None
                and prior
                and prior.score is not None
                and prior.score != 0
                else None
            ),
            "current_source": metric.source,
            "baseline_source": prior.source if prior else None,
            "unavailable_reason": reason,
            "relative_unavailable_reason": reason
            or ("Zero baseline" if prior and prior.score == 0 else None),
        }
    return values


def _number(value: Any, *, bounded: bool = True) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not isfinite(number) or number < 0 or (bounded and number > 1):
        return None
    return number


def _accept(
    score: float | None,
    threshold: float,
    source: str,
    *,
    reason: str | None = None,
    sources: list[SourceAssessment] | None = None,
    evidence: dict[str, Any] | None = None,
) -> MetricAcceptance:
    outcome: Outcome = (
        "unknown" if score is None else ("pass" if score >= threshold else "fail")
    )
    return MetricAcceptance(
        outcome,
        score,
        threshold,
        source,
        reason if score is None else None,
        sources or [],
        evidence or {},
    )


def _aggregate(
    sources: list[SourceAssessment],
    threshold: float,
    source: str,
) -> MetricAcceptance:
    included = [item for item in sources if not item.excluded]
    if not included:
        return _accept(
            None, threshold, source, reason="No eligible sources", sources=sources
        )
    if any(item.penalty is None or item.weight is None for item in included):
        return _accept(
            None,
            threshold,
            source,
            reason="An included source lacks an evaluable penalty or weighting policy",
            sources=sources,
        )
    total_weight = sum(item.weight or 0 for item in included)
    if total_weight <= 0:
        return _accept(
            None, threshold, source, reason="No positive source weight", sources=sources
        )
    penalty = (
        sum((item.penalty or 0) * (item.weight or 0) for item in included)
        / total_weight
    )
    return _accept(1 - penalty, threshold, source, sources=sources)


def assess_performance(
    gate: PerformanceGate,
    thresholds: dict[str, float],
) -> GateAcceptance:
    provider: dict[str, Any] = gate.provider_assessments
    explicit = provider.get("performance_gate")
    results: dict[str, MetricAcceptance] = {}
    if explicit is not None:
        metrics = explicit.get("metrics", {}) if isinstance(explicit, dict) else {}
        for name in METRICS:
            evidence = metrics.get(name, {})
            score = (
                _number(evidence.get("score")) if isinstance(evidence, dict) else None
            )
            results[name] = _accept(
                score,
                thresholds[name],
                f"aggregatorSummary.performance_gate.metrics.{name}",
                reason="Missing or invalid explicit metric score",
                evidence=evidence if isinstance(evidence, dict) else {},
            )
        return GateAcceptance(
            combine_outcomes([item.outcome for item in results.values()]), results
        )

    health = provider.get("transaction_health", {})
    transactions = health.get("per_transaction", {})
    aggregation = health.get("weights", {}).get("transaction_aggregation", {})
    nfr = provider.get("nfr_compliance", {})
    status_weights = nfr.get("weights", {})
    status_labels = {
        code: label for label, code in provider.get("statuses", {}).items()
    }
    for metric in ("response_time", "throughput", "request_outcomes"):
        sources = []
        for name in sorted(gate.transactions.keys() | transactions.keys()):
            item = transactions.get(name, {})
            weight = _number(item.get("transaction_weight"), bounded=False)
            weight_source = item.get("transaction_weight_source")
            if (
                weight is None
                and "transaction_weight" not in item
                and aggregation.get("mode") == "equal"
            ):
                weight = 0.0 if item.get("zero_observation") is True else 1.0
                weight_source = "transaction_aggregation.mode=equal"
            # Zero weight alone is sufficient only when supplied by the provider.
            excluded = weight == 0
            tx = gate.transactions.get(name)
            evidence: dict[str, Any] = {
                "provider": item,
                "weight_source": weight_source,
            }
            if metric == "throughput":
                throughput = tx.throughput if tx else None
                details = (
                    throughput.supporting_evidence.get("load_nfr_details", {})
                    if throughput
                    else {}
                )
                status = throughput.assessment.status if throughput else None
                label = status_labels.get(status)
                penalty = _number(status_weights.get(label))
                if label == "green" and penalty is None:
                    penalty = _number(
                        health.get("weights", {}).get("status", {}).get(label)
                    )
                if not throughput or (
                    isinstance(details, dict) and details.get("not_evaluable") is True
                ):
                    penalty = None
                if throughput and throughput.observation_count == 0:
                    penalty = None
                source = f"loadRuleBased[{name}].summary.status"
                evidence.update(
                    {
                        "status": status,
                        "status_label": label,
                        "load_nfr_details": details,
                    }
                )
            else:
                component = (
                    "local_nfr"
                    if metric == "response_time"
                    else "failure_transactions_rate"
                )
                penalty = _number(item.get("components", {}).get(component))
                if not tx or (
                    metric == "response_time"
                    and (
                        tx.response_time is None
                        or tx.response_time.observation_count <= 0
                    )
                ):
                    penalty = None
                if metric == "request_outcomes" and (
                    not tx
                    or tx.request_outcomes is None
                    or tx.request_outcomes.total_requests <= 0
                ):
                    penalty = None
                source = f"aggregatorSummary.overall_score.transaction_health.per_transaction[{name}].components.{component}"
            sources.append(
                SourceAssessment(
                    name,
                    source,
                    penalty,
                    weight,
                    excluded,
                    "Provider excluded this source"
                    if excluded
                    else (
                        "Missing or unevaluable provider assessment"
                        if penalty is None or weight is None
                        else None
                    ),
                    evidence,
                )
            )
        results[metric] = _aggregate(
            sources,
            thresholds[metric],
            "aggregatorSummary.overall_score.transaction_health",
        )

    nfr_penalty = _number(nfr.get("score_nfr"))
    if nfr.get("has_data") is False:
        nfr_penalty = None
    results["transaction_nfr_status"] = _accept(
        1 - nfr_penalty if nfr_penalty is not None else None,
        thresholds["transaction_nfr_status"],
        "aggregatorSummary.overall_score.nfr_compliance.score_nfr",
        reason="Missing or invalid supplied NFR penalty",
        evidence=nfr,
    )
    nodes = provider.get("infrastructure_health", {}).get("per_node", {})
    for metric in ("cpu", "memory"):
        sources = []
        components = getattr(gate, f"{metric}_components")
        for name in sorted(components.keys() | nodes.keys()):
            item = nodes.get(name, {})
            weight = _number(item.get("node_weight"), bounded=False)
            penalty = _number(
                item.get("metrics_components", {}).get(metric, {}).get("local_nfr")
            )
            if (
                name not in components
                or components[name].summary.observation_count <= 0
            ):
                penalty = None
            excluded = weight == 0
            sources.append(
                SourceAssessment(
                    name,
                    f"aggregatorSummary.overall_score.infrastructure_health.per_node[{name}].metrics_components.{metric}.local_nfr",
                    penalty,
                    weight,
                    excluded,
                    "Provider excluded this source"
                    if excluded
                    else (
                        "Missing or unevaluable provider assessment"
                        if penalty is None or weight is None
                        else None
                    ),
                    item,
                )
            )
        results[metric] = _aggregate(
            sources,
            thresholds[metric],
            "aggregatorSummary.overall_score.infrastructure_health",
        )
    return GateAcceptance(
        combine_outcomes([item.outcome for item in results.values()]), results
    )
