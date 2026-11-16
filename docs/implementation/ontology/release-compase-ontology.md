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

## KISS ontology

Rendered from the hand-drawn sketch [ontology.png](ontology.png). Classes
prefixed `ai2core:` are reused from AI-Square
([ai-square-extended.ttl](../ai_sqaure_ontology/ai-square-extended.ttl)) with
their declared attributes; `release-compass:` marks the release-compass
extension, including attributes added to reused classes. Its namespace IRI is
`https://github.com/ZHAW-InIT-SoftwareEngineering/release-compass/ontology#`.
Mermaid relation labels cannot contain a colon, so `precedes (ai2core)` means `ai2core:precedes`. `ai2core:has_id`
applies to every class and is omitted.

```mermaid
%%{init: {"class": {"rankSpacing": 120, "nodeSpacing": 80}}}%%
classDiagram
    direction TB

    class Report["release-compass:Report"] {
        +release-compass:generated_at xsd:dateTime
        +release-compass:ingestion_sequence xsd:integer
        +release-compass:is_root xsd:boolean
        +release-compass:outcome Outcome
        +release-compass:source_fingerprint xsd:string
        +release-compass:source_path xsd:string
    }
    class QualityGate["ai2core:QualityGate"] {
        +release-compass:executed_at xsd:dateTime
        +release-compass:outcome Outcome
    }
    class Requirement["ai2core:Requirement"] {
        +ai2core:criticality xsd:string
        +ai2core:created_on xsd:integer
        +ai2core:last_modified_on xsd:integer
        +ai2core:remote_url xsd:anyURI
    }
    class Target["ai2core:Target"] {
        +ai2core:aggregation xsd:string
        +ai2core:units xsd:string
        +release-compass:description xsd:string
        +release-compass:min xsd:decimal
        +release-compass:max xsd:decimal
        +release-compass:min_score xsd:decimal
    }
    class Metric["ai2core:Metric"] {
        +ai2core:units xsd:string
        +release-compass:metric_name xsd:string
        +release-compass:value xsd:decimal
        +release-compass:statistic xsd:string
        +release-compass:request_count xsd:integer
        +release-compass:excluded_reason xsd:string
    }
    class MetricAssessment["release-compass:MetricAssessment"] {
        +release-compass:score xsd:decimal
        +release-compass:outcome Outcome
        +release-compass:reason xsd:string
        +release-compass:policy_version xsd:string
    }
    class Source["ai2core:Source (transaction)"]
    class Outcome["release-compass:Outcome"] {
        <<enumeration>>
        pass
        fail
        unknown
    }

    Report "0..1" --> "0..1" Report : previous_report (release-compass)
    Report "*" --> "0..1" Report : baseline_report (release-compass)
    Report "1" --> "1..*" QualityGate : contains_gate (release-compass)
    QualityGate "*" --> "*" QualityGate : precedes (ai2core)
    QualityGate "1" --> "1..*" Target : evaluated_by_requirement (ai2core)
    QualityGate "*" --> "0..1" QualityGate : baseline_gate (release-compass)
    QualityGate "1" --> "*" Metric : produces_metric (release-compass)
    QualityGate "1" --> "1..*" MetricAssessment : has_assessment (release-compass)
    MetricAssessment "*" --> "1" Target : assesses (release-compass)
    MetricAssessment "1" --> "*" Metric : based_on (release-compass)
    Metric "*" --> "1" Source : measured_from (release-compass)
    Requirement <|-- Target
```

Changes from the sketch:

- **One `QualityGate` node.** `ai2core:QualityGateExecution` is merged into
  `ai2core:QualityGate`, which takes its `release-compass:executed_at` and `release-compass:outcome`. A
  `QualityGate` instance is one gate run within a report, so
  `ai2core:evaluates` is dropped and `release-compass:contains_execution` and
  `release-compass:baseline_execution` become `release-compass:contains_gate` and `release-compass:baseline_gate`.
  `release-compass:produces_metric` replaces `ai2core:produces_metric`, whose domain
  `ai2core:QualityGateExecution` would otherwise be inferred for every gate.
- **One `Target` node.** The two `RequirementTarget` boxes are merged.
  `ai2core:Target` is a subclass of `ai2core:Requirement`, so it is a valid
  range of `ai2core:evaluated_by_requirement`. A gate has several targets (one
  per metric, ADR 0012), so the cardinality is `1..*`, not `1:1`.
