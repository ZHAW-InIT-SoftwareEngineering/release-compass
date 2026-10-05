# TODOs

## Persist gate and report acceptance evidence

Implement the accepted decisions in [ADR 0005](../adrs/0005_separate_gate_and_report_acceptance.md)
and [ADR 0006](../adrs/0006_use_last_passed_gate_and_report_as_baselines.md).

- [ ] Define persistence schemas and repository ports for gate acceptance, report acceptance, and evidence packs.
- [ ] Define how the six configured Performance metrics are deterministically scored from report evidence. Preserve source values, units, and missing evidence; do not infer a pass when a metric cannot be assessed.
- [ ] Assess every gate independently against its configured rules and persist its outcome and evidence snapshot.
- [ ] Derive and persist report acceptance from its gate outcomes. A report passes only when every gate explicitly passes.
- [ ] Persist each ingested source report once. Baselines reference the stored report by ID; do not duplicate the parent report.
- [ ] Select the latest prior passing baseline independently for each gate type and for the report as a whole, using the generated-at ordering and tie-break rule in ADR 0006.
- [ ] Build and persist an immutable evidence pack containing current and baseline report IDs, each gate's baseline gate/report ID, acceptance results, snapshots, and the assessment/configuration version. Keep gate-level and report-level baselines distinct.
- [ ] Update application wiring to use the accepted baseline selection instead of comparing only the last two configured reports.
- [ ] Verify that persisted evidence packs can be read back with the one-hop history required by ADR 0005 and can identify earlier evidence by ID.
