# 7. Reuse provider Performance assessments

Date: 2026-10-07

## Status

Accepted

## Decision

Use explicit `aggregatorSummary.performance_gate.metrics` scores when present.
An incomplete or invalid explicit score is unknown; do not replace it with a
different interpretation. This supports the supplied synthetic fixture while
retaining its score provenance and any differences from underlying metrics.

Without this block, use these supplied penalties:

| Metric | Provider evidence |
| --- | --- |
| Response time | Transaction-health component `local_nfr`, including duration-sensitive violation reasons |
| Throughput | Load-summary status mapped through the report's NFR categorical penalty weights |
| Request outcomes | Transaction-health component `failure_transactions_rate` |
| Transaction NFR status | Aggregate `nfr_compliance.score_nfr`, with its provider weights and evidence |
| CPU and memory | Per-node `metrics_components[metric].local_nfr` |

Convert penalties to scores using `1 - penalty`. Apply the project gate
configuration's `>=` thresholds. Provider targets, thresholds, statuses, and
passing flags remain separately identifiable evidence.

Use supplied transaction/node weights, normalized over included sources.
An explicit equal-transaction policy may supply equal weights when individual
weights are absent; zero-observation sources then receive zero weight.
Record zero-weight exclusions. Missing weighting policies, invalid penalties,
positive-weight unevaluable sources, and empty eligible sets yield unknown.
Throughput's explicit `not_evaluable` flag must not become a passing score.

All six metric outcomes must pass for Performance to pass. Weighted aggregation
can offset individual-source failures; every source is still exposed in the
evidence. No median across categorical statuses is introduced.

The provider's global release score is retained as provenance. It includes
out-of-scope logs/trends and does not determine the project's release result.
The project does not recreate upstream formulas for supplied penalties.

## Consequences

Source normalization retains provider assessments, weights, exclusions, and
reasons alongside the original metric summaries and supporting evidence.
Assessment versions include the project configuration and interpretation-policy
version. Changed configuration/policy creates new immutable evidence packs;
earlier results remain available.
