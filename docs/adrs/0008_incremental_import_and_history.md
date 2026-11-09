# 8. Import once and expose chronological evidence history

Date: 2026-10-07

## Status

Accepted

## Decision

The import use case owns imports; the entry point loads
configuration and wires services. SHA-256 of HTML bytes identifies sources.
Identical bytes reuse stored UUIDs, generated-at fields, and ingestion sequences,
even after renaming; record source-path aliases. Changed bytes are new sources.

Prefer complete HTML timestamps, then complete configured timestamps. Reject
partial timestamps and reports lacking complete timestamps from either source.
Order by generated-at UTC timestamp and persistent ingestion sequence;
configured order breaks batch ties. Sort initial batches
chronologically.

Reject new sources older than the latest stored report. Validate batches before
any source/alias writes; commit atomically. Repeat imports bypass this rule,
retaining stored timestamps. Never overwrite imported or assessed snapshots.

Acceptance and evidence preparation process stored reports chronologically.
Registered gate definitions own gate-specific assessment/comparison; the shared
client and history flow do not calculate gate rules.

Evidence packs contain current and passing-baseline snapshots, separate
per-gate source baselines, acceptance results, unit-aware deltas, configuration,
and previous report/evidence-pack IDs. Shallow snapshots never embed predecessor
packs. Roots have a null predecessor and `is_root: true`.

Expose `compare_performance(report_id)` for deterministic evidence and
`get_previous_report(report_id)` for the predecessor's enriched pack. Root
traversal returns `history_end: true` and no predecessor. Bind chat sessions to
one assessment version to avoid mixing policies/configurations.

Persist full supporting series in packs. Tool responses include summary
evidence, violation periods, HTTP histograms, and explicit pack/path references
for series and bucket/window collections, avoiding repetition in
model context. Long violation-period collections show the first eight periods
and a full pack/path reference; persist all periods in the pack.

## Consequences

One report suffices for acceptance assessment and chat without a passing
baseline. Report history includes nonpassing reports independently of baseline
history. Acceptance configuration changes rebuild history under a new version
without editing stored packs. No new package.

## Alternatives

- **Identity by path or modification time.** Rejected: renames and filesystem
  metadata cannot reliably identify content; HTML hashes enable report reuse.
- **Accept backdated additions and rebuild order.** Rejected: this changes
  established predecessor/baseline links; validate batches atomically and reject
  new reports older than stored history.
- **Embed full history in each pack or let the model select baselines.**
  Rejected: recursive packs duplicate history; model selection is
  nondeterministic. Persist shallow references; select baselines in the
  assessment service.
