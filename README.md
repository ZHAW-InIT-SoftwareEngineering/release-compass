# release-compass


Run the local conversational POC:

```bash
uv run python -m src.main
```

Local report paths, fallback timestamps, and the SQLite path are configured in
`configs/application/local.yaml`; metric acceptance thresholds are in
`configs/gates/performance/performance_gate.yaml`. LLM configuration is loaded
from `configs/llm/openrouter.yaml`, with its named API key read from `.env`.

Startup imports unseen report content, prepares versioned acceptance/evidence,
and uses the latest stored report as chat context. Repeat imports reuse stored
UUIDs; later backdated additions are rejected. The agent explains deterministic
results through `compare_performance` and `get_previous_report`.

## Trace

The agent is traced with OpenInference and exported to local Phoenix. Startup
launches Phoenix automatically (log: `data/harness/phoenix.log`), reuses a
running server, and stops a server it started after flushing traces on exit.
Open [localhost:6006](http://localhost:6006), select the **release-compass**
project, and inspect **harness.turn** and **harness.resume** (CI/CD approval)
traces. Turns in one conversation share a session ID; traces carry the current
report ID. Configure tracing in `configs/trace/trace.yaml`; set `enabled: false`
to disable it or `auto_start: false` to manage Phoenix yourself. See
[ADR 0010](docs/adrs/0010_trace_the_harness_with_openinference_and_phoenix.md).

Run checks with the existing environment:

```bash
uv run python -m unittest discover -s tests
```
