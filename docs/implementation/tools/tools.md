# POC tools

Both tools are bound by the host to one assessment/configuration version.
The LLM supplies string report UUIDs; services validate them and return
persisted deterministic evidence. Historical discussion remains in
[the discussion record](../discussions/01_discussions.md).

## compare_performance(report_id)

Returns the report's enriched evidence pack: current and independently selected
passing report/gate baselines, acceptance results, metric values and unit-aware
deltas, thresholds, provenance, supporting evidence, and chronological
predecessor/root references. The model cannot provide a different baseline.
Acceptance can pass without a baseline; comparison is then unavailable.

## get_previous_report(report_id)

Returns `{report_id, history_end, previous_report}`. The predecessor contains
its enriched evidence pack under the same assessment version. Failed and
unknown reports are included. Calling this tool on the root returns
`history_end: true` and `previous_report: null`.

Full time series and bucket/window collections are retained in SQLite;
tool responses reference these by evidence-pack ID and structured path.
HTTP histograms, assessments, weights, and exclusions remain in the
explanation-facing result. Long violation-period lists include the first eight
periods and a full stored-evidence reference.

Invalid UUIDs, absent reports, and unavailable assessments produce expected
tool errors. Unexpected storage/corruption failures propagate. The internal
explicit-ID comparison remains available for deterministic application callers.

See [ADR 0007](../../adrs/0007_use_provider_performance_assessments.md) and
[ADR 0008](../../adrs/0008_incremental_import_and_history.md).
