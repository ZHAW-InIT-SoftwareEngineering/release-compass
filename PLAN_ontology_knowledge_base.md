# Plan: make the RDF knowledge base the data layer (SQLite stays as a second adapter)

> **Status:** implemented (2026-11-18). Both the knowledge base and SQLite
> implement `ReportRepository` and `ReportQuestions`; `system.store` in
> `configs/application/local.yaml` selects one. `chat_session.py` imports,
> assesses, and wires the question tools and the LLM. Open: ADR updates
> (0005, 0008, 0013) await approval.

## Progress

| Part | State |
| --- | --- |
| Vocabulary `ontology/release-compass.ttl` | ✅ all classes, properties and `Outcome` individuals |
| Mappers `src/adapters/outbound/ontology/` | ✅ `report_triples` → `gate_triples` → `metric_triples`; `target_triples`; `assessment_triples` |
| Port `ReportRepository` + adapter `TurtleKnowledgeBase` | ✅ import, assessment (`unassessed_reports`, `gate_types`, `measurements`, `add_gate_assessment`, `apply_rules`), `save` |
| Import use case (step 3) | ✅ |
| Assessment use case and rules (step 4) | ✅ `AssessmentService`, `rules/*.rq` |
| SQLite adapter (step 6) | ✅ `SQLiteReportRepository` implements `ReportRepository`; rules in Python |
| Queries and tools (step 5) | ✅ `ReportQuestions` port, `queries/*.rq` / SQL, `harness/tools/report_tools.py` |

## Decisions made during implementation

- **Ports are shaped by the use cases**, not by SPARQL: the application never
  sees a query language. Competency questions go through the `ReportQuestions`
  port, one method per question, so both stores answer them.
- **Both stores are kept** in one codebase, verified by the same contract
  tests; the knowledge base is the default.
- **No transitional code:** no bridges between the old and new flow.
- **Port named for its role:** `ReportRepository`, not after a technology,
  because the knowledge base and SQLite both implement it.
- **Metrics store exactly what scoring reads:** `gate_triples` stores every
  `Measurement` that `performance_measure` yields for `measurements.SUPPORTED`;
  `ReportRepository.measurements` returns the identical list (tested).
- **Gate outcome comes from Python** (`score_gate` / `combine_outcomes`);
  SPARQL rules derive only the report outcome, `previous_report` and the
  baselines (ADR 0013, updated).
- **Per-transaction results** (`meets_target`, `excluded_reason`, `reason`)
  are triples about the `Metric` node in the assessment file of their version.
- **`release-compass:unit`** replaces `ai2core:units` (ADR 0014), whose two domains would
  make every metric a target.
- **Two named graphs** in one RDFLib `Dataset`: facts and the open assessment
  version; queries see both, writes go to one.
- **Size (measured):** 5 real Locust reports → 259k triples, 29 MB
  `facts.ttl`; import and save 30 s, reload 8 s, the 6 measurement queries of
  one report 5.7 s. Acceptable for now; options if too slow: one measurement
  query per gate instead of six, N-Triples instead of Turtle, or fewer stored
  statistics.

## Context

Today the pipeline is HTML → domain dataclasses → SQLite (JSON blobs) → Python
assessment (`AssessmentService`) → LangChain tools → LLM. History, baselines and
outcomes exist only in Python code and in opaque evidence-pack JSON.

The goal is to make the ontology in
`docs/implementation/ontology/release-compase-ontology.md` the data layer.
Every report fact and every assessment result becomes a triple in an RDF graph.
The LLM reads the graph only through fixed SPARQL queries, one per competency
question.

The decisions you made:

| Topic | Decision |
| --- | --- |
| Architecture | Graph-native: outcomes, baselines and history are SPARQL UPDATE rules |
| Metric scoring (ADR 0012) | Stays in Python (`src/domain/scoring.py`, unchanged). Results are written into the graph as triples. |
| LLM access | Fixed, tested SPARQL tools; the LLM never writes SPARQL |
| Mapping | Python + RDFLib in the ingestion adapter |
| Storage | RDFLib graph saved to and loaded from Turtle files |
| Prefix | `release-compass:`, with IRI `https://github.com/ZHAW-InIT-SoftwareEngineering/release-compass/ontology#` |
| Scoring results | New class `release-compass:MetricAssessment` |

## Target architecture

```
HTML ─► HTMLReport (ADR 0011 mapping, unchanged) ─► dataclass (adapter-internal)
                                                      │ report_triples.py
                                                      ▼
                          facts.ttl  (immutable report facts)
                                                      │ SPARQL SELECT measurements
                          scoring.py (unchanged) ◄────┘
                                                      │ MetricAssessment triples
                                                      ▼
                          assessment-<version>.ttl (derived, per policy version)
                            ▲ SPARQL UPDATE rules, report by report in chronological order:
                            │ previous_report → gate outcome → report outcome → baselines
                                                      │
                          fixed SPARQL queries ─► LangChain tools ─► LLM
```

