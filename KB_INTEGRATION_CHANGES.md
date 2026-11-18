# Knowledge base integration: changes

State: commits `b0b8e05`, `c7412ee` plus the uncommitted step 4 and 5 work on `ontology-wt` (2026-11-18).
Design source: ADR 0013, ADR 0014, `PLAN_ontology_knowledge_base.md`.

Scope so far: reports are imported into the knowledge base (KB). Assessment,
the SPARQL rules and chat are not wired to the KB yet.

## Flow

```
configs/application/local.yaml (kb_dir: data/kb)
  → chat_session.build_chat_session()
    → import_reports(inputs, HTMLReport, TurtleKnowledgeBase)
        → kb.import_state()          latest generated_at + highest sequence
        → kb.get_by_fingerprint()    already imported? record an alias
        → HTMLReport.ingest()        HTML → Report dataclass
        → kb.save_import_batch()     report_triples → facts graph → facts.ttl
```

## Ontology and decisions

| File | How | Why |
|---|---|---|
| `ontology/release-compass.ttl` | Added `MetricAssessment`, `Outcome` (`pass`/`fail`/`unknown`), object properties (`contains_gate`, `produces_metric`, `measured_from`, `has_assessment`, `assesses`, `based_on`, `baseline_report`, `baseline_gate`, `outcome`) and datatype properties (`gate_type`, `metric_name`, `unit`, `statistic`, `value`, `request_count`, `field_path`, `min`/`max`/`min_score`, `score`, `reason`, …). | The ontology is the data model (ADR 0013); every stored triple needs a declared term. |
| `docs/adrs/0013_use_ontology_knowledge_base.md` | Status now supersedes the 0008 *evidence packs*; gate outcomes come from Python scoring; rules cover previous report, report outcomes and baselines. | Matches the implementation: `combine_outcomes` already scores gates. |
| `docs/adrs/0014_replace_ai2core_units_with_own_unit.md` (new) | `release-compass:unit` replaces `ai2core:units`; shared properties declare no `rdfs:domain`. | `ai2core:units` has two domains, so RDFS would infer every metric is also a target. |
| `docs/implementation/ontology/release-compase-ontology.md` | Diagram and notes updated to the new terms. | Keep the documentation in line with the `.ttl`. |

## Application layer

| File | How | Why |
|---|---|---|
| `src/application/ports/outbound/report_repository.py` | `ReportRepository` Protocol (first named `KnowledgeBase`) with `ImportState`; import methods (`import_state`, `get_by_fingerprint`, `save_import_batch`) and assessment methods (`open_assessment`, `measurements`, `add_gate_assessment`, `save`). | Use cases stay independent of RDF/SPARQL; methods are shaped by the use cases. |
| `src/application/use_cases/import_reports.py` | Takes a `ReportRepository` instead of `ReportHistory`; reads `import_state()` instead of listing all reports. | Import rules (fingerprint, aliases, backdating, sequence; ADR 0008) unchanged, storage swapped. |

## Outbound adapters (`src/adapters/outbound/`)

| File | How | Why |
|---|---|---|
| `sqlite/sqlite_report_repository.py` | Moved into `sqlite/` (content unchanged). | Separate the SQLite adapter from the ontology adapters. |
| `ontology/release_compass_ontology.py` | Namespaces (`release-compass:`, the `data/` namespace, `ai2core:`), `bind_prefixes`, IRI builders for report, gate, metric, source, target, assessment (URL-quoted segments). | One place for stable, deterministic IRIs; source IRIs are shared across reports to compare transactions. |
| `ontology/report_triples.py` | `Report` → type, `ai2core:has_id`, `generated_at`, `ingestion_sequence`, `source_fingerprint`, `source_path`s, then its gates. | Facts only; derived links come from rules. Fingerprint and paths allow reload and deduplication. |
| `ontology/gate_triples.py` (new) | Gate → `ai2core:QualityGate` + `gate_type`; measurements via the `_GATE_KINDS` registry, limited to `SUPPORTED`. | Store exactly what scoring can request; new gates only need a registry entry. |
| `ontology/metric_triples.py` (new) | `Measurement` → `ai2core:Metric` with name, statistic, field path, source, value, unit, `request_count`; numbers as `xsd:decimal`. | Gate-agnostic metrics; decimals compare exactly; non-finite values are rejected. |
| `ontology/target_triples.py` (new) | `MetricTarget` → `ai2core:Target` per assessment version. | Targets can change between configurations, so they belong to a version. |
| `ontology/assessment_triples.py` (new) | `GateAcceptance` → gate `outcome`, `MetricAssessment`s, `based_on` metrics, per-version `meets_target`/`excluded_reason`/`reason`. | Results of one assessment version, never written to the facts (ADR 0008/0012). |
| `ontology/turtle_knowledge_base.py` | RDFLib `Dataset` with two named graphs: facts (`facts.ttl`) and the open assessment (`assessment-<version>.ttl`); queries read the union, each write goes to one graph; atomic save via temp file; `_to_python` returns plain values. | Facts stay immutable; rdflib does not leak past the adapter; a failed save leaves no partial file. |
| `ontology/queries/*.rq` (new) | `import_state`, `report_by_fingerprint`, `measurements`. | Fixed, tested SPARQL instead of ad-hoc strings (ADR 0013). |

