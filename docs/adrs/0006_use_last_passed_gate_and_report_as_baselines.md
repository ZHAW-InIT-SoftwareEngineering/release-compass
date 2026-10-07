# 6. Use the latest-passing gate and report as baselines

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

- A gate uses the latest passing instance of the same gate type, ordered by
  its containing report's `generated_at_date` and `generated_at_time`. Its
  containing report does not need to have passed overall.
- A report uses the latest prior report that passed, meaning every gate in
  that report passed, ordered by `generated_at_date` and `generated_at_time`.

The two fields together form a UTC timestamp. When an HTML report supplies
`generated_at_date` and `generated_at_time`, ingestion preserves those values.
Until reports supply them, the import configuration provides the date and time
for each report. If neither source provides them, ingestion assigns the
current UTC date and time when the report is first stored. Re-ingesting the
same report must preserve the originally stored values. Reports are ordered by this combined timestamp;
ingestion order breaks ties when timestamps are equal. The application must
preserve ingestion order to resolve ties deterministically. A report without
a complete generated-at date and time is not eligible for automatic baseline
selection and cannot have an automatic baseline selected for it.

Candidates must precede the current item in this report order. The baseline
is the eligible passing candidate with the greatest combined timestamp (and
latest ingestion order when timestamps tie).

The evidence pack identifies the current item and its selected baseline,
includes their acceptance results and snapshots, and preserves the selected
baseline identifiers. At report level, it includes the current and baseline
reports and the gate outcomes in each. At gate level, it includes each gate's
baseline gate and source report ID, even when that source report differs from
the report-level baseline. This exposes one hop of history so the agent can
explain the comparison and use a baseline identifier to request an earlier hop
when needed.

If no previously passing item of the required kind is available, the item
cannot be marked as passing on the basis of a baseline comparison. A report
with any gate that is not explicitly passing does not pass.

Absolute acceptance still runs when no baseline exists. The first qualifying
gate/report establishes its respective baseline for later reports. Missing
baselines are represented by null identifiers with an unavailable-comparison
reason, rather than a fabricated seed.

Chronological predecessor links are separate from passing-baseline links.
They include failed and unknown reports and terminate at a null predecessor
with `is_root: true`. See [ADR 0008](0008_incremental_import_and_history.md)
for import identity, rejection of backdated additions, and versioned history.

This POC policy replaces the earlier proposal to use the previous compatible
run or an average. The combined generated-at timestamp is authoritative for
ordering; ingestion order is used only to break ties. Other baseline policies
may be considered separately for future work.

## Alternatives

- **Use the immediately previous run, whether it passed or failed.** Rejected
  because a failed result should not become the trusted reference for the next
  comparison, and ingestion recency alone does not establish report recency.
- **Use a moving or simple average.** Rejected for the POC because the decision
  is to use the last passing result as a concrete, traceable reference.

## Consequences

Gate baselines can advance independently of report baselines. A passing gate
from an overall-failed report remains eligible for comparisons of that gate
type. Report ingestion must retain both generated-at fields and ingestion
order. The evidence pack must identify the selected baseline explicitly so
comparisons are reproducible and traceable.
