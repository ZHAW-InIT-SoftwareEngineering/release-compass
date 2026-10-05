# Release Compass: Evidence and Harness Roadmap

## Purpose and target behavior

Build an auditable agent that explains release-quality evidence accurately, uses only authorized data, terminates within a fixed budget, and can be evaluated under controlled conditions. The harness is the runtime around the model: it constructs context, dispatches tools, enforces access policies, records execution, validates outputs, and handles completion and failure.

For the Performance POC, a user supplies a question and a current/baseline report pair. Deterministic code compares compatible metrics and applies configured assessment rules. The agent retrieves the resulting evidence and produces an explanation with traceable factual claims. Preserve the distinction between a metric changing, a configured threshold being violated, and a release being eligible for promotion. The model must not invent a release decision from an incomplete performance comparison.

The goal is a small, reusable harness with domain-specific evidence readers and validators. Keep metric calculations, baseline compatibility, thresholds, and gate semantics in Release Compass's application/domain layers.

**Status:** this document is an implementation proposal and backlog, not an accepted architecture decision. Existing ADRs remain authoritative. Resolve and record new architecture decisions before implementing the affected milestone.

## Read these first

- [POC goals and performance evidence contract](docs/implementation/poc_goals/POC_GOALS.md)
- [Architecture and deterministic/LLM responsibilities](docs/implementation/architecture_overview/ARCHITECTURE.md)
- [ADR 0001: exchangeable OpenAI-compatible model client](docs/adrs/0001_use_openai_compatible_llm_client.md)
- [ADR 0002: external report ingestion boundary](docs/adrs/0002_use_hexagonal_boundry_for_ingestion.md)
- [ADR 0003: compare matching gates by report ID](docs/adrs/0003_compare_gates_by_report_id.md)
- [ADR 0004: string IDs at the model-facing boundary](docs/adrs/0004_use_string_ids_at_model_tool_boundary.md)

Current implementation starting points:

| File | Current responsibility | Planned extension |
| --- | --- | --- |
| [src/harness/graph.py](src/harness/graph.py) | Minimal model/tool loop | Bounded execution, explicit states, validation and explanation stages |
| [src/harness/tools/compare_performance.py](src/harness/tools/compare_performance.py) | Host-built comparison tool accepting string IDs | Evidence contract, authorized scope, structured errors and tracing |
| [src/harness/system/system_prompt.py](src/harness/system/system_prompt.py) | Supplies report IDs | Clear task, fixed baseline context, evidence and output instructions |
| [src/application/use_cases/compare_gate.py](src/application/use_cases/compare_gate.py) | Loads reports and performs the comparison | Preserve deterministic analysis boundary |
| [src/domain/deltas/comparison.py](src/domain/deltas/comparison.py) | Computes numeric deltas | Explicit metric interpretation outside the model |
| [src/domain/gates/performance/performance_gate.py](src/domain/gates/performance/performance_gate.py) | Canonical performance evidence | Source identity, units, thresholds and supporting evidence |
| [src/configs/llm/llm_config.py](src/configs/llm/llm_config.py) | Model configuration | Versioned evaluation settings and suitable output limits |
| [src/agent.py](src/agent.py) | Interactive entry point and wiring | Separate interactive sessions from independent evaluation runs |

## 1. Publish a complete, compact evidence contract

**Problem:** the comparison tool currently returns numeric baseline/current/delta values. Canonical gate snapshots retain richer information that the model does not receive. Numbers without units, source identity, thresholds or metric direction are insufficient for a reliable explanation.

### Tasks

- [ ] Define a versioned evidence-pack schema with pack ID, current/baseline report IDs, gate type, source hashes, comparison-policy version, and evidence-item IDs.
- [ ] For each metric include its field path, source, unit, current value, baseline value, absolute delta, observation count, observation window, and applicable thresholds/statuses.
- [ ] Compute relative deltas deterministically only where meaningful; explicitly represent undefined cases such as a zero baseline.
- [ ] Keep categorical statuses separate from numeric changes. Encode metric direction explicitly where it has been established; do not assume every increase is worse.
- [ ] Preserve missing values and missing-side comparisons. Missing evidence must not become zero or an implicit pass.
- [ ] Resolve baseline compatibility and ownership. Start with explicit report pairs under ADR 0003; automatic baseline selection requires its own decision.
- [ ] Return a compact summary with evidence IDs. Provide bounded retrieval of supporting details only if the POC needs them; avoid placing complete HTML reports in context.
- [ ] Validate newly read external inputs at their entry boundaries through private validation helpers. Downstream processing should rely on validated canonical inputs.

**Done when:** a fixed report pair produces a reproducible pack whose metrics, units, deltas, statuses and provenance can be verified without asking a model. Incompatible comparisons and missing evidence have explicit outcomes.

## 2. Bound execution and enforce evidence access in code

### Tasks

