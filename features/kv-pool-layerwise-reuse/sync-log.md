# kv-pool-layerwise-reuse Sync Log

## 2026-07-03

- Created workspace feature branch `kv-pool-layerwise-reuse`.
- Created `repos/vllm` feature branch from official `v0.20.2`.
- Created `repos/vllm-ascend` feature branch from official `v0.20.2rc1`.
- Checked out `repos/Mooncake` at bundled tag `v0.3.8.post1` for read-only dependency inspection.
- Recorded RFC and reference implementation sources for later design work.

## 2026-07-09

- Archived user-provided preliminary design `DESIGN-mooncake-layerwise-gva-put.md` as a feature snapshot for Mooncake layerwise KVPool put.
- Archived vLLM Ascend PR #11444 as the memcache layerwise KV pooling reference implementation, including a Markdown summary and raw patch.
- Archived vLLM Ascend PR #10733 as the layerwise KV pool reuse coordination target from `ader47/vllm-ascend`, including a Markdown summary and raw patch.
- Updated `references/sources.md` so the design note, PR snapshots, and patch archives are discoverable from the feature source index.
