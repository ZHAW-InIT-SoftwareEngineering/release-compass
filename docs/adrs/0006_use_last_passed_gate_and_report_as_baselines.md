# 6. Use the last passed gate and report as baselines

Date: 2026-10-05

## Status

Accepted

## Context

Gate comparisons need a trusted reference for each gate, while release
comparisons need a trusted reference for the report as a whole. These references
must follow the separate gate and report acceptance decisions in
[ADR 0005](0005_separate_gate_and_report_acceptance.md).

## Decision

For the POC, select baselines as follows:

- A gate uses the most recently recorded passing instance of the same gate
  type. Its containing report does not need to have passed overall.
- A report uses the most recently recorded report that passed, meaning every
  gate in that report passed.

“Most recently recorded” means ingestion order. The evidence pack identifies
the current item and its selected baseline, includes their acceptance results
and snapshots, and preserves the selected baseline identifiers. At report
level, it includes the current and baseline reports and the gate outcomes in
each. At gate level, it includes each gate's baseline gate and source report
ID, even when that source report differs from the report-level baseline. This
exposes one hop of history so the agent can explain the comparison and use a
baseline identifier to request an earlier hop when needed.

If no previously passing item of the required kind is available, the item
cannot be marked as passing on the basis of a baseline comparison. A report
with any gate that is not explicitly passing does not pass.

This POC policy replaces the earlier proposal to use the previous compatible
run or an average. Other baseline policies may be considered separately for
future work.

## Alternatives

- **Use the immediately previous run, whether it passed or failed.** Rejected
  because a failed result should not become the trusted reference for the next
  comparison.
- **Use a moving or simple average.** Rejected for the POC because the decision
  is to use the last passing result as a concrete, traceable reference.

## Consequences

Gate baselines can advance independently of report baselines. A passing gate
from an overall-failed report remains eligible for comparisons of that gate
type. The evidence pack must identify the selected baseline explicitly so
comparisons are reproducible and traceable.