- **Two files.** `facts.ttl` holds the ingested data and is never rewritten
  (ADR 0008). Each `assessment-<version>.ttl` holds the results of one
  assessment version. A changed target config produces a new file and keeps
  the old one, preserving today's per-version evidence behaviour.
- **One dataclass kept.** The parsed `PerformanceGate` dataclass stays as
  the adapter-internal parse result, because the ADR 0011 mapping config is
  built on its fields. It is never stored or queried. Rewriting the mapping
  to target ontology terms directly is a possible follow-up.

## Steps

### 0. ADR, Mermaid and dependency (first, before any code)
1. ✅ **DONE (2026-11-16)** — **Write ADR 0013 "Use an ontology-based knowledge base as the data
   layer"** as `docs/adrs/0013_use_ontology_knowledge_base.md`. It follows
   `0000_template_adr.md` and has a hard limit of 3000 characters. Approving
   this plan approves the ADR content outlined here.
   - **Context:** history, baselines and outcomes are hidden in Python code and
     SQLite JSON blobs. The LLM can't trace why a report passed. AI-Square
     already models staging data as an RDF knowledge graph queried with
     SPARQL (Mosquera et al., 2025).
   - **Decision:**
     - The release-compass ontology (`release-compass:` prefix plus reused
       `ai2core:` terms) is the data model, in OWL/RDFS Turtle
       (`ontology/release-compass.ttl`).
     - Data is stored as RDFLib graphs in `facts.ttl` (immutable) and
       `assessment-<version>.ttl` (derived).
     - Scoring stays in Python (ADR 0012) and writes `MetricAssessment`
       triples.
     - Outcomes, history and baselines are SPARQL UPDATE rules.
     - The LLM uses only fixed SPARQL tools, one per competency question.
     - Reused `ai2core:` properties whose domain or range would infer unwanted
       classes are replaced by `release-compass:` properties.
   - **Alternatives:**
     - Keep SQLite and add an RDF export: rejected, because there would be two
       models to keep in sync.
     - Score in SPARQL: rejected, because three-valued weighted scoring is hard
       to test.
     - Let the LLM write SPARQL: rejected, because answers would not be
       deterministic or verifiable.
     - Use a server triple store (Fuseki): rejected for now, because the scale
       doesn't need it.
   - **Consequences:**
     - Supersedes ADR 0002 (the canonical dataclass model) and the storage part
       of ADR 0008.
     - ADR 0005 and 0006 keep their rules, now implemented in SPARQL.
     - Adds the `rdflib` dependency.
     - Time series and violation periods are no longer exposed to the LLM.
   - Update the Status lines of ADR 0002 and 0008 to "superseded/partially
     superseded by 0013".
2. ✅ **DONE (2026-11-16)** — **Adjust the Mermaid diagram** in
   `docs/implementation/ontology/release-compase-ontology.md`. All of these
   are diagram and doc edits:
   - Every `rc:` becomes `release-compass:`. Relation labels change from
     `(rc)` to `(release-compass)`. The intro states the IRI.
   - Add the class `MetricAssessment["release-compass:MetricAssessment"]`
     with `score xsd:decimal`, `outcome Outcome`, `reason xsd:string` and
     `policy_version xsd:string`.
   - Add these relations:
     - `QualityGate "1" --> "1..*" MetricAssessment : has_assessment`
     - `MetricAssessment "*" --> "1" Target : assesses`
     - `MetricAssessment "1" --> "*" Metric : based_on`
   - Remove `Metric --> Target : assessed_against`, because
     `MetricAssessment` now holds that link.
   - Add these attributes:
     - `Report`: `source_fingerprint` and `source_path`
     - `Metric`: `metric_name` and `excluded_reason`
   - Update "Changes from the sketch" and the tech-stack section to match
     (the two-file layout and the link to ADR 0013).
3. ✅ **DONE (2026-11-16)** — Ask you to run `uv add rdflib` and, at the end, `uv remove pysqlite3` (the
   package is unused). Wait for your go-ahead before writing code.

### 1. Vocabulary file
- New `ontology/release-compass.ttl`: OWL/RDFS declarations of every
  `release-compass:` class and property (domain, range, label, comment). It
  reuses `ai2core:` IRIs and does not import the AI-Square file.
- It is not loaded at runtime (no reasoning); it is the model contract and is
  checked by `tests/ontology/test_release_compass.py`.
