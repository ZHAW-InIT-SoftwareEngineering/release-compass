# Questions the ontology must support

1. **What does a report describe?** Identify its project, system, software
   version, execution, environment, and workload.
2. **Which report immediately preceded it?** Retrieve its chronological
   predecessor within a defined history scope, including failed and unknown
   reports, or identify the beginning of that history.
3. **Which baseline applies, and why?** Distinguish the report baseline from
   each gate's baseline and explain the selection policy and version.
4. **Are particular measurements comparable?** Check their subjects, metric
   meanings, statistics, units, measurement procedures, and execution contexts;
   explain incompatibility or missing information.
5. **What changed?** Retrieve matched current and baseline observations and
   their deterministic comparison results.
6. **Why did a gate or report pass, fail, or remain unknown?** Retrieve the
   applicable requirements, assessment policy, outcomes, and supporting evidence.
7. **Where did an answer come from?** Trace it to source reports, field
   locations, and the analysis activity that produced a derived result.
8. **What information is missing?** Distinguish unavailable evidence, an
   unavailable baseline, and an analysis that has not been performed.

## Proposed conceptual graph

This is a **draft for discussion**, not an accepted architecture decision. Names
and relationships below describe the domain independently of a serialization,
programming language, database, or report provider. Arrows read from subject to
object: “Report describes Run,” for example. These are permitted relationships;
their presence in the diagram does not mean every instance must have every link.

```mermaid
flowchart TB
    subgraph Context["Execution context"]
        Project["Project"] -->|has system| System["System under test"]
        System -->|has version| Version["Software version"]
        Run["Run"] -->|tests version| Version
        Run -->|has context| ExecutionContext["Execution context"]
        ExecutionContext -->|uses environment| Environment["Environment"]
        ExecutionContext -->|uses workload| Workload["Workload"]
        Report["Report artifact"] -->|describes| Run
    end

    subgraph Evidence["Measurements and source evidence"]
        Observation["Observation"] -->|belongs to| Run
        Observation -->|measures subject| Subject["Measured subject"]
        Observation -->|observes property| Metric["Metric definition"]
        Observation -->|uses statistic| Statistic["Statistic"]
        Observation -->|uses procedure| Procedure["Measurement procedure"]
        Observation -->|covers| Window["Observation time window"]
        Observation -->|has result| Quantity["Quantity value"]
        Quantity -->|has unit| Unit["Unit"]
        Metric -->|has quantity kind| QuantityKind["Quantity kind"]
        Observation -->|has source reference| Reference["Evidence reference"]
        Reference -->|identifies source| Report
        Reference -->|locates evidence at| Location["Source field or stored evidence location"]
        Transaction["Transaction"] -->|is a kind of| Subject
        Component["Component"] -->|is a kind of| Subject
        System -->|is a kind of| Subject
    end

    subgraph Decisions["Assessments and comparisons"]
        GateAssessment["Gate assessment"] -->|is a kind of| Assessment["Assessment"]
        ReportAssessment["Report assessment"] -->|is a kind of| Assessment
        Assessment -->|assesses| Run
        Assessment -->|uses policy| Policy["Policy version"]
        Assessment -->|has outcome| Outcome["Assessment outcome"]
        Assessment -->|is supported by| Observation
        Assessment -->|evaluates| Requirement["Requirement"]
        GateAssessment -->|assesses gate| Gate["Gate definition"]
        Gate -->|checks| Requirement
        ReportAssessment -->|aggregates| GateAssessment

        Selection["Baseline selection"] -->|is for| Assessment
        Selection -->|selects baseline| BaselineAssessment["Baseline assessment"]
        BaselineAssessment -->|is a role of| Assessment
        Selection -->|uses policy| Policy
        Selection -->|is within| Scope["History scope"]
        Selection -->|has status| SelectionStatus["Selection status"]
        Selection -->|has reason| Reason["Reason"]

        Comparison["Comparison"] -->|uses current observation| Observation
        Comparison -->|uses baseline observation| BaselineObservation["Baseline observation"]
        BaselineObservation -->|is a role of| Observation
        Comparison -->|uses policy| Policy
        Comparison -->|has compatibility| Compatibility["Compatibility result"]
        Comparison -->|has difference| Difference["Difference result"]
        Comparison -->|has reason| Reason
    end

    subgraph History["Chronological history"]
        Position["History position"] -->|identifies report| Report
        Position -->|is within| Scope
        Position -->|has previous position| Position
        Position -->|has ordering information| Ordering["Timestamp and ingestion sequence"]
        Scope -->|is scoped to| Project
        Run -->|participates in| Scope
    end

    subgraph Provenance["Derivation provenance"]
        Analysis["Analysis activity"] -->|uses evidence| Observation
        Analysis -->|uses policy| Policy
        Analysis -->|uses candidate assessment| Assessment
        Analysis -->|uses history| Position
        Assessment -->|was generated by| Analysis
        Selection -->|was generated by| Analysis
        Comparison -->|was generated by| Analysis
        Analysis -->|is associated with| Agent["Responsible software or person"]
    end
```

## Meaning of the relationships

- **Report, run, and assessment have separate identities.** A run can have
  several report artifacts. The same evidence can support assessments under
  different policy versions without replacing earlier results.
