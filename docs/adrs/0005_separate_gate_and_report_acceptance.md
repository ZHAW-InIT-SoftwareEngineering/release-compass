# 5. Assess gate acceptance separately from report acceptance

Date: 2026-10-05

## Status

Accepted

## Context

A report can contain multiple quality gates. A single report-level result does
not show which gate caused a release to fail, and it limits the detail
available to the agent when explaining the evidence. Gate-level outcomes also
need to remain meaningful when the overall report does not pass.

## Decision

Assess each gate independently using that gate's configured assessment rules
and its own gate baseline. Record the gate result and the evidence used to
reach it.

Acceptance uses absolute configured rules and does not require a prior
baseline. Baseline comparison explains changes; it does not determine
acceptance. Outcomes are explicitly `pass`, `fail`, or `unknown`. A known
failure takes precedence over unknown evidence; otherwise a missing,
duplicate, unsupported, or indeterminate required gate prevents a pass.

Performance scoring follows the provider assessments and weighted aggregation
recorded in [ADR 0007](0007_use_provider_performance_assessments.md).

Assess the report's release result separately. A report passes only when every
gate in it has an explicit passing result. A gate that is missing or has no
determinate passing result does not satisfy this condition.

The evidence returned for a report includes the report-level result and each
gate-level result. For every gate it identifies the current gate and its
baseline gate, including their source report IDs, outcomes, and snapshots. It
also includes the current report and selected baseline report with their gate
outcomes. This gives the agent one complete hop of report history and lets it
request earlier hops by ID when needed. The language model may explain or
aggregate this evidence but does not calculate gate outcomes or infer a
release result.

## Alternatives

- **Use only one report-level result.** Rejected because it hides which gate
  failed and provides less useful diagnostic evidence.
- **Let the language model decide whether gates or the report pass.** Rejected
  because the decision must be reproducible and grounded in configured rules.

## Consequences

The system can explain gate failures independently while still giving one
release-level outcome. Gate-specific rules determine gate outcomes; the
report-level rule is the conjunction of those outcomes. The evidence pack must
preserve report-level and per-gate baseline IDs and the corresponding gate and
report snapshots for one-hop traceability.
