# 13. Use an ontology-based knowledge base as the data layer

Date: 2026-11-16

## Status

Accepted; supersedes 0002 model and 0008 storage

## Context

History, baselines and outcomes live only in Python code and in SQLite
evidence-pack JSON blobs. The LLM cannot trace why a report passed.
AI-Square already models staging data as an RDF knowledge graph queried with
SPARQL ([Mosquera et al., 2025](https://ceur-ws.org/Vol-3959/PT-paper3.pdf)).

## Decision

- The release-compass ontology is the data model: `release-compass:` terms
  plus reused `ai2core:` terms, declared in OWL/RDFS Turtle
  (`ontology/release-compass.ttl`).
- Data is stored as RDFLib graphs in Turtle files. `facts.ttl` holds ingested
  report facts and is never rewritten. `assessment-<version>.ttl` holds the
  derived results of one assessment version.
- Metric scoring stays in Python (ADR 0012) and writes
  `release-compass:MetricAssessment` triples.
- Previous-report links, gate and report outcomes, and baselines are SPARQL
  UPDATE rules, applied report by report in chronological order.
- The LLM reads the graph only through fixed, tested SPARQL tools, one per
  competency question. It never writes SPARQL.
- Reused `ai2core:` properties whose domain or range would infer unwanted
  classes are replaced by `release-compass:` properties.

## Alternatives

- **Keep SQLite and add an RDF export.** Rejected: two models to keep in sync.
- **Score in SPARQL.** Rejected: three-valued weighted scoring is hard to
  test in SPARQL.
- **Let the LLM write SPARQL.** Rejected: answers would be neither
  deterministic nor verifiable.
- **Server triple store (e.g. Apache Jena Fuseki).** Rejected for now: the
  data scale does not need it.

## Consequences

Supersedes the canonical dataclass model of ADR 0002 and the storage part of
ADR 0008. ADR 0005 and 0006 keep their rules, now implemented in SPARQL.
Adds the `rdflib` dependency. Time series and violation periods are no longer
exposed to the LLM.
