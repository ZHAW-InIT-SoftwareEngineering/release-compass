"""Read the embedded performance data from an AI-SQUARE HTML report."""

import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from src.domain.gates.performance.performance_gate import (
    MetricAssessment,
    MetricSummary,
    PerformanceGate,
    RequestOutcomes,
    ResourceMetric,
    ResponseTimeMetric,
    ThresholdConfiguration,
    ThroughputMetric,
    TransactionPerformance,
    ViolationPeriod,
)
from src.domain.report import Report


class _ReportDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_report_data = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__report_data__":
            self.in_report_data = True

    def handle_data(self, data):
        if self.in_report_data:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_report_data = False


def _time_range(timeseries):
    timestamps = [point["timestamp"] for point in timeseries if "timestamp" in point]
    if not timestamps:
        return None, None
    return tuple(
        datetime.fromtimestamp(timestamp / 1000, tz=UTC).isoformat()
        for timestamp in (min(timestamps), max(timestamps))
    )


def _assessment(summary):
    thresholds = summary.get("status_thresholds")
    return MetricAssessment(
        status=summary.get("status"),
        threshold_configuration=(
            ThresholdConfiguration(
                amber_violation_rate_percent=thresholds.get("amber_violation_rate_pct"),
                red_violation_rate_percent=thresholds.get("red_violation_rate_pct"),
                amber_source=thresholds.get("amber_source"),
                red_source=thresholds.get("red_source"),
            )
            if thresholds
            else None
        ),
        status_reason=summary.get("status_reason") or summary.get("load_nfr_reason"),
    )


def _summary(summary, timeseries=(), extra_evidence=None):
    start_time, end_time = _time_range(timeseries)
    evidence = {
        key: summary[key]
        for key in (
            "p0_value",
            "p25_value",
            "p75_value",
            "std",
            "coef",
            "p_value",
            "ci_lower",
            "ci_upper",
            "r_squared_adj",
        )
        if key in summary
    }
    if timeseries:
        evidence["timeseries"] = timeseries
    if extra_evidence:
        evidence.update(extra_evidence)
    return MetricSummary(
        source=summary["source"],
        unit=summary["units"],
        observation_count=summary["num_obs"],
        duration_seconds=summary["duration_sec"],
        start_time=start_time,
        end_time=end_time,
        mean=summary.get("mean"),
        p50=summary.get("p50_value"),
        p90=summary.get("p90_value"),
        maximum=summary.get("p100_value"),
        target_nfr=summary.get("target_nfr"),
        violation_count=summary.get("total_nfr_violations"),
        violation_rate_percent=summary.get("total_violation_perc"),
        violation_periods=[
            ViolationPeriod(
                start_time=period["start_time"],
                end_time=period["end_time"],
                duration_seconds=period["duration_sec"],
                mean_value=period.get("mean_value"),
                max_value=period.get("max_value"),
                violation_type=period.get("violation_type"),
            )
            for period in summary.get("nfr_violation_periods", ())
        ],
        supporting_evidence=evidence,
    )


def _response_time(summary, timeseries=(), extra_evidence=None):
    return ResponseTimeMetric(
        **vars(_summary(summary, timeseries, extra_evidence)),
        assessment=_assessment(summary),
    )


def _outcomes(summary):
    failures = summary.get("transaction_failure")
    if failures is None:
        return None
    total = failures["total_requests"]
    failed = failures["failed_requests"]
    return RequestOutcomes(
        total_requests=total,
        failed_requests=failed,
        passed_requests=total - failed,
        failure_rate_percent=failures["failure_rate_pct"],
        http_code_histogram=failures.get("http_code_hist", {}),
    )


