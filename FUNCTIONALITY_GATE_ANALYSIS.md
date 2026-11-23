# Functionality gate: analysis

Analysis only; nothing is implemented yet. Ground truth:
`data/raw/reports/example_reports/TeaStoreReports/Cypress_Mocha`.

The gate parts of the code are already mostly generic. The real problem is that
one imported file becomes one report, and a report only passes when it contains
every required gate.

## 1. What the reports contain

- **Format:** Mochawesome 7.1.4 (Mocha 7.0.1). Each `.html` stores its JSON in
  a `data-raw="…"` attribute, byte-for-byte the same data as the `.json` file
  next to it.
- **Content:** 4 spec files (`categories`, `navigation`, `shopping_cart`,
  `auth`), each with one nested suite, 23 tests in total.
- **Per test:** `title`, `fullTitle`, `state`
  (`passed`/`failed`/`pending`/`skipped`), `duration`, `err`.
- **Timestamp:** `stats.start` and `stats.end` give the run time.

Things to sort out in the data before relying on it:

1. **Every variant passes all 23 tests.** The "noise" variants only change
   durations, timestamps and UUIDs. There is no failing example, so the fail
   path can only be tested with test fixtures.
2. **`Noise_2` and `Noise_3` are byte-identical.** The import deduplicates by
   SHA-256, so `Noise_3` would become a second path on `Noise_2`'s report, not
   a new report.
3. **The timestamps don't line up with the Locust runs.** Cypress "Original"
   ran on 2026-11-04; all Locust runs on 2026-11-10 between 09:52 and 14:10.
   The Cypress noise runs are on 2026-11-10 between 14:38 and 14:51. With
   Locust reports already stored, importing Cypress Original as its own report
   is rejected as backdated (`import_reports.py:_reject_backdated_report`).

## 2. What already supports a second gate

| Area | Status |
| --- | --- |
| Scoring (`src/domain/scoring.py`) | Generic. A gate only supplies `Measurement`s; three-valued, weighted scoring is reused as is (ADR 0012). |
| Gate registry (`src/domain/gates/registry.py`) | One new `GATE_KINDS` entry registers the gate for both stores and for `compare_gate`. |
| Stores (TurtleKB, SQLite schema, rules) | Everything is keyed by `gate_type`; no schema change needed. |
| `AssessmentService` | Already accepts a list of `GateDefinition`s. The assessment version hash includes every gate's targets. |
| HTML extraction | `AttributeExtractor` (`kind: attribute`) already handles `data-raw`. |
| Harness tools and system prompt | Generic. Only the `compare_gate` default `gate_type="performance"` is performance-specific. |

## 3. The core design problem: pairing performance and functionality evidence

Today one HTML file becomes one `Report`, and `HTMLReport.ingest` always builds
a single `PerformanceGate`.

ADR 0005 and the `report_outcome` rule (`report_outcome.rq`,
`sqlite_db.apply_rules`) say a report passes only if every required gate is
present and passing. If `functionality` simply becomes a second required gate:

- every Locust report is `unknown` (no functionality gate);
- every Cypress report is `unknown` (no performance gate);
- so no report ever passes, there is never a report baseline, and `cicd_tool`
  never dispatches.

| Option | Idea | Trade-off |
| --- | --- | --- |
| **A. One report from several files** (recommended) | A `data.reports` entry lists several files (e.g. `inputs: [{path, source: locust}, {path, source: cypress}]`) and becomes one `Report` with one gate per file. | Matches "a report is one release candidate with several gate runs". Needs config, import and fingerprint changes and one ADR. |
| B. Separate reports, required gates per report | Each file is its own report; only gates present are required. | Smallest change, but the release decision for a Locust-only report ignores functionality. Weakens ADR 0005. |
| C. Pair by time window | Group nearby Locust and Cypress reports automatically. | Implicit and fragile; the example timestamps don't pair cleanly anyway. |

With option A, these need deciding:

- **Fingerprint:** a combined hash over the sorted file hashes, so adding or
  swapping one file gives a new report.
- **Timestamp:** suggested: the latest timestamp among the files.
- **Pairing in `local.yaml`:** five Locust reports against four distinct
  Cypress reports, given the duplicate.

## 4. What to add or change, by layer

### Domain

- New `src/domain/gates/functionality/functionality_gate.py`: a
  `FunctionalityGate(Gate)` with summary counts (tests, passes, failures,
  pending, skipped) and per-test results (name, suite/spec, state, duration,
  error message).
