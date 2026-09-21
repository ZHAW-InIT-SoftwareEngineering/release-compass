# Release Compass Architecture

Release Compass provides evidence-grounded quality-gate assessments through a
conversational interface. The architecture separates language-model work from
deterministic analysis so that an assessment is reproducible and its evidence
can be inspected.

The first proof of concept implements the **Performance** gate. This is an
example gate, not an architectural special case: the same flow supports other
metric domains (for example, Security or Functional Suitability) by supplying
their report adapter, baseline policy, comparison rules, and thresholds.

The source diagram is [release-compass-architecture.drawio](release-compass-architecture.drawio).

## Components

| Layer | Responsibility |
| --- | --- |
| Client layer | The Report UI / Chat Interface supplies a user question and run context, then displays the response. |
| Conversational agent | An exchangeable LLM interprets the request and synthesizes the response. It invokes a metric-analysis tool when evidence is needed; it does not calculate gate results itself. |
| Deterministic metric analysis | Normalizes reports, selects a baseline, compares metrics, and constructs a structured evidence pack. This layer applies gate rules and is the source of the assessment facts. |
| Data and configuration | Current and historical reports provide observations. Gate configuration provides the metric definitions, thresholds, and policies used for normalization and assessment. |

## Request and evidence flow

1. A user asks a question in the UI with the run context.
2. The LLM determines whether a metric comparison is required. For the current
   Performance POC it calls `compare_performance(run_id)`.
3. The tool passes the request to deterministic metric analysis. Analysis loads
   the current and historical reports and applies the relevant gate
   configuration.
4. Report normalization creates a common representation for the selected
   metric domain. Baseline selection chooses the configured reference set.
5. Metric comparison evaluates the normalized current values against the
   baseline and configured thresholds.
6. The evidence-pack builder returns a structured evidence pack to the tool.
   The LLM uses that result to produce an evidence-grounded response in the UI.

## Metric-independent gate contract

Each gate is an implementation of the deterministic-analysis boundary. A gate
must define:

- how its reports are retrieved and normalized;
- the compatible baseline-selection policy;
- the metrics and comparison rules it evaluates;
- thresholds or other configuration used to classify the result; and
- the evidence and provenance returned in its evidence pack.

The shared agent and client layers depend only on the tool and evidence-pack
contract. Adding a gate should therefore extend the analysis and configuration
layers without requiring the LLM to learn or reimplement the gate logic.

## Performance POC

The Performance gate initially compares a run with a selected baseline using
performance reports. Its defined metrics and scope are recorded in
[the POC goals](../poc_goals/POC_GOALS.md). The gate returns the current value,
baseline value, delta, applicable thresholds, and source provenance in the
evidence pack. See [the tool notes](../tools/tools.md) for the current POC
tool discussion and [the discussion record](../discussions/01_discussions.md)
for open decisions such as the baseline policy.

## Architectural constraints

- **Deterministic assessments:** gate calculations, threshold evaluation, and
  evidence construction are outside the LLM.
- **Evidence-grounded answers:** responses must be based on the structured tool
  result rather than invented metrics or conclusions.
- **Exchangeable LLM:** the conversational-agent boundary permits self-hosted
  and frontier models to be evaluated without changing gate logic.
- **Extensible gates:** new metric domains are added through gate-specific data
  adapters, configuration, and deterministic analysis.
