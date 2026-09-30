# 4. Use string report IDs at the model tool boundary

Date: 2026-09-30

## Status

Accepted

## Context

The `compare_gate` LangChain tool is called by a language model. Its arguments are exposed as a tool schema and supplied as JSON values, while the application and domain use Python `UUID` values for report identity.

## Decision

Expose `report_id` and `baseline_report_id` as strings in the model-facing tool signature. Parse both strings into `UUID` values inside the tool adapter before calling the application use case.

## Consequences

The external schema uses a simple string representation compatible with JSON tool arguments. UUID parsing remains at the adapter boundary, and malformed IDs fail there before application or persistence code runs.
