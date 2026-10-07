# Finding: Assessment service is coupled to performance configuration

Status: Resolved

`src/application/use_cases/assess_reports.py` accepts `PerformanceGateConfig` directly. The service reads its metric thresholds to build the default `PerformanceGate` assessor, and includes the config in its assessment-version hash so threshold changes invalidate prior evidence.

This is convenient while Performance is the only built-in gate, but the service now has performance-specific knowledge in addition to its general assessment and evidence orchestration. The optional `gate_definitions` argument does not remove that dependency: callers still need to provide `PerformanceGateConfig`, and the versioned configuration still records it.

As the report gains fields, generic snapshot serialization can preserve those fields in evidence. New gate types, however, need assessment and comparison definitions. Missing, duplicate, or unsupported gates are currently recorded as `unknown`, which prevents a report from passing. Each gate's configuration and policy also needs to participate in the assessment version so changes invalidate stale evidence correctly.

The likely extension point is to assemble gate definitions and their versioned configuration outside `AssessmentService`, then pass the service a complete, gate-neutral assessment setup. That keeps performance thresholds with the performance policy while the use case coordinates gate assessment, baselines, outcomes, and evidence.

This finding is consistent with [ADR 0005](docs/adrs/0005_separate_gate_and_report_acceptance.md), which calls for independent gate assessment, and [ADR 0007](docs/adrs/0007_use_provider_performance_assessments.md), which defines performance-specific scoring. Those decisions explain the distinct policies; they do not require the orchestration use case to depend directly on performance configuration.

## Resolution

Shared assessment contracts remain in `src/domain/assessment.py`. Performance
scoring moved to `src/domain/gates/performance/assessment.py`, and
`AssessmentService` now receives gate definitions and versioned configuration
from its caller. `src/application/performance_assessment.py` composes the
Performance profile. SQLite domain-type decoding uses an injected registry, so
the adapter no longer imports Performance gate classes.