def _throughput(summary, timeseries=(), extra_evidence=None):
    start_time, end_time = _time_range(timeseries)
    evidence = {
        key: summary[key]
        for key in (
            "load_nfr_details",
            "coef",
            "p_value",
            "ci_lower",
            "ci_upper",
            "r_squared_adj",
        )
        if key in summary
    }
    if timeseries:
        evidence["timeseries"] = timeseries
    if extra_evidence:
        evidence.update(extra_evidence)
    return ThroughputMetric(
        source=summary["source"],
        unit=summary.get("units", "req/s"),
        observation_count=summary.get(
            "num_obs", summary.get("n_data_points", len(timeseries))
        ),
        target_nfr=summary.get("target_nfr"),
        tps=summary.get("tps"),
        mean=summary.get("mean"),
        violation_count=summary.get("total_nfr_violations"),
        violation_rate_percent=summary.get("total_violation_perc"),
        duration_seconds=summary.get("duration_sec"),
        start_time=start_time,
        end_time=end_time,
        assessment=_assessment(summary),
        supporting_evidence=evidence,
    )


def _resource(summary, timeseries=(), linear_trend=()):
    return ResourceMetric(
        summary=_summary(summary, timeseries),
        assessment=_assessment(summary),
        timeseries=list(timeseries),
        linear_trend=list(linear_trend),
    )


class HTMLReport:
    def ingest(self, report_path: str | Path) -> Report:
        """Normalize the report at ``report_path`` into performance evidence."""

        path = Path(report_path)
        parser = _ReportDataParser()
        parser.feed(path.read_text(encoding="utf-8"))
        if not parser.chunks:
            raise ValueError(f"No __report_data__ script found in {path}")

        data = json.loads("".join(parser.chunks))
        apm = data["aggregatorSummary"]["metrics"]["apm"]
        performance_gate = PerformanceGate()
        performance_gate.response_time = _response_time(
            apm["response_time"], apm["response_time"].get("timeseries") or ()
        )
        performance_gate.throughput = _throughput(
            apm["load"], apm["load"].get("timeseries") or ()
        )
        performance_gate.request_outcomes = _outcomes(apm["response_time"])

        transactions = {}
        for item in data.get("rtRuleBased", ()):
            name = item["pageName"]
            summary = item["summary"]
            transactions[name] = TransactionPerformance(
                name=name,
                response_time=_response_time(
                    summary,
                    item.get("timeseries") or (),
                    {
                        key: item[key]
                        for key in ("per_minute", "linear_trend_timeseries")
                        if key in item
                    },
                ),
                request_outcomes=_outcomes(summary),
            )
        for item in data.get("loadRuleBased", ()):
            name = item["pageName"]
            transaction = transactions.setdefault(
                name, TransactionPerformance(name=name, response_time=None)
            )
            transaction.throughput = _throughput(
                item["summary"],
                item.get("timeseries") or (),
                {
                    key: item[key]
                    for key in ("per_minute", "linear_trend_timeseries")
                    if key in item
                },
            )
        nfr = data["aggregatorSummary"]["overall_score"]["nfr_compliance"]["metrics"][
            "apm"
        ]
        for name, status in nfr.get("per_transaction", {}).items():
            transaction = transactions.setdefault(
                name, TransactionPerformance(name=name, response_time=None)
            )
            transaction.nfr_status = status.get("status")
        performance_gate.transactions = transactions

        for metric_name, component_key in (
            ("cpu", "cpuComponents"),
            ("memory", "ramComponents"),
        ):
            components = {}
            for item in data.get(component_key, ()):
                metric = _resource(
                    item["summary"],
                    item.get("timeseries") or (),
                    item.get("linear_trend") or (),
                )
                components[metric.summary.source] = metric
            setattr(performance_gate, f"{metric_name}_components", components)
            overall = _resource(apm[metric_name])
            ranges = [component.summary for component in components.values()]
            starts = [value.start_time for value in ranges if value.start_time]
            ends = [value.end_time for value in ranges if value.end_time]
            overall.summary.start_time = min(starts) if starts else None
            overall.summary.end_time = max(ends) if ends else None
            setattr(performance_gate, metric_name, overall)

        return Report(
            source_path=str(path),
            generated_at_date=data.get("generated_at_date"),
            generated_at_time=data.get("generated_at_time"),
            gates=[performance_gate],
        )
