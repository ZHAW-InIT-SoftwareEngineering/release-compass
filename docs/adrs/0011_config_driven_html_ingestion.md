# 11. Config-driven HTML ingestion

## Status
Accepted; supersedes 0002 adapter

## Decision
One HTML adapter. Per-source YAML maps embedded JSON to domain models; every field explicit, null if absent. Reports name their source.

## Consequences
New source: YAML only.