- **Assessing a metric.** `ai2core:aggregation` (e.g. `p90`) and the
  `release-compass:min`/`release-compass:max` range answer “how is a metric assessed?” (ADR 0012).
  A metric matches its target when `release-compass:statistic` equals the aggregation and
  the units are equal. `description` and the range are `release-compass:` additions, since
  AI-Square declares neither on `Target`.
- **Assessment results are their own class.** Scoring (ADR 0012) writes one
  `release-compass:MetricAssessment` per gate and target, with its score,
  outcome, reason, and policy version. It links the target (`assesses`) to
  the metrics it scored (`based_on`), replacing the direct
  `Metric`–`Target` link, so results of different policy versions can coexist
  (ADR 0013).
- **Provenance and exclusions.** `release-compass:source_fingerprint` and
  `release-compass:source_path` identify a report's HTML source (ADR 0008).
  `release-compass:metric_name` names what a metric measures, and
  `release-compass:excluded_reason` records why a metric was left out of
  scoring, e.g. a zero-request transaction (ADR 0012).
- **Metric is a measurement.** It is produced by one gate run
  (`release-compass:produces_metric`, `1:*`), not shared `n:n` between gates.
- **Metric maps directly to Source.** `ai2core:Observable` is removed.
  `release-compass:measured_from` links each metric to its measured transaction for
  per-transaction scoring. `ai2core:yield_from` is not reused because its
  domain `ai2core:Observable` would reintroduce the removed class.
- **Predecessor instead of child.** `release-compass:previous_report` with `release-compass:is_root`
  keeps stored reports immutable when a new report arrives (ADR 0006, ADR 0008).
- **Rules, not ingested facts.** Gate and report `release-compass:outcome`,
  `release-compass:previous_report`, and the baselines are derived by SPARQL
  UPDATE rules into the assessment graph, never into the report facts
  (ADR 0013). Report `release-compass:outcome` is the conjunction of its
  gate outcomes (ADR 0005). `release-compass:baseline_report` and `release-compass:baseline_gate` are
  selected by the latest-passing rule (ADR 0006); without a separate gate
  definition, gates are comparable when they are evaluated by the same
  targets.
- **Not reused.** `ai2core:evaluated_by` is declared twice with different
  domains, so only `ai2core:evaluated_by_requirement` is used.

## Tech stack

AI-Square models its knowledge graph in RDF, maps source data to it with
RML/YARRRML, and lets agents query it with SPARQL
([Mosquera et al., 2025](https://ceur-ws.org/Vol-3959/PT-paper3.pdf), §2.3);
its vocabulary is published as OWL in Turtle
([ai-square-extended.ttl](../ai_sqaure_ontology/ai-square-extended.ttl)). The
paper names no triple store. Release-compass follows the same standards:

| Layer | Choice | Purpose |
| --- | --- | --- |
| Ontology language | [OWL 2](https://www.w3.org/TR/owl2-overview/) / [RDFS](https://www.w3.org/TR/rdf-schema/) in [Turtle](https://www.w3.org/TR/turtle/) | `release-compass:` vocabulary in `ontology/release-compass.ttl` that reuses `ai2core:` terms, as in the diagram above. |
| Editor (optional) | [Protégé](https://protege.stanford.edu/) | Visual editing and consistency checks of the `.ttl` file. |
| Data | RDF instance triples | Reports, gates, metrics, and sources as `release-compass:`/`ai2core:` individuals. |
| Mapping | Python ingestion adapters | Existing adapters emit triples directly. [RML/YARRRML](https://rml.io/yarrrml/), as used by AI-Square, is the declarative alternative if mappings should live outside code. |
| Library and store | [RDFLib](https://rdflib.readthedocs.io/) | Parse and serialize Turtle and run SPARQL in-process. Ingested facts live in `facts.ttl`, which is never rewritten; derived results live in one `assessment-<version>.ttl` per assessment version ([ADR 0013](../../adrs/0013_use_ontology_knowledge_base.md)). A server store (e.g. Apache Jena Fuseki) is only needed for shared or large graphs. |
| Query | [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) | One query per competency question above. |
| Validation (optional) | [SHACL](https://www.w3.org/TR/shacl/) via [pySHACL](https://github.com/RDFLib/pySHACL) | Required fields, cardinalities, and allowed `release-compass:Outcome` values. |

[02_discussion.md](../discussions/02_discussion.md) lists
[pyRDF](https://pypi.org/project/pyRDF/), but it is a lightweight RDF stream
parser without SPARQL support, so RDFLib replaces it. Adding RDFLib (and
pySHACL) requires `uv add rdflib` (`uv add pyshacl`).
