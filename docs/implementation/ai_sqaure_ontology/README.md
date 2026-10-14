# AI-Square ontology

![AI-Square ontology structural overview](ai-square-ontology.png)

The image summarizes [ai-square-extended.ttl](ai-square-extended.ttl): 21 core
classes, their declared inheritance, 31 object properties, 18 datatype
properties, and counts for 161 extension classes. Detailed extension hierarchies
and datatype-property domains are omitted.

Multiple domain/range declarations are shown together. In RDFS these imply
membership in every listed class, rather than alternatives; see the
[W3C RDF Schema specification](https://www.w3.org/TR/rdf-schema/#ch_domain).

## Mermaid schema diagram

The diagram uses exact `ai2core` class and property names. Inheritance arrows
point to the superclass; labeled solid arrows show object-property domains and
ranges. Properties with multiple domains or ranges are represented as explicit
`ObjectProperty` nodes with dotted declaration links, preserving the conjunction
semantics described above. `causes` has no declared domain or range.

Class attributes show datatype properties and their value types (`xsd_` means
`xsd:`). Attributes shared across multiple declared domains appear on each class.
`owl:Thing` is shown separately for the global `has_id` property. The diagram
covers the same core schema as the image; the 161 extension classes are summarized
in the image rather than expanded here.

```mermaid
classDiagram
    direction LR
    class Anomaly
    class Descriptive
    class Environment
    class Log
    class Metric
    class TestResult
    class TestCase
    class TestCaseSpecification
    class Model
    class Observable
    class QualityGate
    class QualityGateExecution
    class Requirement
    class RequirementSpecification
    class Capability
    class CapabilityCoverage
    class Action
    class Source
    class SourceSpecification
    class Target
    class Trace
    Target : xsd_string aggregation
    Anomaly : xsd_dateTimeStamp end_time
    Descriptive : xsd_dateTimeStamp end_time
    class OWLThing["owl:Thing"]
    OWLThing : xsd_string has_id
    Anomaly : xsd_string severity
    Anomaly : xsd_dateTimeStamp start_time
    Descriptive : xsd_dateTimeStamp start_time
    Log : xsd_string status
    Metric : xsd_string units
    Target : xsd_string units
    Requirement : xsd_integer created_on
    Requirement : xsd_integer last_modified_on
    Requirement : xsd_string criticality
    Requirement : xsd_anyURI remote_url
    Action : xsd_anyURI remote_url
    Capability : xsd_string description
    Capability : xsd_string confidence
    CapabilityCoverage : xsd_string confidence
    Capability : xsd_boolean coverage
    CapabilityCoverage : xsd_string covers_step
    CapabilityCoverage : xsd_string reason
    Capability : xsd_string reason
    Capability : xsd_long extracted_on
    Model : xsd_string version
    Observable <|-- Anomaly : subClassOf
    Observable <|-- Log : subClassOf
    Observable <|-- Metric : subClassOf
    Observable <|-- TestResult : subClassOf
    Source <|-- TestCase : subClassOf
    Requirement <|-- Target : subClassOf
    Observable <|-- Trace : subClassOf
    class property_affects["affects"]
    <<ObjectProperty>> property_affects
    property_affects ..> Anomaly : rdfs_domain
    property_affects ..> Observable : rdfs_range
    property_affects ..> Source : rdfs_range
    Source --> Source : calls
    class property_causes["causes"]
    <<ObjectProperty>> property_causes
    note for property_causes "No declared domain or range"
    Source --> Source : depend_on
    Anomaly --> Model : detected_by
    QualityGate --> Requirement : evaluated_by
    class property_evaluates["evaluates"]
    <<ObjectProperty>> property_evaluates
    property_evaluates ..> QualityGate : rdfs_domain
    property_evaluates ..> TestCase : rdfs_domain
    property_evaluates ..> QualityGateExecution : rdfs_range
    property_evaluates ..> Requirement : rdfs_range
    QualityGate --> QualityGate : precedes
    QualityGateExecution --> Observable : produce
    QualityGateExecution --> Observable : produces
    QualityGateExecution --> Metric : produces_metric
    QualityGateExecution --> Log : produces_log
    QualityGateExecution --> TestCase : produces_test_case
    QualityGateExecution --> Anomaly : produces_anomaly
    Environment --> Environment : stages_to
    Observable --> Source : yield_from
    Requirement --> Target : contains_target
    Requirement --> Requirement : linked_requirement
    Requirement --> TestCase : verifying_test_case
    Requirement --> Capability : has_capability
    Capability --> CapabilityCoverage : has_coverage
    CapabilityCoverage --> TestCase : tests
    TestCase --> Action : includes
    Capability --> Model : extracted_by
    class property_specifies["specifies"]
    <<ObjectProperty>> property_specifies
    property_specifies ..> RequirementSpecification : rdfs_domain
    property_specifies ..> TestCaseSpecification : rdfs_domain
    property_specifies ..> SourceSpecification : rdfs_domain
    property_specifies ..> Requirement : rdfs_range
    property_specifies ..> TestCase : rdfs_range
    property_specifies ..> Source : rdfs_range
    RequirementSpecification --> Requirement : specifies_requirement
    TestCaseSpecification --> TestCase : specifies_test_case
    QualityGate --> Requirement : evaluated_by_requirement
    TestCase --> Requirement : evaluates_requirement
    class property_affects_source["affects_source"]
    <<ObjectProperty>> property_affects_source
    property_affects_source ..> Anomaly : rdfs_domain
    property_affects_source ..> Observable : rdfs_range
    property_affects_source ..> Source : rdfs_range
    QualityGateExecution --> RequirementSpecification : produce_reqspec
    note for OWLThing "Global has_id domain; universal superclass is implicit"
```