- New `src/domain/gates/functionality/measurements.py` with
  `GATE_TYPE = "functionality"`, `SUPPORTED`, and a `functionality_measure`.
  Suggestion:
  - one measurement per test, value 100 if passed and 0 if failed, unit `%`,
    weight 1;
  - pending/skipped tests get weight 0, so they are excluded;
  - target `{aggregation: pass_rate_percent, unit: "%", min: 100, max: null}`
    with `score: 1.0`, meaning every test must pass.

  This reuses `score_metric` unchanged, and failing tests appear by name in
  `explain_outcome`. Duration stays supporting evidence and is not scored, so
  it doesn't overlap the performance gate.
- `registry.py`: add the `FunctionalityGate` entry.
- `scoring.py:_assess` uses the reason "No observations" for weight 0; make
  the wording gate-neutral.

### Configuration

- New `configs/gates/functionality/functionality_gate.yaml`, same format as
  the performance targets.
- New `configs/ingestion/cypress.yaml` (or `mochawesome.yaml`) using the
  `attribute` extractor with `data-raw`.
- `src/configs/ingestion/html_mapping.py`: `HtmlMappingConfig.performance_gate`
  is required today. It needs to become an optional mapping per gate type
  (e.g. `gates: {performance: …}` / `{functionality: …}`), plus a
  `FunctionalityGateMapping`. The Locust mapping moves to the new shape.
- `src/configs/application/local.py` and `local.yaml`: register the new
  mapping and, with option A, allow several inputs per report.

### Ingestion

- `src/adapters/outbound/html_report.py:165-168` hardcodes `PerformanceGate`.
  It needs a map from mapping key to gate dataclass, ideally from the registry.
- `src/adapters/outbound/json_path.py` can't flatten
  `results[] → suites[] → tests[]`: no `[*]` and no recursive descent.
  Mochawesome nests suites to any depth, so this needs `[*]` flattening (plus
  recursion) or a dedicated `flatten` transform. Without it, `for_each` cannot
  list the tests.
- `import_reports.py`: with option A, the per-report fingerprint, timestamp and
  `source_paths` handling changes.

### Application and wiring

- `src/application/performance_assessment.py` is performance-only. It should
  become a generic builder taking `(gate_type, targets)` pairs and running
  `check_targets` against each gate's `SUPPORTED`.
- `src/chat_session.py:99` builds only the performance service, and
  `PERFORMANCE_CONFIG_PATH` is hardcoded. Both should be config-driven.

### Ontology and stores

- The `release-compass:Report` comment in `ontology/release-compass.ttl` says
  "(one HTML source)". With option A that changes.
- `metric_triples` stores the weight as `release-compass:request_count`. For
  tests that name is wrong; a neutral `weight` property (or a separate
  `test_count`) would fit both gates. Both stores must mirror the change.

### Harness

- `report_tools.py:106`: reconsider the default `gate_type="performance"`;
  making it required might be better.
- Optionally add one line to the system prompt naming both gate types.

### Tests (mirroring source paths)

- New: `tests/domain/gates/functionality/test_measurements.py`.
- Extended: `test_registry.py`, `test_html_mapping.py`, `test_html_report.py`,
  `test_json_path.py`, `test_import_reports.py`, `test_assess_reports.py`, both
  store tests, and `tests/integration/test_report_lifecycle.py`.
- Include a fixture with failing and pending tests, since the real data has
  none.

### ADRs (propose and approve before writing; 3000-character limit each)

- New: "Functionality gate scored on test outcomes" (metric, weighting, how
  pending/skipped tests count).
- New, or an update to 0008/0013: "One report from several source files"
  (identity, fingerprint, timestamp). Touches ADR 0005, 0006 and 0009.
- Update 0011: the mapping file has one section per gate type.

## 5. Open decisions

1. **Pairing:** option A (one report from several files), B, or C?
2. **Pass rule:** all tests must pass (`score: 1.0`), or a threshold? Should
   pending/skipped tests be excluded or count as failing?
3. **Granularity:** one measurement per test (failures named precisely), or
   per spec file weighted by test count (like Locust transactions)?
4. **Data:** add a Cypress variant with real failures? Keep the
   `Noise_2`/`Noise_3` duplicate?
5. **Input format:** parse the `.html` (consistent with ADR 0011) or allow the
   `.json`?