- [ ] Define immutable run context: run ID, authorized report IDs, selected gate, baseline policy, evidence build ID, optional as-of timestamp, information profile, and budget configuration.
- [ ] Bind readers and run policies into tool factories. The model supplies simple identifiers/ranges, never repositories, credentials or policy settings.
- [ ] Enforce separate limits for model turns, individual tool calls, output size and elapsed time. Define how retries and malformed calls consume limits.
- [ ] Handle multiple tool calls in one model response without exceeding the remaining budget. Persist counters across resume.
- [ ] Use structured tool errors for invalid arguments, unauthorized reports, unavailable evidence and exhausted budgets. Choose which errors are recoverable and bound repair attempts.
- [ ] Record explicit terminal states, including completed, invalid output, exhausted budget, provider failure and evidence failure. Do not silently label a fallback answer successful.
- [ ] Trace accepted, rejected, failed and truncated requests. Check authorization and budget before reading data; log the outcome even when execution is refused.

For retrospective assessments, add an evidence adapter with observation time, availability time and revision identity. Serve only evidence available at the fixed as-of timestamp, selecting the latest eligible revision. Apply eligibility **before** computing summaries or selecting historical baselines. Record requested and served ranges plus any truncation. Distinguish assumed availability from independently verified publication history.

Introduce two controlled information profiles: numerical evidence with provenance, and the same numerical evidence plus approved source text and metric explanations. Verify that shared values remain identical and text cannot bypass availability rules. Keep this profile mechanism separate from gate logic.

**Done when:** deterministic tests prove that malformed IDs, unauthorized reports, future/unavailable revisions, hidden-profile fields and over-budget calls never reach the model. Include boundary timestamps, same-day observations, batched calls and resume cases.

## 3. Separate authoritative assessment from explanation

### Tasks

- [ ] Freeze the deterministic assessment and retrieved evidence before the final explanation stage.
- [ ] Generate the final explanation without further tool access. If evidence is insufficient, return that limitation explicitly.
- [ ] Define structured output containing assessment reference, evidence summary, factual claims with evidence IDs, interpretation, and limitations.
- [ ] Validate the output schema, evidence references, cited values/units, and agreement with the authoritative assessment.
- [ ] Distinguish factual claims from interpretation. A valid evidence ID alone does not prove that a claim is supported.
- [ ] Establish a grounding rubric covering correct numbers, comparisons, units, threshold interpretation, source identity, availability and uncertainty. Review a labeled sample manually before relying on automated semantic grading.
- [ ] Define bounded behavior for invalid explanations. Preserve every failed attempt and distinguish any correction from the original output.

Keep three artifacts separate: the deterministic assessment, the generated explanation, and the explanation-validation result. An explanation-quality rule may flag or withhold presentation, but it must not silently rewrite the underlying gate assessment. Any policy that affects release eligibility needs explicit ownership and versioning.

**Done when:** unsupported claims, wrong units, invented thresholds and contradictory explanations are detected in labeled cases. The interface can show the assessment and its explanation-quality status independently.

## 4. Persist auditable runs and support controlled recovery

### Tasks

- [ ] Export a versioned run record containing exact initial context, ordered visible messages and tool results, accepted assessment, explanation, validation results, terminal status and timing.
- [ ] Record model/provider/endpoint identifiers, decoding settings, SDK versions, code revision, prompt/tool-schema versions, evidence hashes, budgets, retry attempts and reported token usage. Exclude secrets and do not assume access to hidden model reasoning.
- [ ] Store checkpoints separately from the audit export. Checkpoints support recovery; the run record supports inspection and evaluation.
- [ ] Resume with the same immutable run policies and evidence build. Verify their identity before continuing and preserve counters and completed stages.
- [ ] Give each independent repeat a fresh run/thread and fresh conversation. Never inherit another evaluation run's memory or previous answer.
- [ ] Support regeneration of only the explanation from a frozen assessment and trace. Save it as a separate variant linked to its parent run.
- [ ] Support offline trace inspection and deterministic reassessment of saved artifacts under a named validation policy.

A resumed or regenerated run may call the provider again and produce different text. It is not exact replay. Exact inspection reuses saved outputs; deterministic re-evaluation recomputes code-based checks without model calls.

**Done when:** an interrupted run resumes without losing its policy or budget, its exported evidence can be inspected independently of checkpoints, and explanation variants cannot overwrite original records.

## 5. Build behavioral evaluations before scaling up

Stable output is insufficient: a model that repeats the same answer while ignoring changed evidence can appear reliable. Measure grounding, correctness and evidence sensitivity alongside repeatability.

### Evaluation cases

| Experiment | Hold fixed / change | Measure |
| --- | --- | --- |
| Repeated runs | Same reports, prompt, model and settings; independent contexts | Factual agreement, claim support, retrieval variation, latency, tokens and failures |
| Evidence sensitivity | Change one relevant metric or threshold across paired synthetic reports | Correct recognition of the change and agreement with deterministic assessment |
| Prompt anchoring | Identical evidence; neutral versus favorable/unfavorable user framing | Unsupported shifts in interpretation or stated assessment |
| Meaning-preserving perturbation | Reorder metrics, change equivalent wording or formatting | Assessment consistency and grounding |
| Missing/conflicting evidence | Remove values or introduce incompatible windows/units | Explicit uncertainty and rejection of invalid comparisons |
| Temporal canaries | Place recognizable items beyond the allowed availability boundary | No forbidden item in tool responses, context or cited evidence |
| Information profiles | Identical shared numeric values; add approved text | Changes in interpretation, grounding and retrieval without numeric drift |
| Budget/error recovery | Exhaust limits, return invalid IDs, inject provider failures | Bounded retries and accurate terminal states |
| Explanation regeneration | Fixed assessment and retrieval trace; new explanation calls | Report variability independently of retrieval variability |
| Validation-policy sensitivity | Same saved outputs; different named checking policies | Which outputs pass and why, without rerunning inference |

