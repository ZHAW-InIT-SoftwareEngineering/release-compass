# 2. Use a hexagonal boundary for report ingestion

Date: 2026-09-28

## Status

Accepted

## Context

Release Compass consumes external performance reports. The current input is an AI-SQUARE HTML report containing embedded JSON, but the serving format may change to JSON, an API, or another source.

Report-specific schemas and transport formats must not leak into the application or domain logic.

## Decision

We will introduce an `IngestionPort` as the application boundary for report ingestion.

The port returns a canonical Release Compass `PerformanceReport` domain model. External formats are handled by adapters implementing this port.

The initial implementation is an `AiSquareHtmlIngestionAdapter`, which extracts `__report_data__` from the HTML and maps the AI-SQUARE schema to the canonical model.

```text
AI-SQUARE HTML
      ↓
AiSquareHtmlIngestionAdapter
      ↓
IngestionPort
      ↓
PerformanceReport
```

External report schemas terminate at the ingestion adapter. Application logic, comparison logic, persistence, and agent tools operate only on canonical domain models.

## Alternatives

- **Expose the raw report to the agent and let it ingest or parse the report through an agent tool.** Rejected because the report is large and contains substantial presentation code, time-series data, and logs. Loading this data into the LLM context would unnecessarily consume context capacity, reduce the signal-to-noise ratio, and repeatedly incur parsing work for each interaction.

## Consequences

Report formats can be replaced without changing the application or agent logic; only the corresponding adapter and dependency wiring change.

The ingestion adapter is responsible for parsing, validation, schema mapping, and translation of provider-specific errors.

This introduces an explicit domain model and adapter boundary, adding some structure but preventing coupling to the current AI-SQUARE HTML format.