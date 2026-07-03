# kv-pool-layerwise-reuse

`kv-pool-layerwise-reuse` tracks feature development for layerwise KV pool reuse on the vLLM / vLLM Ascend / Mooncake bundle.

## Repositories

- `repos/vllm`: `kv-pool-layerwise-reuse`, based on `v0.20.2`
- `repos/vllm-ascend`: `kv-pool-layerwise-reuse`, based on `v0.20.2rc1`
- `repos/Mooncake`: `tag:v0.3.8.post1`, read-only by default

## Goal

Use the ader47 memcache-based layerwise reuse implementation as reference material, then implement equivalent KV pool layerwise reuse with Mooncake.

## Files

- `references/sources.md`: external links and source references.
- `references/snapshots/`: Markdown snapshots for RFCs and reference code.
- `status.md`: current phase and next steps.
- `repo-state.md`: human-readable repository state matching `workspace.lock.json`.
- `sync-log.md`: sync and branch setup history.
