# 16. Self-host the LLM with SGLang

Date: 2026-11-23

## Status

Accepted; refines 0001

## Context

ADR 0001 lets the harness call OpenRouter or a self-hosted model through the
OpenAI-compatible API, but names no server. We want to run a model on a
desktop GPU (RTX 3080), while machines without an NVIDIA GPU keep using
OpenRouter. The harness is agentic: each turn resends a growing conversation
with the same system prompt and tool schemas, and it needs structured
`tool_calls`.

## Decision

- Self-hosted models are served by [SGLang](https://docs.sglang.io/) in
  Docker. Its server "fully implements the OpenAI API"
  ([docs](https://docs.sglang.io/basic_usage/openai_api_completions.html)).
- OpenRouter stays the default. `configs/llm/openrouter.yaml` and
  `configs/llm/sglang.yaml` both exist, and `configs/application/local.yaml`
  selects one. The client code is the same for both (ADR 0001).
- The server is started with the `--tool-call-parser` of the model family,
  e.g. `qwen` for Qwen2.5
  ([docs](https://docs.sglang.io/advanced_features/tool_parser.html)), set
  next to the model in the compose service.

## Alternatives

- **Ollama.** Easiest local setup, but aimed at a single user: in Red Hat's
  benchmark it peaked at 41 tok/s against 793 tok/s for vLLM, even with
  parallelism tuned
  ([source](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking)).
  Rejected: it does not scale to several concurrent users.
- **vLLM.** Equally production-grade and OpenAI-compatible; throughput is
  near parity with SGLang
  ([source](https://developers.redhat.com/articles/2026/10/14/vllm-vs-sglang-choosing-the-right-inference-engine-for-your-workload)).
  SGLang's RadixAttention reuses shared prefixes across requests without
  configuration, which suits multi-turn agent sessions; the measured gain is
  small, about 5-7% in one vendor test
  ([source](https://www.runpod.io/blog/sglang-vs-vllm-kv-cache)). Not
  chosen, but remains a drop-in replacement behind the same API.

## Consequences

- Concurrent users are served by one server with continuous batching.
- Needs an NVIDIA GPU, its driver and the NVIDIA Container Toolkit; it cannot
  run on Apple Silicon, so those machines use OpenRouter.
- 10 GB of VRAM limits the model to about 7-8B parameters, quantized.
- The tool-call parser must match the model; changing the model means
  checking the parser too.
