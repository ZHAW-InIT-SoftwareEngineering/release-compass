# POC tools

One tool per competency question
([release-compase-ontology.md](../ontology/release-compase-ontology.md)),
implemented in `src/harness/tools/report_tools.py`. The LLM passes report
UUIDs as strings (ADR 0004). Each tool calls one `ReportQuestions` port method,
so the knowledge base (fixed SPARQL in
`src/adapters/outbound/ontology/queries/`) and SQLite give the same answers.
Answers come from the assessment version prepared at startup (ADR 0008,
ADR 0013). Tools return stored values only; they never calculate.

| Tool | Question | Returns |
| --- | --- | --- |
| `describe_report(report_id)` | Q1 | generated-at, ingestion sequence, source paths, gate types, outcome, `is_root`, previous report ID |
| `get_previous_report(report_id)` | Q2 | `{report_id, history_end, previous_report}`; failed and unknown reports included |
| `get_baseline(report_id)` | Q3 | report baseline, each gate's baseline and policy version, selection policy (ADR 0006) |
| `compare_gate(report_id, baseline_report_id, gate_type, metric, statistic)` | Q5 | matched and compared source counts, largest absolute deltas (computed in Python, ADR 0015; only with equal units) |
| `explain_outcome(report_id)` | Q6 | report outcome, missing required gates, per gate and metric: target, score, outcome, reason, policy version, source counts, sources missing the target or not evaluable |
| `cicd_tool()` | — | starts the CI/CD approval; refused unless the current report passed (ADR 0005). After approval, sends a GitHub `repository_dispatch` (`configs/cicd/github_dispatch.yaml`) with `client_payload` `{report_id, outcome}` |

Lists of sources are cut to the first eight entries; the counts stay complete.
Questions 4, 7 and 8 are out of scope.

Invalid UUIDs, unknown reports and unsupported metric statistics return a
tool error to the model. Other failures, e.g. a broken store, propagate.