- ✅ `Report`, `previous_report`, `generated_at`, `ingestion_sequence`,
  `source_fingerprint`, `source_path` (not functional: aliases), `is_root`.

### 2. Port and RDFLib adapter
- ✅ `src/adapters/outbound/ontology/release_compass_ontology.py` holds the
  only copy of the IRI: `RELEASE_COMPASS` (`…/ontology#`),
  `RELEASE_COMPASS_DATA` (`…/data/`) and `new_graph()`, which binds the
  `release-compass` prefix.
- ✅ Port `src/application/ports/outbound/report_repository.py`
  (`ReportRepository`), a `Protocol` with domain types only, named for its
  role rather than the technology and shaped by the use cases:
  - import: `import_state()`, `get_by_fingerprint()`, `save_import_batch()`
  - assessment: `open_assessment(version)`, `measurements(report_id,
    gate_type, metric, statistic)`, `add_gate_assessment(report_id, gate_type,
    acceptance, targets, policy_version)` (also writes the version's targets)
  - `save()`; step 4 adds a method to apply the rules
- New adapter `src/adapters/outbound/ontology/turtle_knowledge_base.py`
  (✅ facts graph, `data/kb/facts.ttl`, atomic save via a `.tmp` file):
  - holds an RDFLib graph for the facts and one for the current assessment
  - loads and saves the `.ttl` files
  - binds `release-compass:`, `ai2core:` and `xsd:` prefixes
  - runs `select` and `update` across both graphs (assessment rules need the facts)
- One mapper file per entity in `src/adapters/outbound/ontology/`. Each
  returns a new `Graph`; a parent mapper merges its children's graphs
  (`report_triples` → `gate_triples` → `metric_triples`), so the nesting
  follows the data and no generic dispatcher is needed. ✅ `report_triples.py`.
  - **Literals:** strings are plain literals (RDF 1.1 `xsd:string`), so
    SPARQL bindings of Python strings match them; dates are UTC
    `xsd:dateTime`, numbers `xsd:integer`.
  - **Derived links** (`previous_report`, `is_root`, outcomes, baselines) are
    never mapped; the rules write them.
  - **IRIs:** `…/data/report/{uuid}`, `…/data/report/{uuid}/gate/performance`,
    `…/data/source/{transaction}`, `…/data/target/{version}/{metric}`, and so on.
  - **Metrics stored:** one `ai2core:Metric` per (source, metric_name, statistic)
    for the statistics in `measurements.SUPPORTED`, plus the run-level values
    used by `compare_gate`. Violation periods, histograms and time series are
    not modelled.
  - **Size check:** about 1129 transactions × 5 reports. Measure the load time
    and trim the stored statistics if it is too slow.

### 3. Ingestion use case
✅ `src/application/use_cases/import_reports.py` keeps its rules: fingerprint
dedupe, aliases, reject backdated reports, sequence numbers.
- It depends only on `ReportRepository` (`import_state`, `get_by_fingerprint`,
  `save_import_batch`), so it has no SPARQL and switching storage changes only
  the composition root.
- `TurtleKnowledgeBase` answers these with SPARQL from
  `src/adapters/outbound/ontology/queries/`. Reports carry `ai2core:has_id`, so
  queries find them without parsing IRIs.
- `chat_session.py` imports into `kb_dir` (`data/kb`, git-ignored) and returns
  `None`; `main.py` prints that chat is disabled.
- To restore with step 4: the dropped test "initial batch is assessed in
  timestamp order" returns as a `previous_report.rq` rule test, and
  `build_chat_session` wires assessment, tools and the LLM again.

### 4. Scoring → triples, then SPARQL rules (✅ DONE 2026-11-18)
- The use case builds a `Measure` from `ReportRepository.measurements` (no
  SPARQL in the application). `score_gate(targets, measure)` is reused
  unchanged, and its `GateAcceptance` goes to `add_gate_assessment`.
- New rules in `src/adapters/outbound/ontology/rules/*.rq` (run by a port method), each one a SPARQL
  UPDATE applied to one report at a time in chronological order:
  1. `previous_report.rq`: the latest earlier report, otherwise `is_root true`
     (ADR 0008)
  2. ~~`gate_outcome.rq`~~: dropped, the gate outcome comes from Python
  3. `report_outcome.rq`: the same combination over gates; a missing required
     gate gives unknown (ADR 0005)
  4. `baseline_report.rq` / `baseline_gate.rq`: the latest earlier passing
     report or gate (ADR 0006; gates are matched by evaluating the same targets)
- `AssessmentService` in `src/application/use_cases/assess_reports.py` becomes
  a thin runner:
  - open `assessment-<version>.ttl`
  - for each report not yet assessed: score, then apply the rules
  - save
  - the existing `version` hash logic is reused

### 5. Fixed queries and tools (✅ DONE 2026-11-18)

Done: `ReportQuestions` port (`describe_report`, `baselines`,
`compare_measurements`, `gate_results`) implemented by both stores
(SPARQL in `src/adapters/outbound/ontology/queries/`, SQL in the SQLite
adapter); `ReportQuestionService` checks reports exist and names missing
required gates; tools in `src/harness/tools/report_tools.py` cut source lists
to eight entries. `compare_measurements.rq` joins two subqueries by source
(a single pattern took 120 s on the real report, now under 1 s). Tool-error
tests restored. Original notes:

| Tool | Question | Returns |
| --- | --- | --- |
| `describe_report(report_id)` | Q1 | timestamp, sequence, gates, outcome |
| `get_previous_report(report_id)` | Q2 | previous report or `history_end` |
| `get_baseline(report_id)` | Q3 | report baseline and each gate baseline, policy version |
| `compare_gate(report_id, baseline_report_id)` | Q5 | matched metrics (same source, name, statistic) and SPARQL-computed deltas |
| `explain_outcome(report_id)` | Q6 | gate and metric outcomes, scores, targets, failing transactions |

- `explain_outcome` replaces `compare_performance`.
- `cicd_tool` stays; its gate reads the report outcome by query.
- The tools read through a port method per question, so both stores serve
  them; restore the tool-error tests (invalid UUID, missing report, storage
  error propagates) for the new tools.
- Questions 4, 7 and 8 stay out of scope, as the doc already notes.
- `src/chat_session.py` is re-wired: open the configured store, then import,
  then assess, then tools. `system_prompt` is updated with the new tool names.

### 6. SQLite as a second adapter (✅ DONE 2026-11-18, pulled before step 5)

Done: `SQLiteReportRepository` stores the same facts (reports, source paths,
gates, measurements) and results (targets, gate, metric, source and report
assessments) in tables and derives history, outcomes and baselines in
Python, reusing `combine_outcomes`. The gate registry moved to
`src/domain/gates/registry.py`, so both adapters store the same
measurements. Deleted: the old ports, `evidence.py`, `deltas/`,
`serialization.py`, `compare_gate.py`, `history.latest_passing` and the old
harness tools (`gate_tools`, `report_tools`, `build_tools`) with their tests.
Older SQLite files are rejected (schema version 2); delete and re-import.
`tests/application/use_cases/test_assess_reports.py` runs the same rule
scenarios against both stores. Original notes:

SQLite is kept. `SQLiteReportRepository` implements `ReportRepository`, so the
composition root can choose either store; the import and assessment tests then
run against both. What becomes obsolete is only the old evidence model:
- the `report_history.py`, `report_reader.py` and `report_writer.py` ports
- `src/domain/evidence.py` and the evidence-pack tables
- `history.latest_passing` (`generated_at` and `report_order` stay)
- `src/domain/deltas/`
- `src/domain/gates/performance/serialization.py`, unless the SQLite adapter
  still needs it to store gates

Each removal is checked with grep for remaining callers. Decided: SQLite
derives previous report, report outcome and baselines in Python inside the
adapter; the knowledge base does it with SPARQL rules.

## Verification

Tests use stdlib `unittest` and mirror `src/`:
- ✅ `tests/ontology/test_release_compass.py`: vocabulary declarations
  (types, domains, ranges, functional properties)
- ✅ `tests/adapters/outbound/ontology/test_turtle_knowledge_base.py`:
  save/reload round trip, no duplicates, SELECT values and bindings; still to
  add: facts file unchanged after assessment
- ✅ `tests/adapters/outbound/ontology/test_report_triples.py`: IRIs, types,
  values (Report only so far)
- `tests/application/knowledge/test_rules.py`: small hand-written Turtle
  fixtures for each rule:
  - pass, fail and unknown combinations
  - the root report
  - the baseline skipping failed and unknown reports
  - gate and report baselines coming from different reports
- `tests/application/knowledge/test_queries.py`: example data plus the
  expected answer for each implemented competency question (as the doc
  requires)
- rewrite `tests/integration/test_report_lifecycle.py` against the knowledge
  base. `RealReportFlowTests` must still give 1129 transactions and outcome
  `pass` on the real Locust HTML.
- `tests/domain/test_scoring.py` stays as it is

Run `uv run python -m unittest discover`, `uv run ruff check`,
`uv run ruff format --check` and `uv run ty check`, then start the chat
(`uv run python -m src.main`) and ask "why did the latest report pass?" and
"what is its baseline?".
