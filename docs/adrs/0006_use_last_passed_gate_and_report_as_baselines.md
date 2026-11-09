# 6. Use the latest-passing gate and report as baselines

Date: 2026-10-05

## Status

Accepted

## Context

Gate and release comparisons need trusted references following the separate
gate/report acceptance decisions in
[ADR 0005](0005_separate_gate_and_report_acceptance.md).

## Decision

For the POC:

- A gate uses the latest passing instance of its gate type, even if its
  containing report failed overall.
- A report uses the latest prior passing report: every gate must have passed.

Order reports by the UTC timestamp formed from `generated_at_date` and
`generated_at_time`, with preserved ingestion order breaking ties
deterministically. [ADR 0009](0009_require_complete_report_timestamps.md)
defines timestamp source precedence and validation. Re-ingestion preserves
original values. Candidates must precede the current item in this order;
select the eligible passing candidate with the greatest timestamp, then
latest ingestion order for ties.

The evidence pack identifies current and selected baseline items, their
acceptance results and snapshots, and preserves baseline identifiers.
Report-level evidence includes both reports and their gate outcomes.
Gate-level evidence includes each baseline gate and its source report ID,
even when it differs from the report baseline. This exposes one history hop;
the agent can request an earlier hop using a baseline identifier.

Without a prior passing item of the required kind, baseline comparison cannot
mark an item passing. A report fails to pass if any gate is not explicitly
passing. Absolute acceptance still runs without a baseline; the first
qualifying gate/report establishes its respective baseline for later reports.
Represent missing baselines with null identifiers and an unavailable-comparison
reason, never a fabricated seed.

Chronological predecessor links are separate from passing-baseline links:
they include failed and unknown reports and end with a null predecessor and
`is_root: true`. [ADR 0008](0008_incremental_import_and_history.md) defines
import identity, rejection of backdated additions, and versioned history.

This POC policy replaces the previous-compatible-run or average proposal.
Generated-at timestamps govern ordering; ingestion order only breaks ties.
Future work may consider other baseline policies.

## Alternatives

- **Immediately previous run, passing or failing.** Rejected: failed results
  are not trusted references, and ingestion recency alone is not report recency.
- **Moving or simple average.** Rejected for the POC: the last passing result
  provides a concrete, traceable reference.

## Consequences

Gate baselines advance independently of report baselines; passing gates in
failed reports remain eligible for their gate type. Retain both generated-at
fields and ingestion order. Explicit baseline identifiers make evidence-pack
comparisons reproducible and traceable.
