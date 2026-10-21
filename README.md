# release-compass

## Architecture

```mermaid
flowchart TB
    user(["User<br/>(terminal chat)"])
    main["<b>CLI entrypoint</b> · src/main.py<br/>loads configs/*.yaml and wires all parts"]

    subgraph harness["<b>Agent harness</b> · src/harness (LangGraph)"]
        llm["<b>LLM node</b><br/>answers using the current report"]
        approval["<b>Human approval</b><br/>pauses before cicd_tool runs"]
        tools["<b>Tool node</b><br/>compare_gate · compare_performance<br/>get_previous_report · cicd_tool"]
        llm -- "cicd_tool call" --> approval
        approval -- "approved" --> tools
        llm <-- "other tool calls / results" --> tools
    end

    openrouter[("<b>OpenRouter</b><br/>LLM API")]
    phoenix[("<b>Phoenix</b><br/>trace viewer")]

    subgraph app["<b>Application</b> · src/application"]
        importuc["<b>Import reports</b><br/>(runs once at startup)"]
        assess["<b>Assessment service</b><br/>gate acceptance · evidence packs"]
    end

    domain["<b>Domain</b> · src/domain<br/>reports · gates · thresholds · deltas"]

    subgraph adapters["<b>Outbound adapters</b> · src/adapters"]
        html["<b>HTMLReport</b><br/>parses report files"]
        sqlite["<b>SQLiteReportRepository</b><br/>stores reports and evidence"]
    end

    rawdata[("<b>HTML reports</b><br/>data/raw/reports")]
    db[("<b>SQLite</b><br/>data/database")]

    user <-- "chat · yes/no approval" --> main
    main -- "1 · import" --> importuc
    main -- "2 · chat turns" --> llm
    llm -- "prompts" --> openrouter
    tools -. "spans" .-> phoenix
    tools -- "queries" --> assess
    app -- "uses" --> domain
    importuc --> html
    importuc --> sqlite
    assess --> sqlite
    html -- "reads" --> rawdata
    sqlite -- "reads / writes" --> db
```

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

Agent runs are traced to a local Phoenix server, which starts automatically
with the agent (log: `data/harness/phoenix.log`).

To view traces, open [localhost:6006](http://localhost:6006) and select the
**release-compass** project.

Tracing is configured in `configs/trace/trace.yaml`:

- `enabled: false` turns tracing off.
- `auto_start: false` skips launching Phoenix, so you run it yourself.

## Environment

API keys are read only from the `.env` file in the project root (values set in the shell are ignored). The key needed depends on the `api_key_env` field of the LLM config in use:

| Key | Used by | Description |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | `configs/llm/openrouter.yaml` | API key for OpenRouter |

Example `.env`:

```dotenv
OPENROUTER_API_KEY="sk-or-..."
```