## Wiring and configuration

| File | How | Why |
|---|---|---|
| `configs/application/local.yaml`, `src/configs/application/local.py` | `system.db_path` → `system.kb_dir` (`data/kb`). | The KB replaces the SQLite file. |
| `.gitignore` | Ignores `/data/kb/`. | Generated by the import. |
| `src/chat_session.py` | Only imports into `TurtleKnowledgeBase`; returns `None`. LLM, tools and assessment wiring removed. | Assessment does not read from the KB yet (plan steps 4–5). |
| `src/main.py` | Prints a notice and exits when the session is `None`. | Chat is disabled until assessment reads from the KB. |
| `src/ontology/test.py` | Formatting only. | — |

## Tests

| File | Covers |
|---|---|
| `tests/adapters/outbound/ontology/examples.py` | Shared example reports and gates. |
| `tests/adapters/outbound/ontology/test_{report,gate,metric,target,assessment}_triples.py` | IRIs, types and values of each mapper. |
| `tests/adapters/outbound/ontology/test_turtle_knowledge_base.py` | Save/reload, import state, fingerprint lookup, aliases, measurements, assessment graph. |
| `tests/application/use_cases/test_import_reports.py` | Import rules against the KB. |
| `tests/ontology/test_release_compass.py` | Vocabulary: every term is declared with the expected domain and range. |
| `tests/integration/test_report_lifecycle.py`, `tests/test_chat_session.py`, `tests/configs/application/test_local.py` | Adjusted to the KB and `kb_dir`. |

Result: 136 tests pass (`uv run python -m unittest discover -s tests -t .`).

## Step 4: assessment, rules, SQLite as second adapter (2026-11-18)

