# 3. Compare matching gates from current and baseline reports

Date: 2026-09-30

## Status

Accepted

The explicit-ID comparison remains an internal primitive. Its compact,
two-ID tool contract has been superseded in the chat interface by the
automatic evidence tools in [ADR 0008](0008_incremental_import_and_history.md).

## Context

The agent needs to compare performance evidence without receiving complete reports in its context. Reports are stored and retrieved by `report_id`; each report contains typed domain gates. Comparison must identify the same gate kind in the current and baseline reports and return both source values and their changes.

The comparison also needs to remain independent of SQLite and of the agent tool protocol.

## Decision

The application `compare_gate` use case receives current and baseline report IDs, a `ReportReader`, and the concrete gate type to compare. It loads both reports, requires exactly one matching gate of that type in each report, and returns a `GateDeltas` value containing:

- the gate type;
- the baseline gate snapshot;
- the current gate snapshot;
- numeric values keyed by domain field path, with baseline, current, and delta values.

Numeric deltas are calculated as **current minus baseline**. Time series, violation period lists, and supporting evidence are retained in the gate snapshots but excluded from numeric delta calculation. Missing numeric values are represented with a `null` delta rather than treated as zero.

The pure `compute_report_deltas` domain operation compares the two selected gates. The LangChain tool is a thin wrapper built with a `ReportReader` and gate type supplied by the host. It accepts report IDs as strings, validates them as UUIDs, and returns only the compact numeric comparison. It does not construct storage adapters or accept application services as model-provided arguments.

## Alternatives

- **Pass full reports to the language model and ask it to compare them.** Rejected because it spends context on unrelated evidence and makes arithmetic less reliable.
- **Let the tool issue arbitrary SQL.** Rejected because comparison rules should operate on domain models and remain independent of the chosen storage adapter.
- **Compare only matching field names without selecting a gate type.** Rejected because reports may contain multiple gate kinds, and matching must be explicit and unambiguous.

## Consequences

The tool can return focused comparisons while preserving baseline and current gate snapshots for application callers that need detailed evidence. Adding gate types requires registering their domain types with the persistence adapter and selecting the type when building the comparison tool.

Comparison fails explicitly when either report is missing or contains zero or multiple gates of the selected type. Numeric fields are compared mechanically; domain-specific interpretation of status codes and metric direction remains a higher-level concern.
