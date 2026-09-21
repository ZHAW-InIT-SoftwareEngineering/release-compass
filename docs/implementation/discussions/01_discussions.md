Things we need to clarify for the POC and then persist as decisions in ADRs:

1. Scope of the gates
   Here, I suggest focusing on one quality gate: metrics related to performance. Refer to @docs/example_reports/report.html and identify the metrics related to performance, which is a nonfunctional requirement (NFR) in the paper: @docs/papers/initial_paper_david.pdf.

***

2. What triggers the system?
   Here, I want to clarify whether the user asks the agentic system to execute the audit, or whether the audit is triggered in the background, for example through PubSub patterns, and the user only asks about the outcome rather than triggering it.

   If the triggers are external, we need to define a backlog, for example a DB of stored metrics. This might be more complicated. I am unsure here.

***

3. Tools
   We need to define the system's tools. For the POC, I propose using only two tools:

   * `compare_performance(run_id_A, run_id_B)`: This tool ensures QU3 of QV1. See @docs/papers/initial_paper_david.pdf.

     Addition: `run_id_B` might not be needed. We could compare `run_id_A`, meaning the most recent run, with a baseline. The baseline still needs to be defined:

     1. Only the second most recent run
     2. A weighted moving average
     3. A simple average

     This assumes that a minimal API is available in the AI-Square project. It must provide the performance run metrics, or at least all report metrics, so we can deterministically reduce them to the ones related to performance.

     From what I identified in the report, these metrics are available and, in my opinion, related to performance:

     * Response time: mean, p90, max
     * Throughput / TPS
     * Failure rate
     * CPU
     * Memory

     Memory and CPU still need to be defined, meaning where they are measured.

   * `get_performance_evidence(run_id)`: This tool ensures several identified and required points from the paper's goal model. See @docs/papers/initial_paper_david.pdf:

     * The staging decision is understood
     * Confidence in the decision
     * Decision consistency

   [Tool Decision File](../tools/tools.md)

***

4. LLM
   What LLM do we want to use? Also, what is our budget?

   Here, I would suggest sticking with OpenRouter (https://openrouter.ai/). The benefit is that we can easily exchange the

***

Decisions after the meeting w/ David on the 21.09.2026: 

1. Architecture should be designed in a way that gates can be extended i.e. new gates i.e. a `Security Gate` could be easily added. 
2. LLM must be echangable i.e. use a self-hosted as well as a forntier closed-source one (i.e. for experimentation)
3. Design: I (Cyril) am free to choose wht framworks etc. I will use if they are able to fullfil the workflow and that we are in charge of the hosting etc. 
4. Start with a implementation of the POC defined in [Workflow Diagram](../architecture_overview/release-compass-architecture.drawio) respectively [Architecture Diagram](../architecture_overview/release-compass-architecture.drawio)
5. W.r.t the data: I (Cyril) need to tell David what reports I need (i.e. 1x Passed, 1x Failed) because we decised in having this data static available and not directly accessing the Partner Projects API