- **Definitions are distinct from occurrences.** Response time is a metric
  definition; p90 is a statistic; the Performance gate is a gate definition.
  Their measurements and assessments are individual occurrences. Provider and
  transaction names do not become classes in the shared ontology.
- **Measured subjects have scoped identities.** Transactions and components
  belong to their system/project. Equal display names do not establish identity
  across providers or projects. The “is a kind of” arrows express class
  specialization; other arrows describe relationships between instances.
- **Baseline is a role.** A baseline assessment is an ordinary assessment
  selected for another assessment under a policy. Likewise, a baseline
  observation is an ordinary observation used as a comparison input. These
  diagram nodes do not introduce separate entity identities or mandatory classes.
- **Selection has an explicit result.** A successful selection identifies one
  baseline at the corresponding gate/report level. An unavailable selection has
  a reason and no selected baseline. No selection result means the operation has
  not been recorded, rather than proving that no eligible baseline exists.
- **Predecessor and baseline differ.** History positions include failed and
  unknown reports. Passing-baseline selection follows its versioned policy.
  Gate and report baselines can originate from different reports.
- **Comparability applies to particular inputs.** One pair of reports may
  support a response-time comparison while lacking comparable CPU evidence.
  Compatibility is compatible, incompatible, or unknown under a specified
  policy. A computable numeric difference alone does not establish compatibility.
- **Results retain provenance.** Analysis activities record their inputs and
  policy versions. A derived relationship is accompanied by its selection or
  comparison result, reasons, and evidence references.
- **This is the common core.** Numeric observations are shown explicitly for
  the Performance use case. Additional gates may introduce other evidence/result
  types without changing report, assessment, history, or provenance semantics.

## Semantics reused from official vocabularies

The graph uses plain domain names. The table specifies the proposed formal
alignments; it does not assert that similarly named concepts are equivalent.

| Official vocabulary | Semantics reused | Application in this proposal |
| --- | --- | --- |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) | **Entity**, **Activity**, **Agent**; **used**, **wasGeneratedBy**, **wasDerivedFrom**, **wasAssociatedWith** | Reports, policy versions, assessment results, selections, and comparisons specialize Entity. Runs and analysis specialize Activity. Responsible software/persons use Agent. Generation and input links record provenance; derived-from links are asserted where a result actually derives from an input. |
| [W3C SOSA/SSN](https://www.w3.org/TR/vocab-ssn/) | **Observation**, **ObservableProperty**, **FeatureOfInterest**, **Procedure**; **observedProperty**, **hasFeatureOfInterest**, **usedProcedure**, **hasResult**, **phenomenonTime** | Observation measures a property of a subject using a procedure, with a result and observation time. Metric definitions specialize ObservableProperty. Measured subjects use FeatureOfInterest. Statistic remains an explicit local concept. |
| [QUDT](https://qudt.org/pages/QUDToverviewPage.html) | **QuantityValue**, **Unit**, **QuantityKind**; numeric value and unit semantics | Numeric measurement results carry values and identified units. Quantity kinds describe the quantity measured. Provider units retain their original representation and are mapped only when meaning is verified. Conversion requires an explicitly supported implementation. |
| [W3C RDF Schema](https://www.w3.org/TR/rdf-schema/) | Classes, subclass relationships, labels, comments, property domains and ranges | Define the vocabulary and class specialization. Domain/range declarations express inference semantics; required fields are specified separately. |
| [W3C OWL 2](https://www.w3.org/TR/owl2-overview/) | Selected class/property axioms, including equivalence, disjointness, and inverse relationships when justified | Add only axioms needed by the competency questions. A mapping to a provider term does not automatically justify equivalence or identity. |

## Project-specific semantics

The following require our own definitions rather than being supplied by the
reused vocabularies:

- Software-delivery context: project, system, software version, workload,
  environment, and history scope.
- Report-to-run association and precise source/stored-evidence references.
- Metric statistics, requirements, gate definitions, gate assessments, report
  assessments, and assessment outcomes.
- Baseline-selection policies, eligibility, selection status, and reasons.
- Comparison policies, compatibility decisions, and difference results.
- Chronological history positions, ordering, and predecessor relationships.

Provider-specific mappings, including
[AI-Square](../ai_sqaure_ontology/ai-square-extended.ttl), belong in separate
mapping modules. The shared core must not depend on AI-Square field names or
import its complete class hierarchy. Existing terms are aligned individually
after their meanings have been checked.

## Validation and derivation

[W3C SHACL](https://www.w3.org/TR/2017/REC-shacl-20170720/) supplies validation
semantics, rather than domain concepts: required fields, cardinalities, allowed
outcomes, and value types. Missing comparison context can leave a comparison
unknown while still permitting evidence retrieval.

Deterministic, versioned rules select baselines, evaluate compatibility, compute
differences, and assess gates. The ontology describes the meanings and results
of these operations; it does not by itself implement “latest eligible passing
assessment” selection. Each question above needs example data and an expected
answer, including missing-data and cross-project cases.

**Open decisions:** define history scopes and the context conditions required
by each comparison policy. Adding compatibility restrictions to baseline
eligibility would extend the current policy and requires an approved ADR change.
