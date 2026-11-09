# 12. Score performance against target ranges

Date: 2026-11-09

## Status

Accepted; supersedes 0007

## Context

Reports no longer carry provider assessments (ADR 0011), so ADR 0007 scores
every metric as unknown. Scoring must use only domain fields.

## Decision

Each gate metric names its measured aggregation (`ai2core:Target`), unit,
and a target range:

```yaml
target: { aggregation: p90, unit: ms, min: null, max: 3000 }
```

- `min` and `max` are both required; `null` means unbounded on that side.
  At least one bound is set and `min <= max`. Bounds are inclusive.
- Current metrics are one-sided: response time and failure rate have only
  `max`, throughput only `min`. Two-sided ranges are for future metrics such
  as CPU usage, where both overload and idle capacity are findings.
- Response time and request outcomes are scored per transaction: a
  transaction meets its target or not, weighted by its request count. The
  score is the share of requests in transactions meeting the target.
- Throughput is scored once for the overall run, since per-transaction
  throughput reflects the load mix rather than system quality.
- A missing value or a unit differing from the target's makes the metric
  unknown; it never passes. Zero-request transactions are excluded and
  recorded.
- Each metric passes when its score is at least its configured `score`.

## Alternatives

- **Overall values only.** Rejected: high-volume transactions hide slow or
  failing low-volume ones.
- **Unweighted transaction share.** Rejected: a health check would count as
  much as the busiest business transaction.
- **Separate lower/upper target types.** Rejected: one range covers both.

## Consequences

Any source mapped to the domain model is assessable. Per-transaction results
stay in the evidence, so failing transactions can be named.

Scoring is gate-agnostic (`src/domain/scoring.py`); a gate only supplies
its measurements and supported metrics. Adding a metric touches only the
gate's measurements and its target configuration.
