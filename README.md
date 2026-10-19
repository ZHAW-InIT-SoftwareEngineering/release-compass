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

Run checks with the existing environment:

```bash
uv run python -m unittest discover -s tests
```
