"""Performance-specific provider assessment rules."""

from math import isfinite
from typing import Any

from src.domain.assessment import (
    GateAcceptance,
    MetricAcceptance,
    Outcome,
    SourceAssessment,
    combine_outcomes,
)
from src.domain.gates.performance.performance_gate import (
    PerformanceGate,
    TransactionPerformance,
)

POLICY_VERSION = "provider-assessments-v1"
METRICS = (
    "response_time",
    "throughput",
    "request_outcomes",
    "transaction_nfr_status",
    "cpu",
    "memory",
)


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


def _combine_metric_results(results: dict[str, MetricAcceptance]) -> GateAcceptance:
    return GateAcceptance(
        combine_outcomes([item.outcome for item in results.values()]), results
    )


def _status_penalty(
    status: int | None,
    status_definitions: dict[str, int],
    status_weights: dict[str, Any],
    fallback_weights: dict[str, Any],
) -> tuple[float | None, str | None]:
    """Resolve a provider status code to its configured penalty and label."""
    label = next(
        (label for label, code in status_definitions.items() if code == status), None
    )
    if label is None:
        return None, None

    penalty = _number(status_weights.get(label))
    if label == "green" and penalty is None:
        penalty = _number(fallback_weights.get(label))
    return penalty, label


def _assess_explicit_performance_metrics(
    explicit: Any,
    thresholds: dict[str, float],
) -> GateAcceptance:
    metrics = explicit.get("metrics", {}) if isinstance(explicit, dict) else {}
    results = {}
    for name in METRICS:
        evidence = metrics.get(name, {})
        score = _number(evidence.get("score")) if isinstance(evidence, dict) else None
        results[name] = _accept(
            score,
            thresholds[name],
            f"aggregatorSummary.performance_gate.metrics.{name}",
            reason="Missing or invalid explicit metric score",
            evidence=evidence if isinstance(evidence, dict) else {},
        )
    return _combine_metric_results(results)


def _transaction_weight(
    item: dict[str, Any], aggregation: dict[str, Any]
) -> tuple[float | None, str | None, bool]:
    weight = _number(item.get("transaction_weight"), bounded=False)
    weight_source = item.get("transaction_weight_source")
    if (
        weight is None
        and "transaction_weight" not in item
        and aggregation.get("mode") == "equal"
    ):
        weight = 0.0 if item.get("zero_observation") is True else 1.0
        weight_source = "transaction_aggregation.mode=equal"
    # A zero weight excludes a source only when the provider supplied it.
    return weight, weight_source, weight == 0


def _throughput_source(
    transaction: TransactionPerformance | None,
    status_definitions: dict[str, int],
    status_weights: dict[str, Any],
    fallback_status_weights: dict[str, Any],
    name: str,
) -> tuple[float | None, str, dict[str, Any]]:
    throughput = transaction.throughput if transaction else None
    details = (
        throughput.supporting_evidence.get("load_nfr_details", {}) if throughput else {}
    )
    status = throughput.assessment.status if throughput else None
    penalty, label = _status_penalty(
        status, status_definitions, status_weights, fallback_status_weights
    )
    if not throughput or (
        isinstance(details, dict) and details.get("not_evaluable") is True
    ):
        penalty = None
    if throughput and throughput.observation_count == 0:
        penalty = None
    return (
        penalty,
        f"loadRuleBased[{name}].summary.status",
        {
            "status": status,
            "status_label": label,
            "load_nfr_details": details,
        },
    )


def _response_time_source(
    item: dict[str, Any],
    transaction: TransactionPerformance | None,
    name: str,
) -> tuple[float | None, str, dict[str, Any]]:
    penalty = _number(item.get("components", {}).get("local_nfr"))
    if (
        transaction is None
        or transaction.response_time is None
        or transaction.response_time.observation_count <= 0
    ):
        penalty = None
    source = (
        "aggregatorSummary.overall_score.transaction_health."
        f"per_transaction[{name}].components.local_nfr"
    )
    return penalty, source, {}


