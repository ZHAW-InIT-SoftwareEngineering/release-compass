# 1. Use the OpenAI-compatible API standard for LLM access

Date: 2026-09-23

## Status

Accepted

## Context

The application must support OpenRouter-hosted models and self-hosted models. Both OpenRouter and vLLM expose OpenAI-compatible APIs.

## Decision

We will use `langchain-openai` and configure `ChatOpenAI` with the selected model, endpoint (`base_url`), and API key. The chosen endpoint determines whether requests go to OpenRouter or the self-hosted model server.

We will rely on the OpenAI API standard and will not introduce an LLM gateway framework at this time.

## Alternatives

- [LiteLLM](https://www.litellm.ai/): a unified client and deployable gateway for diverse provider APIs, routing, and observability.
- [Bifrost](https://github.com/maximhq/bifrost): a deployable OpenAI-compatible gateway with centralized routing and governance.

## Consequences

The model integration remains a small, in-process configuration concern with no additional gateway service to operate. A gateway can be reconsidered if multiple applications require centralized routing, credentials, policies, or observability.