| File | How | Why |
|---|---|---|
| `src/application/ports/outbound/report_repository.py` | Added `unassessed_reports`, `gate_types`, `apply_rules`. | The use case asks for work and triggers the rules without knowing SPARQL or SQL. |
| `src/application/use_cases/assess_reports.py` | Rewritten: open version → for each unassessed report score its required gates (`score_gate` with measurements from the store) → `apply_rules` → `save`. Version is a hash of gates, targets and policy versions. | Gate outcomes stay in Python (ADR 0012); history, report outcome and baselines come from the store (ADR 0013). |
| `src/application/performance_assessment.py` | Builds the service with one `GateDefinition("performance", targets, policy)`. | No gate dataclass is needed for scoring any more. |
| `src/domain/assessment.py` | `GateDefinition` is now (gate type, targets, policy version); `compare_acceptance_scores` removed. | The assess/compare callables belonged to the evidence-pack flow. |
| `src/domain/history.py` | `latest_passing` removed. | Baselines are rules now. |
| `src/domain/gates/registry.py` (new), `performance/measurements.py` | Gate type → name, measure, supported statistics; `GATE_TYPE = "performance"`. | Both adapters store exactly the measurements scoring can request. |
| `ontology/gate_triples.py` | Uses the registry. | Single source for gate kinds. |
| `ontology/turtle_knowledge_base.py` | `unassessed_reports`, `gate_types`, `apply_rules` (runs `RULES` in order, writes into the assessment graph). | Rules read facts and results, write only results. |
| `ontology/queries/{unassessed_reports,gate_types}.rq`, `ontology/rules/{previous_report,report_outcome,baseline_report,baseline_gate}.rq` (new) | SPARQL SELECT and UPDATE. | ADR 0005, 0006, 0008 rules in SPARQL. |
| `sqlite/sqlite_report_repository.py` | Rewritten as `ReportRepository`: tables for reports, paths, gates, measurements, targets and gate/metric/source/report assessments; schema in `schema.sql`, queries and rules as `.sql` files in `queries/` and `rules/`, named like the SPARQL files; results commit on `save()`; schema version 2, older files rejected. | Second adapter with the same data as the knowledge base. |
| `src/configs/application/local.py`, `configs/application/local.yaml` | `system.store` (`knowledge_base` or `sqlite`) with `kb_dir` and `db_path`. | The composition root picks the store. |
| `src/chat_session.py`, `src/main.py` | `open_repository()`, then import and assess; still returns `None`. | Chat waits for the step 5 tools. |
| Deleted | `report_history.py`, `report_reader.py`, `report_writer.py`, `compare_gate.py`, `domain/evidence.py`, `domain/deltas/`, `performance/serialization.py`, `harness/tools/{gate_tools,report_tools,build_tools}.py`, `tests/harness/tools/test_tool_errors.py`. | Evidence-pack model replaced; tools are rebuilt in step 5. |
| Tests | `test_assess_reports.py` (same scenarios on both stores), `sqlite/test_sqlite_report_repository.py`, `domain/gates/test_registry.py`; integration test assesses the real Locust report in both stores (`pass`). | Both paths verified. |

## Step 5: competency-question tools, chat wired again (2026-11-18)

| File | How | Why |
|---|---|---|
| `src/application/ports/outbound/report_questions.py` (new) | `ReportQuestions` port: `describe_report`, `baselines`, `compare_measurements`, `gate_results`, with read models (`ReportSummary`, `Baselines`, `MeasurementChange`, `GateResult`, …). | One method per competency question, so both stores answer without the application seeing SPARQL or SQL. |
| `src/application/use_cases/answer_report_questions.py` (new) | `ReportQuestionService`: raises `ReportNotFoundError`, composes the previous report, adds missing required gates. | Tools stay thin; no calculation outside the store. |
| `ontology/queries/{describe_report,baselines,compare_measurements,gate_results}.rq` (new), `turtle_knowledge_base.py` | Fixed SPARQL; deltas computed in SPARQL; compare uses two subqueries joined by source. | Single join pattern took 120 s on the real report; now under 1 s. |
| `sqlite/sqlite_report_repository.py` | Same four methods in SQL. | Second adapter gives identical answers. |
| `src/harness/tools/report_tools.py`, `build_tools.py` (new), `common.py` | `describe_report`, `get_previous_report`, `get_baseline`, `compare_gate`, `explain_outcome` + `cicd_tool`; JSON via `to_json`; source lists cut to 8 with full counts. | Q1, Q2, Q3, Q5, Q6; keeps answers small for the LLM (ADR 0008 limit of eight). |
| `src/harness/system/system_prompt.py` | New tool names. | — |
| `src/chat_session.py`, `src/main.py` | Import → assess → `ReportQuestionService` → tools → LLM → graph; CI/CD reads the current outcome via `describe_report`. | Chat works again on either store. |
| `docs/implementation/tools/tools.md` | Rewritten for the new tools. | Doc matched the old evidence-pack tools. |
| Tests | `test_answer_report_questions.py` (same questions on both stores), `tests/harness/tools/test_report_tools.py` (restored tool errors), integration test: both stores give identical tool answers on the real report, chat session wires six tools. | Both paths verified end to end. |

## Open

- ADR updates awaiting approval: 0013 (questions via `ReportQuestions`, both stores), 0008 (tool names), 0005 (duplicate-gate case).
- Duplicate gates of one type in a report share one IRI/row, so ADR 0005's "duplicate gate gives unknown" cannot occur; import rejects unsupported gates.