def _request_outcomes_source(
    item: dict[str, Any],
    transaction: TransactionPerformance | None,
    name: str,
) -> tuple[float | None, str, dict[str, Any]]:
    penalty = _number(item.get("components", {}).get("failure_transactions_rate"))
    if (
        transaction is None
        or transaction.request_outcomes is None
        or transaction.request_outcomes.total_requests <= 0
    ):
        penalty = None
    source = (
        "aggregatorSummary.overall_score.transaction_health."
        f"per_transaction[{name}].components.failure_transactions_rate"
    )
    return penalty, source, {}


def _source_reason(
    excluded: bool,
    penalty: float | None,
    weight: float | None,
) -> str | None:
    if excluded:
        return "Provider excluded this source"
    if penalty is None or weight is None:
        return "Missing or unevaluable provider assessment"
    return None


def _transaction_source(
    gate: PerformanceGate,
    provider_transactions: dict[str, Any],
    aggregation: dict[str, Any],
    status_weights: dict[str, Any],
    fallback_status_weights: dict[str, Any],
    status_definitions: dict[str, int],
    metric: str,
    name: str,
) -> SourceAssessment:
    item = provider_transactions.get(name, {})
    weight, weight_source, excluded = _transaction_weight(item, aggregation)
    transaction = gate.transactions.get(name)
    if metric == "throughput":
        metric_assessment = _throughput_source(
            transaction,
            status_definitions,
            status_weights,
            fallback_status_weights,
            name,
        )
    elif metric == "response_time":
        metric_assessment = _response_time_source(item, transaction, name)
    elif metric == "request_outcomes":
        metric_assessment = _request_outcomes_source(item, transaction, name)
    else:
        raise ValueError(f"Unsupported transaction metric: {metric}")
    penalty, source, evidence = metric_assessment

    return SourceAssessment(
        name,
        source,
        penalty,
        weight,
        excluded,
        _source_reason(excluded, penalty, weight),
        {"provider": item, "weight_source": weight_source, **evidence},
    )


def _assess_transaction_metrics(
    gate: PerformanceGate,
    provider: dict[str, Any],
    thresholds: dict[str, float],
) -> dict[str, MetricAcceptance]:
    health = provider.get("transaction_health", {})
    transactions = health.get("per_transaction", {})
    aggregation = health.get("weights", {}).get("transaction_aggregation", {})
    nfr = provider.get("nfr_compliance", {})
    status_weights = nfr.get("weights", {})
    status_definitions = provider.get("statuses", {})
    results = {}
    for metric in ("response_time", "throughput", "request_outcomes"):
        sources = [
            _transaction_source(
                gate,
                transactions,
                aggregation,
                status_weights,
                health.get("weights", {}).get("status", {}),
                status_definitions,
                metric,
                name,
            )
            for name in sorted(gate.transactions.keys() | transactions.keys())
        ]
        results[metric] = _aggregate(
            sources,
            thresholds[metric],
            "aggregatorSummary.overall_score.transaction_health",
        )
    return results


def _assess_transaction_nfr(
    provider: dict[str, Any], thresholds: dict[str, float]
) -> MetricAcceptance:
    nfr = provider.get("nfr_compliance", {})
    penalty = _number(nfr.get("score_nfr"))
    if nfr.get("has_data") is False:
        penalty = None
    return _accept(
        1 - penalty if penalty is not None else None,
        thresholds["transaction_nfr_status"],
        "aggregatorSummary.overall_score.nfr_compliance.score_nfr",
        reason="Missing or invalid supplied NFR penalty",
        evidence=nfr,
    )


def _assess_infrastructure_metrics(
    gate: PerformanceGate,
    provider: dict[str, Any],
    thresholds: dict[str, float],
) -> dict[str, MetricAcceptance]:
    nodes = provider.get("infrastructure_health", {}).get("per_node", {})
    results = {}
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
    return results


def assess_performance(
    gate: PerformanceGate,
    thresholds: dict[str, float],
) -> GateAcceptance:
    """Apply supplied Performance evidence, grouped by its evidence source."""
    provider: dict[str, Any] = gate.provider_assessments
    explicit = provider.get("performance_gate")
    if explicit is not None:
        return _assess_explicit_performance_metrics(explicit, thresholds)

    results = _assess_transaction_metrics(gate, provider, thresholds)
    results["transaction_nfr_status"] = _assess_transaction_nfr(provider, thresholds)
    results.update(_assess_infrastructure_metrics(gate, provider, thresholds))
    return _combine_metric_results(results)
