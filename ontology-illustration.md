# Ontology schema and knowledge-base instances

This illustration uses proposed names, not an implemented ontology.

## Schema: what kinds of things and properties exist?

Like the AI-Square overview, this diagram shows **classes**, not instances.
Rows inside a box show datatype properties and their value types. Labeled
arrows show object properties between instances of the connected classes.
Grouping properties inside a class box is a drawing convention; RDF properties
are defined separately from classes.

```mermaid
classDiagram
    direction LR
    class Report {
        dateTime generated_at
        string project_name
    }
    class Result {
        string outcome
    }
    Result --> Report : assesses_report
```

Read the arrow as: “A Result instance can assess a Report instance.” It is
similar to a foreign key from a Result table to a Report table. This diagram
does not specify required fields or cardinalities.

In the AI-Square image, hollow triangle arrows represent **subclass-of**
(inheritance), labeled association arrows represent **object properties**, and
`1` / `*` indicate multiplicities. Such annotations express the intended schema;
whether the ontology formally encodes or validates them must be checked separately.

## Data: which particular things exist, and what do we know about them?

This graph draws all six example RDF statements. Each arrow is a property;
its source is the statement's subject and its destination is the object.
`rdf:type` links an instance to its class. Literal values are shown in rounded
boxes, instances in rectangular boxes, and classes in hexagonal boxes.

```mermaid
flowchart LR
    reportInstance["report_42 (instance)"]
    resultInstance["result_99 (instance)"]
    reportClass{{"Report (class)"}}
    resultClass{{"Result (class)"}}
    generatedAt("2026-10-19T10:00:00Z (dateTime literal)")
    projectName("Checkout (string literal)")
    outcome("pass (string literal)")

    reportInstance -.->|rdf:type| reportClass
    reportInstance -->|generated_at| generatedAt
    reportInstance -->|project_name| projectName
    resultInstance -.->|rdf:type| resultClass
    resultInstance -->|outcome| outcome
    resultInstance -->|assesses_report| reportInstance
```

For example, `result_99 -- assesses_report --> report_42` is one concrete
statement. `Result -- assesses_report --> Report` in the schema diagram
describes the kinds of things that can participate in that relationship.

The same instances can also be drawn in a compact, row-like form. Here the
rows contain **actual values**, rather than the schema's property types:

```mermaid
flowchart LR
    resultInstance["result_99 : Result<br/>outcome = pass"]
    reportInstance["report_42 : Report<br/>generated_at = 2026-10-19T10:00:00Z<br/>project_name = Checkout"]
    resultInstance -->|assesses_report| reportInstance
```

The last two diagrams describe the same data. The compact drawing folds the
literal-value statements and class memberships into the instance boxes.
