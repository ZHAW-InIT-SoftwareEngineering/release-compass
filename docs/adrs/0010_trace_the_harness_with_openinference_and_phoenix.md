# 10. Trace the harness with OpenInference and local Phoenix

Date: 2026-10-19

## Status

Accepted

## Context

The CLI agent runs a LangGraph ReAct loop with tools and human approval before
the CI/CD tool. Terminal output shows only the final answer, obscuring model
messages, tool calls/results, timings, and approval-resume relationships.

## Decision

Instrument LangChain/LangGraph with `openinference-instrumentation-langchain`.
`src/harness/trace/trace.py` configures an OpenTelemetry tracer provider with a
batched OTLP/HTTP exporter to local Phoenix at `http://localhost:6006/v1/traces`,
project `release-compass`. Instrument before building the agent; on exit remove instrumentation and shut
down the provider, flushing queued spans even after startup failures.

Each turn's `graph.invoke` is a root trace `harness.turn`. Each
approval resume (`Command(resume=...)`) is a separate root
`harness.resume`. Use the LangGraph checkpointer `thread_id` as the OpenInference session ID:
one Phoenix session per CLI conversation. Include current report ID metadata.

`src/harness/trace/phoenix.py` auto-starts Phoenix for local HTTP `/v1/traces`
when tracing and `auto_start` are enabled, using the active interpreter
(`phoenix.server.main serve`). It waits for `/readyz` up to a
configured timeout, logs to `data/harness/phoenix.log`, reuses a ready server
without stopping it; stop only servers started here, after spans flush.
Remote and custom endpoints are managed externally. Startup failure stops the
CLI and reports the log path.

Settings: `configs/trace/trace.yaml` (`enabled`, `auto_start`, startup
and export timeouts, endpoint, project and service names). Capture inputs/outputs by default; OpenInference masking can limit payloads.

This follows the `imp` project's ADR 0031.

## Alternatives

- **Python `logging` only.** Rejected: nested model/tool spans,
  timings, and session grouping would require manual instrumentation and a
  viewer.
- **OpenInference with a console exporter.** Useful for debugging; rejected as
  default because flat records are harder to inspect than Phoenix's nested
  traces and sessions.
- **One trace per conversation.** Rejected: a long-lived root exports only at exit; per-invoke traces map to
  turns and resumes.

## Consequences

Phoenix exposes model/tool inputs and outputs, latency, errors, and approval
flow. OpenTelemetry-compatible export supports other collectors. This adds the `arize-phoenix`, OpenInference, and OpenTelemetry
dependencies, a managed local service, and trace storage under Phoenix's
working directory. `enabled: false` disables tracing. Traces record execution, not agent memory or evaluation verdicts.

See [OpenInference LangChain guide](https://arize-ai.github.io/openinference/python/instrumentation/openinference-instrumentation-langchain/),
the [OpenInference specification](https://github.com/Arize-ai/openinference/tree/main/spec),
and [Phoenix tracing documentation](https://arize.com/docs/phoenix/tracing).
