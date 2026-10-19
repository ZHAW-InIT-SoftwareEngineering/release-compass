# 10. Trace the harness with OpenInference and local Phoenix

Date: 2026-10-19

## Status

Accepted

## Context

The CLI agent runs a LangGraph ReAct loop with tool calls and a human approval
interrupt before the CI/CD tool. Terminal output shows only the final answer, so
it is hard to see which messages reached the model, which tools ran, what they
returned, how long each step took, and how an approval resume relates to the
turn that requested it.

## Decision

Instrument LangChain/LangGraph with `openinference-instrumentation-langchain`.
`src/harness/trace/trace.py` configures an OpenTelemetry tracer provider with a
batched OTLP/HTTP exporter to local Phoenix at `http://localhost:6006/v1/traces`,
under project `release-compass`. Instrumentation starts before the agent is
built; on exit it is removed and the provider is shut down, flushing queued
spans even after startup failures.

Each user turn's `graph.invoke` is a root trace named `harness.turn`. Each
approval resume (`Command(resume=...)`) is a separate root trace named
`harness.resume`. The OpenInference session ID is the LangGraph checkpointer
`thread_id`, so a Phoenix session equals one CLI conversation. Traces carry the
current report ID as metadata.

`src/harness/trace/phoenix.py` starts Phoenix automatically for local HTTP
`/v1/traces` endpoints when tracing and `auto_start` are enabled, using the
active interpreter (`phoenix.server.main serve`). It waits for `/readyz` up to a
configured timeout, logs to `data/harness/phoenix.log`, reuses a ready server
without stopping it, and stops only a server it started after spans flush.
Remote and custom endpoints are managed externally. Startup failure stops the
CLI and reports the log path.

Settings live in `configs/trace/trace.yaml` (`enabled`, `auto_start`, startup
and export timeouts, endpoint, project and service names). Inputs and outputs
are captured by default; OpenInference masking options can limit payloads.

This follows the approach used in the `imp` project (its ADR 0031).

## Alternatives

- **Python `logging` only.** Rejected: reproducing nested model/tool spans,
  timings, and session grouping would require manual instrumentation and a
  viewer.
- **OpenInference with a console exporter.** Rejected as the default: useful
  for debugging, but flat span records are hard to inspect compared to
  Phoenix's nested trace and session views.
- **One trace per conversation.** Rejected: a long-lived root span is only
  exported at exit, and per-invoke traces map cleanly to turns and resumes.

## Consequences

Model and tool inputs/outputs, latency, errors, and the approval flow can be
inspected in Phoenix. Export is OpenTelemetry-compatible and not tied to one
collector. This adds the `arize-phoenix`, OpenInference, and OpenTelemetry
dependencies, a managed local service, and trace storage under Phoenix's
working directory. Set `enabled: false` to run without tracing. Traces are
execution records, not agent memory or an evaluation verdict.

See the [OpenInference LangChain guide](https://arize-ai.github.io/openinference/python/instrumentation/openinference-instrumentation-langchain/),
the [OpenInference specification](https://github.com/Arize-ai/openinference/tree/main/spec),
and [Phoenix tracing documentation](https://arize.com/docs/phoenix/tracing).