### Tasks

- [ ] Create small synthetic fixtures with known expected comparisons, metric directions and statuses. Start with pass, violation, missing-data and incompatible-report cases.
- [ ] Test runtime invariants with a scripted model so these checks need no inference service.
- [ ] Keep live-model evaluation separate. Begin with a small pilot to estimate repeat counts, token limits and cost before choosing the frozen evaluation protocol.
- [ ] Record fixture count, independent-run count, failures and uncertainty. Do not discard provider errors from the denominator without reporting them.
- [ ] Freeze prompts, model settings, budgets, scoring rubric and acceptance criteria before the evaluation set is run. Use separate development cases.
- [ ] Label changes made after observing results as new exploratory experiments; retain original results.
- [ ] Use private or newly generated evidence for tests of reliance on supplied evidence. Hiding dates or names does not establish absence of model memorization.

**Done when:** one command runs the deterministic suite and a separate explicit command runs the configured live evaluation. Results distinguish retrieval failures, assessment errors, unsupported explanations and infrastructure failures.

## 6. Manage context deliberately and keep reuse small

- [ ] Construct the initial context from the task, authorized report pair, gate description, policies and output contract. Remove contradictory baseline instructions.
- [ ] Bound tool-result sizes and return explicit truncation indicators. Preserve units, source IDs, thresholds and missingness when producing summaries.
- [ ] Keep full raw evidence in the audit artifacts even when only a compact representation is sent to the model.
- [ ] Start short evaluation runs without automatic model-generated compaction. If compaction becomes necessary, version and log the transformation and evaluate its effect on grounding.
- [ ] Keep cross-run memory disabled for independent evaluations. Interactive conversation history must not leak into batch runs.
- [ ] Implement the reusable pieces inside `src/harness/` first: run context, dispatcher, trace, output-validation hooks and run records.
- [ ] Keep ingestion, comparison and Performance gate semantics in their existing layers. Extract a shared library only after another concrete adapter demonstrates the same runtime requirements.

**Done when:** another evidence adapter can use the execution and audit mechanisms without importing Performance gate logic or changing the core loop.

## Using the Claude Code leak as a blueprint

Use the Claude Code leak as architectural reading material for the surrounding runtime. Record the exact source revision inspected and link each proposed mechanism to a source location. No specific leaked implementation has been verified by this roadmap.

Study these questions:

1. Where does the runtime dispatch tools, validate arguments and enforce access?
2. What defines completion, cancellation, retry and failure?
3. Which events are persisted, and how are sessions resumed?
4. How is context selected, limited or transformed before each model request?
5. How are runtime changes tested independently from model changes?

Implement only mechanisms that satisfy the milestones above, with tests demonstrating their effect. Shell access, broad filesystem access, background autonomy and multi-agent orchestration are unnecessary for this evidence-explanation POC. Prefer an independently implemented, provider-neutral design over importing a coding assistant's entire runtime.

Public sources that can substantiate the patterns independently of a leaked mirror:

- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works): model/tool loop, context, sessions and recovery.
- [Hooks reference](https://code.claude.com/docs/en/hooks): lifecycle interception and checks outside model reasoning.
- [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): selecting useful context and managing growing histories.
- [Anthropic's April 2026 quality postmortem](https://www.anthropic.com/engineering/april-23-postmortem): prompt, reasoning-setting and context-management changes affected quality even though the inference layer was unaffected. Treat harness configuration as part of the evaluated system.

## Recommended implementation order

1. **Evidence first:** publish the compact evidence schema and verify it on fixed report pairs.
2. **Explanation next:** produce structured claims, validate references and establish the grounding rubric.
3. **Controlled runtime:** enforce budgets/access, explicit failures and durable run records.
4. **Small evaluation pilot:** run evidence sensitivity, anchoring, repeats and grounding checks.
5. **Extended controls:** add as-of/revision fixtures, information profiles and recovery tests.
6. **Freeze and scale:** resolve acceptance-policy ownership, record decisions and execute the frozen evaluation suite.

The first milestone is complete when a fixed report pair yields an explanation whose factual claims refer to identifiable evidence, preserve missing values, and agree with deterministic comparison results. Complete that vertical slice before adding gates, retrieval infrastructure or complex orchestration.

For each milestone, propose the relevant ADR, implement focused changes, add meaningful tests aligned with source paths, and run the applicable checks with Python 3.14+ and `uv`. If a new dependency is necessary, follow [AGENTS.md](AGENTS.md): provide the exact direct-package `uv add` command and wait for the developer to install it and authorize continuation.
