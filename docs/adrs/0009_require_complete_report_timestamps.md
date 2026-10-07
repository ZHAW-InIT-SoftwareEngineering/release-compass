# 9. Require complete report timestamps

Date: 2026-10-07

## Status

Accepted

## Context

Chronological processing and baseline selection need a reliable report
generation time. Assigning import time when the report has no timestamp makes
ordering depend on when the file happened to be ingested.

## Decision

Use a complete `generated_at_date` and `generated_at_time` pair from the HTML
report when present. Otherwise, require both fields in import configuration.
Reject a partial pair from the selected source and reject the report if neither
source supplies a complete pair. Do not substitute the current time. Identical
content reimports retain the timestamp stored on first import.

## Alternatives

- **Use the current UTC time when both sources are missing.** Rejected because
  import time is not report generation time and can produce misleading
  chronology and baseline selection.
- **Require timestamps in HTML only.** Rejected because configuration is a
  useful explicit fallback for source reports that omit generation metadata.
- **Accept a partial pair and infer its missing field.** Rejected because the
  inferred value would be arbitrary and could misorder reports.

## Consequences

Every newly imported report has a complete timestamp before it can be stored
or assessed. Timestamp ordering remains reproducible across repeat imports.
