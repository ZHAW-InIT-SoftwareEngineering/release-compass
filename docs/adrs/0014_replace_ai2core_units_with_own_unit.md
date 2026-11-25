# 14. Replace ai2core:units with release-compass:unit

Date: 2026-11-16

## Status

Accepted

## Context

ADR 0013 reuses AI-Square terms unless their domain or range would infer
unwanted classes. Both metrics and targets carry a unit. AI-Square declares
`ai2core:units` with two domains, `ai2core:Metric` and `ai2core:Target`
([ai-square-extended.ttl](../implementation/ai_sqaure_ontology/ai-square-extended.ttl)).
In RDFS, several `rdfs:domain` values apply together, not as alternatives
([RDF Schema 1.1, §4.1](https://www.w3.org/TR/rdf-schema/#ch_domain)). Any
subject with a unit would therefore be both a metric and a target.

## Decision

- Metrics and targets state their unit with `release-compass:unit`
  (`xsd:string`, functional). It has no `rdfs:domain`, because two classes
  share it.
- `ai2core:units` is not used.
- The same rule applies to other properties shared by several classes
  (`release-compass:metric_name`, `outcome`, `reason`): they declare a range
  but no domain.

## Alternatives

- **Reuse `ai2core:units`.** Rejected: a reasoner would type every measured
  metric as a target, and queries by class would return wrong results.
- **One unit property per class** (e.g. `metric_unit`, `target_unit`).
  Rejected: scoring compares the two units for equality (ADR 0012), which is
  simpler with one property.
- **Declare the domain as `owl:unionOf`.** Rejected for now: no reasoner is
  used, and a missing domain infers nothing wrong.

## Consequences

The diagram, the vocabulary and the mappers use `release-compass:unit`.
`tests/ontology/test_release_compass.py` fails if a mapper writes a term that
the vocabulary or AI-Square does not declare. Data stays compatible with
AI-Square classes, but tools that expect `ai2core:units` do not find units.
