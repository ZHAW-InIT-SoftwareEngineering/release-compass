# Release Compass: Next Ideas

This file tracks possible extensions to the current POC. The current implementation already imports reports, assesses gates deterministically, selects baselines, persists immutable evidence packs in SQLite, and exposes report and gate evidence through tools. The ideas below are future work, not accepted architecture decisions; update the relevant ADR before changing a covered design decision.

## Human approval and CI/CD showcase

Add an approval step for a proposed release action. The agent can request approval through a tool call; a human approves or rejects the pending action. After approval, trigger a CI/CD pipeline and advance the run.

The workflow needs durable checkpointing because it can pause while waiting for a person. Store checkpoints in a separate SQLite database file, using the same SQLite engine as report/evidence persistence. Capture the pending run, approval state, and enough context to resume safely after restart.

For a POC demonstration, let the pipeline perform a visible action such as sending an email or posting a notification. Keep this separate from actual release eligibility: the existing deterministic assessment remains authoritative, and approval controls whether a follow-up action runs.

## Behavioral evaluation and explanation validation

Build a small evaluation set to check that explanations follow the evidence pack, respond correctly when evidence changes, and state uncertainty when evidence is missing or incompatible. Start with scripted model responses and synthetic reports so runtime checks do not require a live model.

A later extension could produce structured claims tied to evidence IDs and validate their references, values, units, and consistency with the deterministic outcome. Keep the assessment, generated explanation, and explanation validation as separate records.

## MarkItDown document reading

Explore adding Microsoft MarkItDown as a document-reading tool so the agent can analyze PDFs and HTML as Markdown alongside the existing report evidence tools. MarkItDown converts document content; it does not preserve visual layout faithfully.

A possible integration is to run Microsoft's `markitdown-mcp` server locally over stdio, connect it through LangChain's MCP adapter, and add its converted tool to the agent's tool list. Keep this as general document reading; report ingestion and deterministic gate assessment stay in Release Compass's existing layers.

### License, cost, and access

MarkItDown and its MCP server are available under the MIT License. Retain the copyright and license notice when distributing them, and review transitive dependency licenses separately. The conversion tool runs locally without a paid conversion API; the model provider may still charge for usage.

The MCP server can read files accessible to its process and fetch network URLs. Keep it on stdio or localhost and restrict which paths and URLs the agent may submit. A container with limited mounts and permissions can provide additional isolation.

References:

- [MarkItDown license](https://github.com/microsoft/markitdown/blob/main/LICENSE)
- [MCP package metadata](https://github.com/microsoft/markitdown/blob/main/packages/markitdown-mcp/pyproject.toml)
- [MarkItDown MCP setup and security guidance](https://github.com/microsoft/markitdown/blob/main/packages/markitdown-mcp/README.md)
- [LangChain MCP adapter documentation](https://reference.langchain.com/python/langchain-mcp-adapters)
