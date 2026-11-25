# 15. Compare measurements in Python

Date: 2026-11-23

## Status

Accepted; supersedes 0003

## Context

Q5 compares one metric statistic of a gate between a report and a baseline
report. ADR 0013 removed the dataclass model that ADR 0003 compared, and
both stores then computed the deltas in their own query (SQL and SPARQL). The
rule "no delta when units differ" was written twice and tested only through
the stores. Scoring already stays in Python because it is easier to test
there (ADR 0012).

## Decision

- Both stores return only facts: `ReportQuestions.measurements(report_id,
  gate_type, metric, statistic)` gives one statistic of a gate run, one
  `Measurement` per source.
- The pure domain function `compare_measurements` (`src/domain/comparison.py`)
  matches the two runs by source and returns `MeasurementChange` values,
  ordered by source.
- The delta is current minus baseline. It is `None` when either value or unit
  is missing or the units differ. Sources found in only one run are left out.
- `ReportQuestionService.compare_gate` checks that both reports exist, reads
  both runs and calls the function.

## Alternatives

- **Compute the delta in each store's query.** It keeps the whole answer in
  one query, traceable to SPARQL. Rejected: the rule lives in two languages
  and is tested only through both stores.
- **Compare whole reports by reflection over dataclasses** (ADR 0003).
  Rejected: stores no longer rebuild gates, and reflection compares every
  numeric field without units.

## Consequences

- One definition of the comparison rule, unit-tested without a store.
- Two reads per comparison instead of one joined query; fine at this data
  scale.
- Stores keep only fact and rule queries; `compare_measurements.sql` and
  `compare_measurements.rq` are removed.
- The graph supplies the facts of a comparison, while the delta itself is
  not stored or derivable in the knowledge base. The same split already
  applies to scoring.
