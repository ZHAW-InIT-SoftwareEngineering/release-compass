# Incremental ingestion, assessment, and report history

## Architecture and flow

Extend the existing layers; no new dependencies are needed.

- **Application:** orchestrate incremental import, assessment, baseline discovery, evidence construction, and history retrieval. Move `ingest_configured_reports` out of `main.py`; keep application inputs independent of YAML/Pydantic configuration models.
- **Domain:** define acceptance results, provider assessment interpretation, baseline policy, comparisons, and evidence-pack types.
- **Repository ports and SQLite adapter:** persist reports, assessment results, immutable evidence packs, source fingerprints, and deterministic ingestion order.
- **`main.py`:** load configuration, construct services, import configured reports, prepare assessments, select the latest stored report as chat context, and register tools.

Process reports chronologically. Assess gates from their own evidence and configured thresholds; derive report acceptance; select earlier passing baselines; calculate comparisons; persist the resulting evidence pack.

## Import and history

- Identify source reports by **SHA-256 of the HTML bytes**. An existing fingerprint reuses its report UUID and stored timestamps without reparsing or rewriting the report. Changed content creates a new report.
- Preserve the original source path and record additional paths encountered for identical content.
- Timestamp precedence: complete HTML timestamp, complete configured timestamp, then UTC time at first import. Reject partially supplied timestamp pairs.
- Persist an ingestion sequence. Order reports by `(generated_at UTC timestamp, ingestion sequence)`, preserving configured order for timestamp ties.
- Sort new imports before processing. Reject a new report whose timestamp precedes the latest stored report; validate the entire batch before writing. Identical-content imports remain valid regardless of configuration changes.
- Allow one stored report: acceptance can run without a baseline. Remove the two-report minimum.
- Store the immediate chronological `previous_report_id` separately from report and gate baselines. The first report has `previous_report_id: null` and `is_root: true`.

## Performance acceptance and baselines

Extend normalization to retain provider metric assessments, weights, exclusions, reasons, and their source paths.

**Score precedence:** use explicit `performance_gate.metrics` scores when supplied. Otherwise use these provider assessments:

| Metric | Assessment source |
|---|---|
| Response time | Transaction-health `components.local_nfr` penalties |
| Throughput | Load-summary status mapped through the report’s categorical penalty weights |
| Request outcomes | Transaction-health `components.failure_transactions_rate` penalties |
| Transaction NFR status | Supplied aggregate `nfr_compliance.score_nfr` penalty |
| CPU and memory | Per-node `metrics_components[metric].local_nfr` penalties |

- Convert penalties to acceptance scores using `1 − penalty`. Apply the existing configured `>=` thresholds; preserve provider thresholds and passing flags as separate evidence.
- For response time, throughput, and request outcomes, aggregate using supplied transaction weights. For CPU and memory, use supplied node weights. Normalize over included sources and preserve explicit exclusions.
- Missing required scores, weights, unknown status mappings, or included unevaluable sources produce `unknown`. An empty eligible source set also produces `unknown`; never substitute a passing score.
- Performance passes only when all six required metric assessments pass. Report acceptance requires every required gate to pass; the POC requires Performance. Explicit failures produce `fail`; otherwise unresolved requirements produce `unknown`.
- Gate baselines select the latest earlier **passing gate of the same type**, independently of report acceptance. Report baselines select the latest earlier **passing report**.
- Acceptance remains possible without a baseline. The first qualifying item establishes a baseline for subsequent reports.
- Preserve the provider’s overall release score as provenance; the project’s release result follows its gate-acceptance rule.

## Evidence and tools

Persist packs keyed by report ID and assessment version. Derive the version from the acceptance configuration and interpretation-policy version. Reuse existing packs for unchanged versions; configuration/policy changes rebuild assessments chronologically into new immutable packs.

Each pack contains:

- Current report identity, timestamps, predecessor/root information, and acceptance results.
- Report baseline and each gate’s baseline/source report IDs, results, and snapshots.
- Metric values, units, sources, observation counts, time ranges, targets, statuses, assessments, weighting/exclusion reasons, and supporting evidence.
- Absolute deltas and relative deltas where meaningful. Zero baselines, missing values, and incompatible units have explicit unavailable reasons.
- Assessment/configuration version and references to earlier packs. Snapshot references remain shallow; packs do not recursively embed the entire history.

Expose:

- **`compare_performance(report_id)`**: return the prepared evidence pack using deterministic baseline selection.
- **`get_previous_report(report_id)`**: return the predecessor’s enriched pack; return an explicit history-end result when called on the root.

Bind both tools to one assessment version per chat session. Keep explicit-ID comparison as an internal primitive. Update the system prompt to require tool-grounded metrics, baselines, and acceptance explanations.

## Validation and documentation

Test repeat imports, renamed files, changed content, timestamp precedence/ties, atomic rejection of older imports, and one-report operation.

Test explicit-score precedence, each provider assessment mapping, weights/exclusions, missing evidence, threshold boundaries, independent gate/report baselines, and first-pass baseline establishment.

Test immutable pack round-trips, configuration-version rebuilds, comparison edge cases, chronological traversal to root, UUID/not-found tool errors, and propagation of unexpected storage errors. Preserve the existing HTML metric assertions.

Update the ADRs and POC documentation to record the selected scoring mappings, aggregation, ingestion identity, chronological history, and acceptance without a prior baseline. Run relevant tests and repository checks before implementation is considered complete.
