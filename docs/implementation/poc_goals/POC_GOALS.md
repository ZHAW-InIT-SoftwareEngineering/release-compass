# POC Goals and Scope

## Purpose

The proof of concept assesses one quality gate: **Performance**. Given a
current test run and a selected baseline, it produces deterministic,
traceable evidence that a conversational agent can explain to a user. The
reference input is [the example report](../../example_reports/report.html).

This document defines the POC contract; it does not prescribe production
threshold values. Thresholds remain gate configuration and must be retained in
the returned evidence.

## In-scope performance metrics

All metric values retain the report's source, unit, observation count, and
time range. They are assessed both for the overall run where available and at
the granularity offered by the report: transaction for response time,
throughput, and failures; service/component for CPU and memory.

| Metric | Report data | Values compared | Unit and granularity |
| --- | --- | --- | --- |
| Response time | `aggregatorSummary.metrics.apm.response_time` and `rtRuleBased[].summary` | Mean, p50, p90, and maximum; NFR-violation rate and threshold configuration | Milliseconds; overall and per transaction |
| Throughput | `aggregatorSummary.metrics.apm.load` and `loadRuleBased[].summary` | TPS (`tps` / `mean`), target-NFR result, and violation rate when configured | Requests per second; overall and per transaction |
| Request outcomes | `transaction_failure` within response-time summaries | Total requests, passed requests (`total_requests - failed_requests`), failed requests, failure rate, and HTTP-code histogram | Count and percent; overall and per transaction |
| Transaction NFR status | `aggregatorSummary.overall_score.nfr_compliance.metrics.apm.per_transaction[transaction].status` | Categorical Red, Amber, or Green assessment | Per transaction; `red = 0`, `amber = 1`, `green = 2`, using `dictionnaries.statuses` |
| CPU usage | `aggregatorSummary.metrics.apm.cpu` and `cpuComponents[].summary` | Mean, p50, p90, and maximum; NFR-violation rate and status when configured | The report's supplied `cores` unit; overall and per service/component |
| Memory usage | `aggregatorSummary.metrics.apm.memory` and `ramComponents[].summary` | Mean, p50, p90, and maximum; NFR-violation rate and status when configured | Bytes; overall and per service/component |

The report also contains time series, trend/statistical fields, NFR violation
periods, and confidence-related values. The POC preserves these as supporting
evidence and provenance; it does not use them as additional gate metrics or
derive a new score from them.

The **Transaction NFR status** is a categorical assessment of NFR compliance,
not request pass/fail. It must be presented independently of the
request-outcome counts.

## Assessment output

For every assessed metric and source, the evidence pack contains:

- the current value and selected baseline value;
- absolute and relative delta, where a relative delta is meaningful;
- the configured target/threshold and resulting report status, if supplied;
- observation count, time range, unit, metric source, and run identifiers; and
- the relevant supporting evidence, such as violation periods or HTTP-code
  distribution.

The deterministic analysis layer creates this pack. The LLM may explain its
contents but must not calculate metrics, choose a different baseline, or infer
an unsupported release decision.

## Scope decisions

The following decisions are in effect for the POC:

| Decision | POC consequence |
| --- | --- |
| Performance is the only implemented quality gate. | Security, Functional Suitability, Build Quality, logs, and JVM data are out of scope for assessment. |
| Gate logic is metric-domain specific, but the architecture is gate-extensible. | A later gate supplies its own report adapter, metric definitions, baseline policy, comparison rules, and configuration without changing the client or agent contract. |
| Analysis is deterministic and evidence-first. | Report normalization, baseline selection, comparison, threshold evaluation, and evidence-pack construction are outside the LLM. |
| The LLM is exchangeable. | The POC must retain a provider/model boundary so self-hosted and frontier models can be evaluated without changing gate logic. |
| The project controls its framework and hosting choices. | No external managed decision engine is required by this POC. |
| The report is the POC data contract. | The implementation consumes the named report fields and preserves their units; it does not reinterpret CPU as a percentage or memory as MB before analysis. |

The report's `overall_score` is excluded from the POC decision because its
calculation is not defined here. The POC instead exposes the underlying
metrics and their configured statuses.

## Tool scope

The architecture diagram shows the POC request as
`compare_performance(run_id)`: the analysis selects the configured baseline
and returns a structured evidence pack. A separately callable
`get_performance_evidence(run_id)` remains a proposed convenience tool, not a
required POC capability; `compare_performance` already returns the evidence
needed for an explanation.

## Open decisions and explicit non-goals

These items are intentionally not decided by this document:

- **Baseline policy:** previous compatible run, moving average, or simple
  average still needs to be selected and configured.
- **Trigger model:** the POC supports a user-initiated comparison; background
  or event-driven audits and persistent audit backlogs are not in scope.
- **Threshold ownership and values:** use the values supplied by the report or
  gate configuration; do not hard-code new thresholds in the POC.
- **Metric-source validation:** the report labels CPU as `cores` and memory as
  `bytes`. Their collection point and semantics must be verified with the data
  provider before production use.
