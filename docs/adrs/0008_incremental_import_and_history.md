# 8. Import once and expose chronological evidence history

Date: 2026-10-07

## Status

Accepted

## Decision

An application's import use case owns report import; the entry point only
loads configuration and wires services. SHA-256 of HTML bytes identifies a
source report. Identical bytes reuse the stored UUID, generated-at fields, and
ingestion sequence, including after renaming. Record source-path aliases.
Changed bytes are a new source report.

Use complete HTML timestamps first and complete configured timestamps second.
Reject partial timestamps and reports with no complete timestamp from either
source. Order by
generated-at UTC timestamp and persistent ingestion sequence; configured order
breaks ties within a new batch. Sort the initial batch chronologically.

Reject new sources older than the latest stored report. Validate a batch
before any source or alias writes and commit its changes atomically.
Repeat imports bypass this rule because their stored timestamps are unchanged.
Imported and assessed source snapshots cannot be overwritten.

Acceptance and evidence preparation process stored reports in chronological
order. Registered gate definitions own gate-specific assessment/comparison;
the shared client and history flow do not calculate gate rules.

Evidence packs contain current and passing-baseline snapshots, separate
per-gate source baselines, acceptance results, unit-aware deltas, configuration,
and previous report/evidence-pack identifiers. Snapshots are shallow: they do
not recursively embed predecessor evidence packs. Root reports have a null
predecessor and `is_root: true`.

Expose `compare_performance(report_id)` for deterministic evidence and
`get_previous_report(report_id)` for the predecessor's enriched pack. Root
traversal returns `history_end: true` and no predecessor. Bind a chat session
to one assessment version so traversal does not mix policies/configurations.

Full supporting series remain in persisted packs. Tool responses contain
summary evidence, violation periods, HTTP histograms, and explicit pack/path
references for series and bucket/window collections instead of repeating
all observations in model context.

Long violation-period collections include the first eight periods and a full
pack/path reference. Their complete contents remain in the persisted pack.

## Consequences

One report is sufficient to assess acceptance and start chat, even without a
passing baseline. Report history includes nonpassing reports independently of
baseline history. Changing acceptance configuration rebuilds history under a
new version without editing previously stored packs. No new package is needed.

## Alternatives

- **Identify reports by path or modification time.** Rejected because renames
  and filesystem metadata do not reliably indicate content identity; hash the
  HTML bytes so identical content reuses its report.
- **Accept backdated additions and rebuild the existing order.** Rejected
  because that would change established predecessor and baseline links;
  validate a batch atomically and reject new reports older than stored history.
- **Embed the full prior history in every pack or let the model select a
  baseline.** Rejected because recursive packs duplicate history and model
  selection is nondeterministic; persist shallow references and select
  baselines in the assessment service.
